"""
Writes the name / category / description / tags saved on an alpha before
submission.

Providers are interchangeable through one interface (`chat_json`), so
switching from OpenRouter+Mistral to plain Mistral, OpenAI, a local Ollama
model, or any other OpenAI-compatible endpoint is a one-line config change -
never a code change:

    llm:
      provider: openrouter   # openrouter | mistral | openai | ollama | custom | template
      model: mistralai/mistral-small-3.2-24b-instruct
      api_key_env: OPENROUTER_API_KEY   # blank = provider default

`template` needs no network access or API key at all: it fills in a
deterministic, factual description from the pack's own FIELDS glossary. It is
also the automatic fallback whenever the configured provider fails, so a bad
key or an outage never stops a run - it only makes the descriptions less
polished until you fix it.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Optional

import requests

from .metadata import FALLBACK_CATEGORY, Metadata, fields_in_expression, template_metadata

ALLOWED_CATEGORIES = [
    "PRICE_REVERSION", "PRICE_MOMENTUM", "VOLUME", "FUNDAMENTAL",
    "ANALYST", "PRICE_VOLUME", "RELATION", "SENTIMENT",
]

PROVIDER_DEFAULTS = {
    "openrouter": {"base_url": "https://openrouter.ai/api/v1/chat/completions", "model": "mistralai/mistral-small-3.2-24b-instruct", "api_key_env": "OPENROUTER_API_KEY"},
    "mistral": {"base_url": "https://api.mistral.ai/v1/chat/completions", "model": "mistral-small-latest", "api_key_env": "MISTRAL_API_KEY"},
    "openai": {"base_url": "https://api.openai.com/v1/chat/completions", "model": "gpt-4o-mini", "api_key_env": "OPENAI_API_KEY"},
    "ollama": {"base_url": "http://localhost:11434/v1/chat/completions", "model": "mistral", "api_key_env": ""},
}


class LLMError(Exception):
    pass


def resolve_provider_config(cfg) -> dict:
    provider = cfg.llm.provider
    if provider in ("none", "template"):
        return {"provider": "template"}
    defaults = PROVIDER_DEFAULTS.get(provider, {})
    if provider == "custom":
        base_url = cfg.llm.base_url
        if not base_url:
            raise LLMError("llm.provider is 'custom' but llm.base_url is empty")
    else:
        base_url = cfg.llm.base_url or defaults.get("base_url")
    return {
        "provider": provider,
        "base_url": base_url,
        "model": cfg.llm.model or defaults.get("model", ""),
        "api_key_env": cfg.llm.api_key_env or defaults.get("api_key_env", ""),
    }


def chat_json(prov: dict, system: str, user: str, temperature: float, timeout_s: float) -> str:
    """POST an OpenAI-style /chat/completions request. Returns the raw message content."""
    import os

    headers = {"Content-Type": "application/json"}
    key_env = prov.get("api_key_env")
    if key_env:
        key = os.environ.get(key_env, "").strip()
        if not key:
            raise LLMError(f"environment variable {key_env} is not set (needed for llm.provider: {prov['provider']})")
        headers["Authorization"] = f"Bearer {key}"
        if prov["provider"] == "openrouter":
            headers["HTTP-Referer"] = "http://localhost"
            headers["X-Title"] = "alphapilot"

    payload = {
        "model": prov["model"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": temperature,
        "max_tokens": 800,
    }
    try:
        r = requests.post(prov["base_url"], headers=headers, json=payload, timeout=timeout_s)
    except requests.RequestException as e:
        raise LLMError(f"{prov['provider']} request failed: {e!r}") from e

    if r.status_code != 200:
        raise LLMError(f"{prov['provider']} HTTP {r.status_code}: {r.text[:300]}")
    try:
        return r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise LLMError(f"{prov['provider']} returned an unexpected response shape: {e!r}") from e


def _parse_json_object(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise LLMError("no JSON object found in the model's reply")
    return json.loads(m.group(0))


def _clean(x, limit=700):
    return re.sub(r"\s+", " ", str(x or "")).strip()[:limit]


def build_prompt(expr: str, field_glossary: dict, settings_text: str, stats: dict, allowed_categories):
    fields = fields_in_expression(expr, field_glossary)
    field_lines = "\n".join(f"- {f}: {field_glossary[f]}" for f in fields) or "(no known field names matched - describe the expression on its own)"

    def fmt(v):
        try:
            return f"{float(v):.2f}"
        except (TypeError, ValueError):
            return "n/a"

    system = (
        "You write concise, factual research descriptions for quantitative equity alphas "
        "submitted to WorldQuant BRAIN. Reply with ONE valid JSON object and nothing else - "
        "no markdown, no code fences, no commentary."
    )
    user = f"""Alpha expression (FASTEXPR):
{expr}

Simulation settings: {settings_text}

Data fields used:
{field_lines}

In-sample context only (do NOT quote these numbers): sharpe {fmt(stats.get('sharpe'))}, fitness {fmt(stats.get('fitness'))}, turnover {fmt(stats.get('turnover'))}

Return a JSON object with exactly these keys:
"name": short identifier, max 40 chars, letters/digits/underscores only
"category": one of {json.dumps(list(allowed_categories))}
"idea": 2-3 sentences on the market intuition of what the expression captures
"rationale_data": 2-3 sentences on why these data fields are relevant, based ONLY on the field descriptions above
"rationale_operators": 2-3 sentences on what each operator in the expression does and why it is used
"tags": list of up to 3 short lowercase tags

Rules: describe only what the expression actually computes; do not invent data sources; do not promise returns; do not mention any numbers that were not given."""
    return system, user


def _try_provider(prov: dict, expr, field_glossary, settings_text, stats) -> Metadata:
    system, user = build_prompt(expr, field_glossary, settings_text, stats, ALLOWED_CATEGORIES)
    raw = chat_json(prov, system, user, temperature=prov.get("temperature", 0.3), timeout_s=prov.get("timeout_s", 90))
    obj = _parse_json_object(raw)

    idea = _clean(obj.get("idea"))
    r_data = _clean(obj.get("rationale_data"))
    r_ops = _clean(obj.get("rationale_operators"))
    if min(len(idea), len(r_data), len(r_ops)) < 30:
        raise LLMError("description too short / incomplete")

    description = f"Idea: {idea}\nRationale for data used: {r_data}\nRationale for operators used: {r_ops}"
    name = re.sub(r"[^A-Za-z0-9_]", "", str(obj.get("name", "")))[:40] or f"alpha_{hashlib.md5(expr.encode()).hexdigest()[:6]}"
    category = str(obj.get("category", "")).strip().upper()
    if category not in ALLOWED_CATEGORIES:
        category = FALLBACK_CATEGORY
    tags = []
    for t in (obj.get("tags") or [])[:3]:
        t = re.sub(r"[^a-z0-9_]", "", str(t).lower().replace(" ", "_"))
        if t:
            tags.append(t)

    return Metadata(name=name, category=category, description=description, tags=tags, source=prov["provider"])


def generate_metadata(cfg, expr: str, field_glossary: dict, pack_name: str, settings_text: str, stats: Optional[dict] = None) -> Metadata:
    stats = stats or {}
    prov = resolve_provider_config(cfg)
    if prov["provider"] == "template":
        return template_metadata(expr, field_glossary, pack_name)

    try:
        return _try_provider({**prov, "temperature": cfg.llm.temperature, "timeout_s": cfg.llm.timeout_s}, expr, field_glossary, settings_text, stats)
    except LLMError as primary_err:
        fallback = cfg.llm.fallback or "template"
        if fallback in ("none", "template") or fallback == prov["provider"]:
            meta = template_metadata(expr, field_glossary, pack_name)
            meta.source = f"template (primary failed: {primary_err})"
            return meta
        try:
            fb_cfg = {**PROVIDER_DEFAULTS.get(fallback, {}), "provider": fallback, "temperature": cfg.llm.temperature, "timeout_s": cfg.llm.timeout_s}
            return _try_provider(fb_cfg, expr, field_glossary, settings_text, stats)
        except LLMError as fallback_err:
            meta = template_metadata(expr, field_glossary, pack_name)
            meta.source = f"template (primary failed: {primary_err}; fallback failed: {fallback_err})"
            return meta


def generate_ai_metadata(cfg, expr: str, field_glossary: dict, pack_name: str, settings_text: str,
                         stats: Optional[dict] = None) -> Metadata:
    """Generate metadata with a configured model, failing clearly rather than silently substituting a template."""
    prov = resolve_provider_config(cfg)
    if prov["provider"] == "template":
        raise LLMError("AI metadata was requested, but llm.provider is 'template'. Configure a model provider or use llm.metadata_mode=template.")
    return _try_provider(
        {**prov, "temperature": cfg.llm.temperature, "timeout_s": cfg.llm.timeout_s},
        expr, field_glossary, settings_text, stats or {},
    )


def preflight(cfg) -> dict:
    """Cheap check before a long run: is the configured provider usable? Never raises."""
    prov = resolve_provider_config(cfg)
    if prov["provider"] == "template":
        return {"ok": True, "provider": "template", "detail": "no network calls needed"}
    try:
        _try_provider(
            {**prov, "temperature": cfg.llm.temperature, "timeout_s": cfg.llm.timeout_s},
            "rank(x)", {"x": "placeholder field for a connectivity check"}, "region X", {"sharpe": 1.0, "fitness": 1.0, "turnover": 0.2},
        )
        return {"ok": True, "provider": prov["provider"], "detail": f"model {prov['model']} responded"}
    except LLMError as e:
        return {"ok": False, "provider": prov["provider"], "detail": str(e)}
