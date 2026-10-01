"""
The "pack" contract.

A pack is a single .py file describing one dataset: which fields to use, which
BRAIN settings to simulate with, and how to build a pool of candidate alpha
expressions from those fields. This is the piece you hand Claude the dataset
screenshot / operator list for, and Claude writes one of these files - nothing
else in alphapilot needs to change.

Required module-level names
----------------------------
PACK_NAME        str   short identifier, e.g. "oth176_jpn"
PACK_DESCRIPTION str   one line, shown in `alphapilot packs`
SETTINGS         dict  kwargs for ace_lib.generate_alpha (region, universe, delay,
                        decay, neutralization, truncation, pasteurization,
                        unit_handling, nan_handling, max_trade)
FIELDS           dict  {field_id: human description}  (used for the LLM prompt
                        and shown to you before simulating, so you can eyeball
                        that the right dataset was picked up)
ALLOWED_OPERATORS list[str]  operators your account/pack is allowed to use
                        (checked against the account's real operator list at
                        runtime; anything missing is dropped with a warning,
                        not a crash)

def build_pool(seed: int, pool_size: int) -> dict[str, str]
    Returns {expression: family_tag}. `family_tag` is just a label (e.g.
    "ts_zscore", "group_level") used to spread the selected pool evenly across
    idea types instead of picking 900 near-duplicates - it is never sent to
    BRAIN. Must be deterministic for a given seed.

Optional
--------
MAX_RAW_FIELDS   int, default 3
MAX_OPERATORS    int, default 8
GENIUS_OPERATORS list[str]  operators that need the Genius tier; if the
                        account lacks Genius, expressions using them are
                        dropped (see `alphapilot doctor`).
"""
from __future__ import annotations

import ast
import difflib
import hashlib
import os
import re
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

OP_RE = re.compile(r"\b([a-z_][a-z0-9_]*)\s*\(")

REQUIRED_ATTRS = ["PACK_NAME", "PACK_DESCRIPTION", "SETTINGS", "FIELDS", "ALLOWED_OPERATORS", "build_pool"]


class PackError(Exception):
    pass


@dataclass
class Pack:
    name: str
    description: str
    settings: dict
    fields: dict
    allowed_operators: set
    genius_operators: set
    max_raw_fields: int
    max_operators: int
    build_pool_fn: object
    source_path: Path
    module: object = field(repr=False)
    key: str = ""          # file stem - the unique identity of this pack (PACK_NAME may be duplicated)
    file_hash: str = ""    # sha256 of the pack file's bytes - changes whenever the file is replaced/edited

    def build(self, seed: int, pool_size: int) -> dict:
        pool = self.build_pool_fn(seed=seed, pool_size=pool_size)
        if not isinstance(pool, dict) or not pool:
            raise PackError(f"pack {self.name!r}: build_pool() must return a non-empty dict {{expr: tag}}")
        return pool

    def field_ids(self):
        return list(self.fields.keys())


REQUIRED_SETTINGS_KEYS = {
    "region", "universe", "delay", "decay", "neutralization",
    "truncation", "pasteurization", "unit_handling", "nan_handling", "max_trade",
}


@dataclass
class PackInfo:
    """One pack file on disk. `key` (the file stem) is the pack's identity: unique per folder, and it is
    what config.yaml and the state database are keyed on. `pack_name` is only a display label and CAN be
    duplicated by two files (e.g. a re-downloaded `foo-1.py` next to `foo.py`) - that is detected, not trusted."""

    key: str
    path: Path
    pack_name: Optional[str]
    file_hash: str
    shadowed_by: Optional[Path] = None          # an earlier folder has a file with the same stem
    same_name_as: list = field(default_factory=list)   # keys of other packs declaring the same PACK_NAME
    description: Optional[str] = None
    error: Optional[str] = None

    @property
    def label(self) -> str:
        return self.pack_name or self.key


def _file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _static_pack_name(path: Path) -> Optional[str]:
    """Reads PACK_NAME from the file's AST without executing it (cheap, side-effect free)."""
    try:
        tree = ast.parse(Path(path).read_bytes())
    except (SyntaxError, ValueError, OSError):
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PACK_NAME" for t in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value
    return None


def _info_for(path: Path) -> PackInfo:
    path = Path(path).resolve()
    return PackInfo(key=path.stem, path=path, pack_name=_static_pack_name(path), file_hash=_file_hash(path))


def discover(search_dirs) -> list:
    """Every *.py pack file in the search folders (earlier folder wins on the same file stem; the loser is
    kept in the list with `shadowed_by` set so it can be reported instead of silently ignored)."""
    infos, first_by_key = [], {}
    for d in search_dirs:
        d = Path(d)
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.py")):
            if f.stem.startswith("_"):
                continue
            info = _info_for(f)
            if info.key in first_by_key:
                info.shadowed_by = first_by_key[info.key].path
            else:
                first_by_key[info.key] = info
            infos.append(info)
    live = [i for i in infos if not i.shadowed_by]
    for i in live:
        i.same_name_as = [o.key for o in live if o is not i and o.pack_name and o.pack_name == i.pack_name]
    return infos


def resolve_pack(name_or_path: str, search_dirs) -> PackInfo:
    """Turns whatever is in config.yaml (file stem, PACK_NAME, or a path to a .py) into exactly ONE pack
    file. A file stem always wins; a PACK_NAME shared by several files is refused as ambiguous."""
    ref = str(name_or_path).strip()
    if ref.endswith(".py") or os.sep in ref or "/" in ref:
        p = Path(ref).expanduser()
        if p.is_file():
            return _info_for(p)
        raise PackError(f"pack file not found: {ref}")
    live = [i for i in discover(search_dirs) if not i.shadowed_by]
    for exact in (lambda i: i.key == ref, lambda i: i.pack_name == ref,
                  lambda i: i.key.lower() == ref.lower(), lambda i: (i.pack_name or "").lower() == ref.lower()):
        hits = [i for i in live if exact(i)]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise PackError(
                f"pack name {ref!r} is ambiguous - {len(hits)} files declare it:\n  "
                + "\n  ".join(f"{h.key}  ({h.path})" for h in hits)
                + "\nSet `pack:` to the exact FILE name (without .py) of the one you want, "
                  "or delete/rename the extra file(s)."
            )
    names = sorted({x for i in live for x in (i.key, i.pack_name) if x})
    close = difflib.get_close_matches(ref, names, n=3, cutoff=0.5)
    tried = ", ".join(str(Path(d)) for d in search_dirs)
    hint = f"\nDid you mean: {', '.join(close)}?" if close else ""
    raise PackError(f"pack {ref!r} not found in: {tried}{hint}\nRun `alphapilot packs` to list available packs.")


def _exec_pack_file(path: Path):
    """Runs the pack file from its CURRENT bytes. Deliberately bypasses Python's import machinery: its
    __pycache__ check trusts source mtime+size, so a replaced file with the same size/mtime (copy over,
    unzip, re-download) silently ran the OLD compiled code. Nothing here reads or writes .pyc files."""
    data = Path(path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    safe = re.sub(r"\W", "_", Path(path).stem)
    prefix = f"alphapilot_pack_{safe}_"
    mod_name = prefix + digest[:12]
    for stale in [m for m in sys.modules if m.startswith(prefix) and m != mod_name]:
        del sys.modules[stale]
    module = types.ModuleType(mod_name)
    module.__file__ = str(path)
    sys.modules[mod_name] = module
    try:
        exec(compile(data, str(path), "exec", dont_inherit=True), module.__dict__)
    except BaseException:
        sys.modules.pop(mod_name, None)
        raise
    return module, digest


def load_pack(name_or_path: str, search_dirs) -> Pack:
    info = resolve_pack(name_or_path, search_dirs)
    path = info.path
    try:
        module, file_hash = _exec_pack_file(path)
    except Exception as e:
        raise PackError(f"pack {path} raised an error while loading: {e!r}") from e

    missing = [a for a in REQUIRED_ATTRS if not hasattr(module, a)]
    if missing:
        raise PackError(f"pack {path} is missing required attribute(s): {', '.join(missing)}")

    settings = getattr(module, "SETTINGS")
    if not isinstance(settings, dict):
        raise PackError(f"pack {path}: SETTINGS must be a dict")
    missing_keys = REQUIRED_SETTINGS_KEYS - set(settings)
    if missing_keys:
        raise PackError(f"pack {path}: SETTINGS is missing key(s): {sorted(missing_keys)}")

    fields = getattr(module, "FIELDS")
    if not isinstance(fields, dict) or not fields:
        raise PackError(f"pack {path}: FIELDS must be a non-empty dict {{field_id: description}}")

    allowed_ops = getattr(module, "ALLOWED_OPERATORS")
    if not isinstance(allowed_ops, (list, tuple, set)) or not allowed_ops:
        raise PackError(f"pack {path}: ALLOWED_OPERATORS must be a non-empty list")

    build_fn = getattr(module, "build_pool")
    if not callable(build_fn):
        raise PackError(f"pack {path}: build_pool must be a function")

    pack = Pack(
        name=str(getattr(module, "PACK_NAME")),
        description=str(getattr(module, "PACK_DESCRIPTION")),
        settings=dict(settings),
        fields=dict(fields),
        allowed_operators=set(allowed_ops),
        genius_operators=set(getattr(module, "GENIUS_OPERATORS", [])),
        max_raw_fields=int(getattr(module, "MAX_RAW_FIELDS", 3)),
        max_operators=int(getattr(module, "MAX_OPERATORS", 8)),
        build_pool_fn=build_fn,
        source_path=path,
        module=module,
        key=info.key,
        file_hash=file_hash,
    )

    # smoke-test build_pool with a tiny pool so a broken pack fails at `run`
    # start, not silently mid-simulation
    try:
        sample = pack.build(seed=1, pool_size=20)
    except Exception as e:
        raise PackError(f"pack {path}: build_pool(seed=1, pool_size=20) raised {e!r}") from e
    for expr in list(sample)[:20]:
        problems = validate_expression(expr, pack)
        if problems:
            raise PackError(f"pack {path}: sample expression {expr!r} is invalid: {'; '.join(problems)}")

    return pack


def ops_in(expr: str) -> set:
    return set(OP_RE.findall(expr))


def count_raw_fields(expr: str, field_ids) -> int:
    used = set()
    for fid in field_ids:
        if re.search(rf"\b{re.escape(fid)}\b", expr):
            used.add(fid)
    return len(used)


def balanced(expr: str) -> bool:
    depth = 0
    for ch in expr:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def validate_expression(expr: str, pack: Pack) -> list:
    """Local, offline checks only (no network). Returns a list of problem strings (empty = OK)."""
    problems = []
    if not expr or not expr.strip():
        problems.append("empty expression")
        return problems
    if not balanced(expr):
        problems.append("unbalanced parentheses")
    n_fields = count_raw_fields(expr, pack.field_ids())
    if n_fields == 0:
        problems.append("uses none of the pack's fields")
    if n_fields > pack.max_raw_fields:
        problems.append(f"uses {n_fields} raw fields (max {pack.max_raw_fields})")
    used_ops = ops_in(expr)
    n_ops = sum(len(re.findall(rf"\b{re.escape(o)}\s*\(", expr)) for o in pack.allowed_operators)
    if n_ops > pack.max_operators:
        problems.append(f"uses {n_ops} operator calls (max {pack.max_operators})")
    unknown = used_ops - pack.allowed_operators
    if unknown:
        problems.append(f"uses operator(s) not in ALLOWED_OPERATORS: {sorted(unknown)}")
    return problems


def normalize_focus(items) -> list:
    """Accepts a list or a comma-separated string. Returns a clean ordered list of focus tokens.

    Token meanings (order = run order):
      <field_id>        expressions that use ONLY that one field
      combo             expressions that mix 2+ fields (any combination)
      combo:<field_id>  mix expressions that include that field
    """
    if items is None:
        return []
    if isinstance(items, str):
        items = items.split(",")
    out = []
    for t in items:
        t = str(t).strip()
        if not t:
            continue
        if t.lower() in ("combo", "combos"):
            t = "combo"
        elif t.lower().startswith(("combo:", "combos:")):
            t = "combo:" + t.split(":", 1)[1].strip()
        if t not in out:
            out.append(t)
    return out


def validate_focus(focus, field_ids) -> list:
    ids = set(field_ids)
    bad = []
    for t in focus:
        base = t.split(":", 1)[1] if t.startswith("combo:") else t
        if t == "combo":
            continue
        if base not in ids:
            bad.append(f"unknown focus token {t!r} (fields: {sorted(ids)}, or 'combo', or 'combo:<field>')")
    return bad


def list_pack_infos(search_dirs) -> list:
    """discover() + a real load of each live pack (description / load error filled in)."""
    infos = discover(search_dirs)
    for i in infos:
        if i.shadowed_by:
            continue
        try:
            p = load_pack(str(i.path), search_dirs)
            i.description = p.description
            i.pack_name = p.name
        except PackError as e:
            i.error = str(e)
    for i in infos:  # PACK_NAME may only now be known for packs whose name is not a plain literal
        if not i.shadowed_by:
            i.same_name_as = [o.key for o in infos if o is not i and not o.shadowed_by and o.pack_name and o.pack_name == i.pack_name]
    return infos
