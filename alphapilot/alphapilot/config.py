"""Configuration: built-in defaults < <home>/config.yaml < --set key=value overrides."""
from __future__ import annotations

import copy
import os
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


class ConfigError(Exception):
    pass


SUBMIT_MODES = ("off", "dry", "ask", "auto")
LLM_PROVIDERS = ("openrouter", "mistral", "openai", "ollama", "custom", "template", "none")


def default_config() -> dict:
    return {
        # name of a pack (in <home>/packs or the built-in packs folder) or a path to a .py file
        "pack": "oth176_jpn",
        "api": {
            "base_url": os.environ.get("BRAIN_API_URL", "https://api.worldquantbrain.com"),
            "timeout_s": 60,
            "max_retry_after_s": 60,      # cap on how long we sleep between polls
        },
        "session": {
            "min_seconds_left": 1800,     # re-authenticate (face check) BEFORE a batch if less than this remains
            "reuse_cookies": True,        # remember the session between runs (saved in <home>/session.json)
            "persona_timeout_min": 20,    # how long to wait for you to finish the face check
            "persona_poll_seconds": 4,
            "open_browser": True,         # open the face-check link automatically (never inside Docker)
        },
        "simulation": {
            "pool_size": 1000,            # alphas to draw from the pack
            "batch_size": 10,             # alphas per multi-simulation (1..10)
            "seed": 20260920,             # pool selection seed (same seed = same pool)
            "batch_timeout_min": 180,
            "max_attempts": 2,            # re-tries for transient simulation failures (TIMEOUT / FAIL)
            "on_daily_limit": "stop",     # stop | wait
            "error_streak_halt": 20,      # stop the whole run if this many simulations IN A ROW fail
                                           # with a similar error (catches a daily/rate limit that BRAIN
                                           # reports as a normal simulation failure instead of HTTP 429 -
                                           # without this, a systemic problem burns through the rest of
                                           # the pool one alpha at a time instead of stopping early)
        },
        "submit": {
            "mode": "ask",                # off | dry | ask | auto
            "precheck": False,            # False = skip /check and just submit; the platform accepts or refuses.
                                          # True = run the official /check first (dry mode always does).
            "max_per_run": 1,             # stop the WHOLE run after this many submissions (0 = no limit) ...
            "max_per_day": 1,             # ... or this many per calendar day (see timezone)
            "timezone": "America/New_York",
            "cycle_every_batches": 1,     # look for submittable alphas after every N batches
            "max_candidates_per_cycle": 15,
            "min_sharpe": 0.0,            # extra local filters on top of the platform's own tests
            "min_fitness": 0.0,
            "poll_seconds": 10,
            "timeout_min": 15,
                "show_polling": True,         # print async submission polling progress
            "halt_on_unsure": False,       # False = warn, skip to next candidate, keep batch running; True = halt run
        },
        "llm": {
            "provider": "template",       # openrouter | mistral | openai | ollama | custom | template
            "model": "",                  # empty = provider default
            "base_url": "",               # only needed for provider: custom
            "api_key_env": "",            # empty = provider default (e.g. MISTRAL_API_KEY)
            "fallback": "template",       # provider to try if the main one fails (or "template")
            "temperature": 0.3,
            "timeout_s": 90,
        },
        "run": {
            "focus": [],                  # ordered field filter, e.g. [oth176_eq_medium, combo]. Empty = whole pool.
                                          # <field> = expressions using only that field | combo = any 2+ field mix
                                          # | combo:<field> = mixes that include that field
        },
        "notify": {
            "webhook_url": "",            # Slack / Discord / any JSON webhook
            "ntfy_url": "",               # e.g. https://ntfy.sh/my-secret-topic
        },
        "logging": {"verbose": False},
    }


class Cfg(dict):
    """dict with attribute access: cfg.submit.mode"""

    def __getattr__(self, key):
        try:
            v = self[key]
        except KeyError:
            raise AttributeError(key) from None
        return Cfg(v) if isinstance(v, dict) else v


def deep_merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def parse_overrides(items) -> dict:
    """['submit.mode=auto', 'simulation.batch_size=5'] -> nested dict (values parsed as YAML scalars)."""
    out: dict = {}
    for item in items or []:
        if "=" not in item:
            raise ConfigError(f"--set expects key=value, got: {item!r}")
        key, _, raw = item.partition("=")
        val = yaml.safe_load(raw) if yaml else raw
        node = out
        parts = key.strip().split(".")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = val
    return out


def config_path(home: Path) -> Path:
    return Path(home) / "config.yaml"


def read_file_config(home: Path) -> dict:
    p = config_path(home)
    if not p.exists():
        return {}
    if yaml is None:
        raise ConfigError("PyYAML is not installed: pip install pyyaml")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"{p} is not valid YAML: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"{p} must contain a YAML mapping")
    return data


def save_file_config(home: Path, data: dict) -> None:
    if yaml is None:
        raise ConfigError("PyYAML is not installed: pip install pyyaml")
    p = config_path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    header = "# alphapilot settings (edit freely; see config.example.yaml for every option)\n"
    p.write_text(header + yaml.safe_dump(data, sort_keys=False, default_flow_style=False), encoding="utf-8")


def load_config(home: Path, overrides=None) -> Cfg:
    merged = deep_merge(default_config(), read_file_config(home))
    merged = deep_merge(merged, parse_overrides(overrides))
    problems = validate(merged)
    if problems:
        raise ConfigError("Configuration problems:\n  - " + "\n  - ".join(problems))
    return Cfg(merged)


def validate(c: dict) -> list:
    bad = []

    def num(path, lo=None, hi=None, integer=False):
        node = c
        for p in path.split("."):
            node = node.get(p) if isinstance(node, dict) else None
        ok = isinstance(node, (int, float)) and not isinstance(node, bool)
        if ok and integer and int(node) != node:
            ok = False
        if ok and lo is not None and node < lo:
            ok = False
        if ok and hi is not None and node > hi:
            ok = False
        if not ok:
            rng = f" between {lo} and {hi}" if lo is not None and hi is not None else (f" >= {lo}" if lo is not None else "")
            bad.append(f"{path} must be a number{rng} (got {node!r})")

    if not isinstance(c.get("pack"), str) or not c["pack"].strip():
        bad.append("pack must be a pack name or path")
    if not str(c["api"].get("base_url", "")).startswith("http"):
        bad.append("api.base_url must start with http(s)://")
    num("api.timeout_s", 1)
    num("api.max_retry_after_s", 0)
    num("session.min_seconds_left", 0)
    num("session.persona_timeout_min", 0)
    num("session.persona_poll_seconds", 0)
    num("simulation.pool_size", 1, integer=True)
    num("simulation.batch_size", 1, 10, integer=True)
    num("simulation.batch_timeout_min", 0)
    num("simulation.max_attempts", 1, integer=True)
    num("simulation.error_streak_halt", 1, integer=True)
    if c["simulation"]["on_daily_limit"] not in ("stop", "wait"):
        bad.append("simulation.on_daily_limit must be 'stop' or 'wait'")
    if c["submit"]["mode"] not in SUBMIT_MODES:
        bad.append(f"submit.mode must be one of {SUBMIT_MODES}")
    num("submit.max_per_run", 0, integer=True)
    num("submit.max_per_day", 0, integer=True)
    num("submit.cycle_every_batches", 1, integer=True)
    num("submit.max_candidates_per_cycle", 1, integer=True)
    num("submit.min_sharpe")
    num("submit.min_fitness")
    num("submit.poll_seconds", 0)
    num("submit.timeout_min", 0)
    if not isinstance(c["submit"].get("show_polling", True), bool):
        bad.append("submit.show_polling must be a boolean")
    if not isinstance(c["submit"].get("halt_on_unsure", False), bool):
        bad.append("submit.halt_on_unsure must be a boolean (true or false)")
    focus = (c.get("run") or {}).get("focus", [])
    if not isinstance(focus, list) or not all(isinstance(x, str) for x in focus):
        bad.append("run.focus must be a list of strings, e.g. [oth176_eq_medium, combo]")
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(c["submit"]["timezone"])
    except Exception:
        bad.append(f"submit.timezone {c['submit']['timezone']!r} is not a valid timezone name (e.g. America/New_York, UTC)")
    if c["llm"]["provider"] not in LLM_PROVIDERS:
        bad.append(f"llm.provider must be one of {LLM_PROVIDERS}")
    if c["llm"]["provider"] == "custom" and not c["llm"].get("base_url"):
        bad.append("llm.provider 'custom' needs llm.base_url")
    return bad


def resolve_home(arg=None) -> Path:
    return Path(arg or os.environ.get("ALPHAPILOT_HOME") or "data").expanduser().resolve()
