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

import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

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


def _resolve_path(name_or_path: str, search_dirs) -> Path:
    p = Path(name_or_path)
    if p.suffix == ".py" and p.exists():
        return p.resolve()
    for d in search_dirs:
        cand = Path(d) / f"{name_or_path}.py"
        if cand.exists():
            return cand.resolve()
    tried = ", ".join(str(Path(d) / f"{name_or_path}.py") for d in search_dirs)
    raise PackError(f"pack {name_or_path!r} not found. Tried: {tried}\nRun `alphapilot packs` to list available packs.")


def load_pack(name_or_path: str, search_dirs) -> Pack:
    path = _resolve_path(name_or_path, search_dirs)
    mod_name = f"alphapilot_pack_{path.stem}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise PackError(f"could not load pack file: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    try:
        spec.loader.exec_module(module)
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


def list_packs(search_dirs):
    out = []
    seen = set()
    for d in search_dirs:
        d = Path(d)
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.py")):
            if f.stem in seen or f.stem.startswith("_"):
                continue
            seen.add(f.stem)
            try:
                p = load_pack(f.stem, search_dirs)
                out.append((p.name, p.description, str(f), None))
            except PackError as e:
                out.append((f.stem, "(failed to load)", str(f), str(e)))
    return out
