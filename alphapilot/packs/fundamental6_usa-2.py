"""
alphapilot pack: Company Fundamental Data for Equity · USA / D1 / TOP3000

Built the same way as oth176_jpn: Data Explorer screenshot + simulation
settings screenshot + the operator list for the account.

Nothing outside this file is dataset-specific - the CLI, the BRAIN client,
the LLM description writer and the submission logic are all generic.

Power Pool Oct'26 (28 Sep - 26 Oct 2026) compliant: delay 1, a single dataset
(fundamental), and no support / pv1 group fields (industry, subindustry, sector...)
anywhere in an expression. Peer-relative ideas use size buckets of the dataset's own
fields instead.

USE_GENIUS: leave False unless the account has the Genius tier. When False,
every Genius operator is removed from ALLOWED_OPERATORS and every candidate
expression that uses one is dropped from the pool.
"""
from __future__ import annotations

import random
import re
from itertools import combinations, permutations

# ---------------------------------------------------------------------------
# Account switch: set True ONLY if your account has Genius.
# ---------------------------------------------------------------------------
USE_GENIUS = False

PACK_NAME = "fundamental6_usa"
PACK_DESCRIPTION = (
    "Company Fundamental Data for Equity (6 balance-sheet / income fields, "
    "ratio-driven), USA/D1/TOP3000"
)

SETTINGS = {
    "region": "USA",
    "universe": "TOP3000",
    "delay": 1,
    "decay": 4,
    "neutralization": "SECTOR",
    "truncation": 0.08,
    "pasteurization": "ON",
    "test_period": "P0Y0M0D",
    "unit_handling": "VERIFY",
    "nan_handling": "ON",
    "max_trade": "OFF",
}

FIELDS = {
    "assets": "Assets - Total",
    "operating_income": "Operating Income After Depreciation - Quarterly",
    "liabilities": "Liabilities - Total",
    "enterprise_value": "Enterprise Value",
    "sales": "Sales/Turnover (Net)",
    "debt": "Debt",
}

MAX_RAW_FIELDS = 3
MAX_OPERATORS = 8

# Only operators that have their own formal entry (Level + Scope + Description) in
# WorldQuant_BRAIN_Operators.md and can be used in a Regular alpha. Operators that
# only appear inside examples (e.g. ts_returns) or have no complete entry are NOT listed.
_ALL_OPERATORS = [
    # arithmetic
    "abs", "add", "densify", "divide", "inverse", "log", "max", "min",
    "multiply", "power", "reverse", "sigmoid", "sign", "signed_power", "sqrt",
    "subtract", "tanh",
    # logical
    "and", "if_else", "is_nan", "not", "or",
    # time series
    "days_from_last_change", "hump", "kth_element", "last_diff_value",
    "ts_arg_max", "ts_arg_min", "ts_av_diff", "ts_backfill", "ts_corr",
    "ts_count_nans", "ts_covariance", "ts_decay_linear", "ts_delay", "ts_delta",
    "ts_entropy", "ts_mean", "ts_min_max_cps", "ts_min_max_diff", "ts_product",
    "ts_quantile", "ts_rank", "ts_regression", "ts_scale", "ts_skewness",
    "ts_std_dev", "ts_step", "ts_sum", "ts_target_tvr_decay", "ts_zscore",
    # cross sectional
    "normalize", "quantile", "rank", "regression_proj", "scale",
    "vector_neut", "vector_proj", "winsorize", "zscore",
    # transformational
    "bucket", "trade_when",
    # group
    "group_backfill", "group_cartesian_product", "group_extra", "group_mean",
    "group_neutralize", "group_rank", "group_scale", "group_zscore",
]

# Level: genius in the operators file (only those relevant to a Regular alpha here).
GENIUS_OPERATORS = [
    "sigmoid", "tanh", "ts_entropy", "ts_min_max_cps", "ts_min_max_diff",
    "ts_skewness", "ts_target_tvr_decay", "regression_proj", "vector_neut",
    "vector_proj", "group_cartesian_product", "group_extra",
]

ALLOWED_OPERATORS = (
    list(_ALL_OPERATORS)
    if USE_GENIUS
    else [o for o in _ALL_OPERATORS if o not in GENIUS_OPERATORS]
)

_GENIUS_RE = re.compile(r"\b(?:" + "|".join(map(re.escape, GENIUS_OPERATORS)) + r")\s*\(")

# Power Pool Oct'26: support fields (pv1 group fields) are not allowed in expressions.
_SUPPORT_FIELDS = ["industry", "subindustry", "sector", "market", "exchange", "country", "currency"]
_SUPPORT_RE = re.compile(r"\b(?:" + "|".join(_SUPPORT_FIELDS) + r")\b")

_FIELD_NAMES = list(FIELDS.keys())
assets, op_inc, liab, ev, sales, debt = _FIELD_NAMES

# Strictly positive size-like fields (safe for log). operating_income can be
# negative and debt can be zero, so they are excluded.
_LOG_FIELDS = [assets, liab, ev, sales]


def _R(a, b):
    """Ratio a / b. Uses the epsilon form from the operators file because
    divide() raises an error on a zero denominator (debt etc. can be 0)."""
    return f"divide({a},add({b},0.0001))"


def _generate_candidates():
    """Every candidate expression this pack knows how to build, tagged by idea family."""
    candidates: dict[str, str] = {}

    def add(expr, tag):
        candidates.setdefault(expr.strip(), tag)

    fields = _FIELD_NAMES
    pairs = list(combinations(fields, 2))
    ordered = list(permutations(fields, 2))  # (numerator, denominator)

    # 1. single-field level
    for f in fields:
        add(f"rank({f})", "level")
        add(f"-rank({f})", "level")
        add(f"zscore({f})", "level")
        add(f"-zscore({f})", "level")
        add(f"normalize({f},useStd=true)", "level")
        add(f"rank(winsorize({f},std=4))", "level")
        add(f"rank(quantile({f},driver=gaussian))", "level")
    for f in _LOG_FIELDS:
        add(f"rank(log({f}))", "level")
        add(f"-rank(log({f}))", "level")

    # 2. coverage / staleness (instrument coverage is only ~50%)
    for f in fields:
        for d in [63, 126, 252]:
            add(f"rank(ts_backfill({f},{d}))", "backfill")
            add(f"-rank(ts_backfill({f},{d}))", "backfill")
        add(f"rank(days_from_last_change({f}))", "staleness")
        add(f"-rank(days_from_last_change({f}))", "staleness")
        add(f"rank(last_diff_value({f},60))", "staleness")
        add(f"rank(subtract({f},last_diff_value({f},60)))", "staleness")
        add(f"rank(subtract({f},last_diff_value({f},120)))", "staleness")

    # 3. single-field growth / trend (63 days ~ one reporting quarter)
    for f in fields:
        for d in [63, 126, 252]:
            g = f"divide(ts_delta({f},{d}),add(abs(ts_mean({f},{d})),0.0001))"
            add(f"rank({g})", "growth")
            add(f"-rank({g})", "growth")
            add(f"rank(ts_zscore({f},{d}))", "field_ts")
            add(f"-rank(ts_zscore({f},{d}))", "field_ts")
            add(f"rank(ts_rank({f},{d}))", "field_ts")
            add(f"rank(ts_av_diff({f},{d}))", "field_ts")
            add(f"-rank(ts_av_diff({f},{d}))", "field_ts")

    # 4. cross-sectional ratio level (30 ordered ratios)
    for a, b in ordered:
        r = _R(a, b)
        add(f"rank({r})", "ratio")
        add(f"-rank({r})", "ratio")
        add(f"zscore({r})", "ratio")
        add(f"-zscore({r})", "ratio")
        add(f"rank(winsorize({r},std=4))", "ratio")
        add(f"rank(quantile({r},driver=gaussian))", "ratio")

    # 5. ratio time-series dynamics
    for a, b in ordered:
        r = _R(a, b)
        for d in [63, 126, 252]:
            add(f"rank(ts_delta({r},{d}))", "ratio_ts")
            add(f"-rank(ts_delta({r},{d}))", "ratio_ts")
            add(f"rank(ts_zscore({r},{d}))", "ratio_ts")
            add(f"-rank(ts_zscore({r},{d}))", "ratio_ts")
            add(f"rank(ts_rank({r},{d}))", "ratio_ts")
            add(f"rank(ts_av_diff({r},{d}))", "ratio_ts")
            add(f"rank(ts_mean({r},{d}))", "ratio_ts")
            add(f"rank(ts_decay_linear({r},{d}))", "ratio_ts")

    # 6. shared-denominator composites (value / quality / leverage blends, 3 raw fields)
    for den in fields:
        others = [f for f in fields if f != den]
        for a, b in combinations(others, 2):
            za, zb = f"zscore({_R(a, den)})", f"zscore({_R(b, den)})"
            add(f"rank(add({za},{zb}))", "shared_den")
            add(f"rank(subtract({za},{zb}))", "shared_den")
            add(f"rank(subtract({zb},{za}))", "shared_den")
            add(f"rank(ts_zscore(add({za},{zb}),126))", "shared_den_ts")
            add(f"rank(ts_delta(add({za},{zb}),63))", "shared_den_ts")
            add(f"rank(ts_zscore(subtract({za},{zb}),126))", "shared_den_ts")
            add(f"rank(ts_zscore(subtract({zb},{za}),126))", "shared_den_ts")

    # 7. shared-numerator composites
    for num in fields:
        others = [f for f in fields if f != num]
        for x, y in combinations(others, 2):
            zx, zy = f"zscore({_R(num, x)})", f"zscore({_R(num, y)})"
            add(f"rank(add({zx},{zy}))", "shared_num")
            add(f"rank(subtract({zx},{zy}))", "shared_num")
            add(f"rank(subtract({zy},{zx}))", "shared_num")
            add(f"rank(ts_zscore(subtract({zx},{zy}),126))", "shared_num_ts")
            add(f"rank(ts_delta(add({zx},{zy}),63))", "shared_num_ts")

    # 8. cross-field correlation / covariance
    for a, b in pairs:
        for d in [126, 252]:
            add(f"rank(ts_corr({a},{b},{d}))", "ts_corr")
            add(f"-rank(ts_corr({a},{b},{d}))", "ts_corr")
            add(f"rank(ts_covariance({a},{b},{d}))", "ts_cov")
            add(f"-rank(ts_covariance({a},{b},{d}))", "ts_cov")

    # 9. cross-field time-series regression
    for y, x in ordered:
        for d in [126, 252]:
            add(f"rank(ts_regression({y},{x},{d},lag=0,rettype=0))", "ts_reg_resid")
            add(f"rank(ts_regression({y},{x},{d},lag=0,rettype=2))", "ts_reg_slope")
    for a, b in pairs:
        for d in [126, 252]:
            add(f"rank(ts_regression({a},{b},{d},lag=0,rettype=6))", "ts_reg_r2")

    # 10. ratio backfill (instrument coverage is ~50%)
    for a, b in ordered:
        r = _R(a, b)
        for d in [63, 126, 252]:
            add(f"rank(ts_backfill({r},{d}))", "ratio_backfill")

    # 11. size-bucket groups built ONLY from this dataset's own fields.
    #     Power Pool forbids pv1 group fields (industry, subindustry, sector, ...),
    #     so peer-relative signals use bucket(rank(<dataset field>)) as the group.
    for bucket_field in [assets, ev, sales]:
        bucket_group = f'bucket(rank({bucket_field}),range="0, 1, 0.1")'
        for f in fields:
            if f == bucket_field:
                continue
            add(f"group_rank(rank({f}),{bucket_group})", "bucket_level")
            add(f"group_neutralize(rank({f}),{bucket_group})", "bucket_level")
            add(f"group_zscore(zscore({f}),{bucket_group})", "bucket_level")
        for a, b in ordered:
            r = _R(a, b)
            add(f"group_rank(rank({r}),{bucket_group})", "bucket")
            add(f"group_neutralize(rank({r}),{bucket_group})", "bucket")
            add(f"group_zscore(zscore({r}),{bucket_group})", "bucket")
            add(f"group_scale(rank({r}),{bucket_group})", "bucket")
            for d in [63, 126]:
                add(f"group_rank(rank(ts_delta({r},{d})),{bucket_group})", "bucket_ts")
                add(f"group_zscore(ts_zscore({r},{d}),{bucket_group})", "bucket_ts")

    # 13. hump / turnover control
    for a, b in ordered:
        r = _R(a, b)
        add(f"hump(rank({r}),hump=0.01)", "hump")
        add(f"hump(rank(ts_zscore({r},126)),hump=0.01)", "hump")
        add(f"hump(rank(ts_delta({r},63)),hump=0.01)", "hump")

    # 14. trade_when (act around filing updates / extremes)
    for a, b in ordered:
        r = _R(a, b)
        add(f"trade_when(days_from_last_change({a})<=5,rank({r}),-1)", "trade_when")
        add(f"trade_when(abs(ts_zscore({r},126))>1,rank({r}),-1)", "trade_when")
        add(f"trade_when(ts_rank({r},126)>0.7,rank({r}),ts_rank({r},126)<0.3)", "trade_when")
    for f in fields:
        add(f"trade_when(days_from_last_change({f})<=5,rank({f}),-1)", "trade_when")

    # 15. decayed / smoothed ratio signals
    for a, b in ordered:
        r = _R(a, b)
        for d in [63, 126, 252]:
            add(f"rank(ts_decay_linear(ts_zscore({r},{d}),20))", "decay_combo")
            add(f"rank(ts_decay_linear(ts_rank({r},{d}),20))", "decay_combo")

    # 16. Genius-only ideas (dropped automatically when USE_GENIUS is False)
    for y, x in ordered:
        add(f"rank(vector_neut(zscore({y}),zscore({x})))", "neut")
        add(f"rank(subtract(zscore({y}),regression_proj(zscore({y}),zscore({x}))))", "neut")
        for d in [60, 126]:
            add(f"rank(ts_zscore(vector_neut(zscore({y}),zscore({x})),{d}))", "neut_ts")
    for a, b in ordered:
        r = _R(a, b)
        for d in [126, 252]:
            add(f"rank(ts_min_max_diff({r},{d}))", "ts_shape")
            add(f"rank(ts_skewness({r},{d}))", "ts_shape")

    return candidates


def _validate_local(expr: str) -> bool:
    """Cheap offline filter mirroring the pack's own limits (kept in sync with packs_api.validate_expression)."""
    if not USE_GENIUS and _GENIUS_RE.search(expr):
        return False
    if _SUPPORT_RE.search(expr):
        return False
    if "vec_" in expr and not any(v in expr for v in ("vec_avg(", "vec_sum(")):
        return False
    used = {f for f in FIELDS if re.search(rf"\b{re.escape(f)}\b", expr)}
    if not used or len(used) > MAX_RAW_FIELDS:
        return False
    n_ops = sum(len(re.findall(rf"\b{re.escape(o)}\s*\(", expr)) for o in ALLOWED_OPERATORS)
    if n_ops > MAX_OPERATORS:
        return False
    depth = 0
    for ch in expr:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def build_pool(seed: int, pool_size: int) -> dict:
    """Deterministic pool of `pool_size` expressions, spread round-robin across idea families."""
    all_candidates = {e: t for e, t in _generate_candidates().items() if _validate_local(e)}
    if len(all_candidates) < pool_size:
        raise ValueError(
            f"fundamental6_usa pack only has {len(all_candidates)} valid candidates, "
            f"requested pool_size={pool_size}"
        )

    rng = random.Random(seed)
    by_family: dict[str, list] = {}
    for expr, tag in all_candidates.items():
        by_family.setdefault(tag, []).append(expr)
    for tag in by_family:
        by_family[tag].sort()
        rng.shuffle(by_family[tag])

    order = sorted(by_family)
    chosen: dict[str, str] = {}
    while len(chosen) < pool_size:
        progressed = False
        for tag in order:
            if by_family[tag]:
                expr = by_family[tag].pop()
                chosen[expr] = tag
                progressed = True
                if len(chosen) == pool_size:
                    break
        if not progressed:
            break
    return chosen
