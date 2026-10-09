"""Small shared helpers. Standard library only."""
from __future__ import annotations

import hashlib
import json
import logging
import logging.handlers
import os
import re
import sys
import contextvars
from datetime import datetime, timezone
from pathlib import Path

LOGGER = logging.getLogger("alphapilot")
_OUTPUT_HANDLER = contextvars.ContextVar("alphapilot_output_handler", default=None)


def set_output_handler(handler):
    """Route business-layer progress to an interactive renderer when installed."""
    return _OUTPUT_HANDLER.set(handler)


def reset_output_handler(token):
    _OUTPUT_HANDLER.reset(token)


class Theme:
    """Terminal presentation policy shared by all user-facing output."""

    _COLORS = {
        "accent": "\x1b[94m",
        "success": "\x1b[92m",
        "warning": "\x1b[93m",
        "error": "\x1b[91m",
        "muted": "\x1b[90m",
        "border": "\x1b[90m",
        "reset": "\x1b[0m",
        "bold": "\x1b[1m",
    }

    @staticmethod
    def enabled() -> bool:
        """Enable styling only for an interactive terminal explicitly allowing color."""
        try:
            return (sys.stdout.isatty() and "NO_COLOR" not in os.environ
                    and not os.environ.get("CI") and os.environ.get("TERM") != "dumb")
        except (AttributeError, OSError):
            return False

    @staticmethod
    def symbol(unicode_symbol: str, ascii_symbol: str) -> str:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        try:
            unicode_symbol.encode(encoding)
            return unicode_symbol
        except (UnicodeEncodeError, LookupError):
            return ascii_symbol

    @classmethod
    def paint(cls, value: str, role: str) -> str:
        if not cls.enabled():
            return value
        color = cls._COLORS.get(role, "")
        if os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
            color = {
                "accent": "\x1b[38;2;105;184;255m", "success": "\x1b[38;2;105;200;150m",
                "warning": "\x1b[38;2;235;185;95m", "error": "\x1b[38;2;235;115;115m",
                "muted": "\x1b[38;2;145;155;170m", "border": "\x1b[38;2;80;95;115m",
            }.get(role, color)
        return f"{color}{value}{cls._COLORS['reset']}"

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
        return bool(sys.stdin.isatty() and sys.stdout.isatty() and Theme.enabled())
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
    """Write concise user output to stdout and the original message to the log."""
    text = msg
    if msg:
        for prefix, role in (("HALTED:", "error"), ("Error:", "error"), ("!!", "warning"),
                             ("Interrupted", "warning"), ("SUBMITTED:", "success"),
                             ("OK", "success"), ("Face check needed:", "accent")):
            if msg.lstrip().startswith(prefix):
                text = msg.replace(prefix, Theme.paint(prefix, role), 1)
                break
    handler = _OUTPUT_HANDLER.get()
    if handler is not None:
        handler(msg)
        LOGGER.log(level, msg)
        return
    print(text, flush=True)
    LOGGER.log(level, msg)


def banner(lines, char: str = "=") -> None:
    """Render a compact, width-aware section heading without an oversized box."""
    if not lines:
        return
    handler = _OUTPUT_HANDLER.get()
    if handler is not None:
        handler(" | ".join(lines))
        LOGGER.info("BANNER: %s", " | ".join(lines))
        return
    title, *details = lines
    print(flush=True)
    print(f"{Theme.symbol('✦', '*')} {Theme.paint(title, 'accent')}")
    for line in details:
        print(f"  {Theme.paint(line, 'muted')}")
    try:
        width = os.get_terminal_size(sys.stdout.fileno()).columns
    except (OSError, AttributeError, ValueError):
        width = 80
    rule = Theme.symbol("─", "-") * max(12, min(width, 100))
    print(Theme.paint(rule, "border"), flush=True)
    LOGGER.info("BANNER: %s", " | ".join(lines))
