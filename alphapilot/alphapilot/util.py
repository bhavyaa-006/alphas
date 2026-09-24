"""Small shared helpers. Standard library only."""
from __future__ import annotations

import hashlib
import json
import logging
import logging.handlers
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

LOGGER = logging.getLogger("alphapilot")

# an identifier directly followed by "(" is an operator call
OP_RE = re.compile(r"\b([a-z_][a-z0-9_]*)\s*\(")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_str(tz_name: str = "America/New_York") -> str:
    """Calendar day in the configured timezone (used for the per-day submission cap)."""
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def fmt_duration(sec) -> str:
    try:
        sec = int(max(0, float(sec)))
    except (TypeError, ValueError):
        return "?"
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def sha256_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


def in_docker() -> bool:
    return os.environ.get("ALPHAPILOT_DOCKER") == "1" or os.path.exists("/.dockerenv")


def is_tty() -> bool:
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except Exception:
        return False


def ops_in(expr: str) -> set:
    return set(OP_RE.findall(expr))


def count_ops(expr: str) -> int:
    return len(OP_RE.findall(expr))


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


# ---------------------------------------------------------------- files / secrets

def write_private(path, text: str) -> None:
    """Write a file readable only by the owner (best effort on Windows)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def load_dotenv(path) -> dict:
    """Minimal .env reader. Existing environment variables win."""
    out = {}
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key] = val
        if key not in os.environ or os.environ[key] == "":
            os.environ[key] = val
    return out


def set_dotenv_value(path, key: str, value: str) -> None:
    p = Path(path)
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    new = f"{key}={value}"
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key:
            lines[i] = new
            break
    else:
        lines.append(new)
    write_private(p, "\n".join(lines) + "\n")
    os.environ[key] = value


# ---------------------------------------------------------------- output

def setup_logging(log_file, verbose: bool = False) -> None:
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.handlers.clear()
    try:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        LOGGER.addHandler(fh)
    except OSError:
        pass
    if verbose:
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        LOGGER.addHandler(ch)


def say(msg: str = "", level: int = logging.INFO, stamp: bool = True) -> None:
    """User-facing line: printed with a timestamp and also written to the log file."""
    text = f"{time.strftime('%H:%M:%S')}  {msg}" if (stamp and msg) else msg
    print(text, flush=True)
    LOGGER.log(level, msg)


def banner(lines, char: str = "=") -> None:
    width = max(len(x) for x in lines) + 4
    width = min(max(width, 40), 100)
    print(flush=True)
    print(char * width)
    for x in lines:
        print(f"  {x}")
    print(char * width, flush=True)
    LOGGER.info("BANNER: %s", " | ".join(lines))
