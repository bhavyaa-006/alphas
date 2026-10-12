"""
alphapilot pack: RSK82 "ETF Risk Data" · USA / D1 / TOP3000

Dataset notes (from the Data Explorer screenshot):
  * All fields are VECTOR type, so every raw field is wrapped in vec_avg() before use.
  * Fields are already z-normalised ownership / flow measures of US-listed ETFs
    (ownership as % of market cap, its 1w / 1m / 3m deltas and growth, and aggregate
    market value held), so cross-field blends and spreads are on a comparable scale.
  * Coverage is 98-100%, so backfill matters little; staleness and slow-moving-flow
    ideas (long windows, hump, trade_when) matter more.
  * Pyramid theme multiplier 1.3.

Settings follow the BRAIN simulation-settings screenshot: Fast Expression, Equity,
USA / delay 1 / TOP3000, Sector neutralization, decay 4, truncation 0.08, pasteurization ON,
unit handling VERIFY, NaN handling ON, test period 0Y0M, max trade OFF.

Limits mirrored from the other packs: <= 3 raw fields and <= 8 operators per expression
(vec_avg counts as an operator), every called function must be in ALLOWED_OPERATORS.
"""
from __future__ import annotations

import random
import re
from itertools import combinations, permutations

PACK_NAME = "rsk82_usa"
PACK_DESCRIPTION = "RSK82 ETF Risk Data (8 ETF ownership / flow vector fields), USA/D1/TOP3000"

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
    "rsk82_znorm_m1d_tni_su_fte": "1m delta in ownership as a percent of market-cap by US-listed ETFs (vector)",
    "rsk82_znorm_m1d_tni_p_su_fte": "1m delta in ownership as a percent of market-cap by US-listed passive ETFs (vector)",
    "rsk82_znorm_w1d_tni_su_fte": "1w delta in ownership as a percent of market-cap by US-listed ETFs (vector)",
    "rsk82_znorm_m3d_tni_su_fte": "3m delta in ownership as a percent of market-cap by US-listed ETFs (vector)",
    "rsk82_znorm_m3g_tni_p_su_fte": "3m growth in ownership as a percent of market-cap by US-listed passive ETFs (vector)",
    "rsk82_znorm_tni_p_su_fte": "Ownership as a percent of market-cap by passive US-listed equity ETFs (vector)",
    "rsk82_znorm_etf_us_lev_g1w": "Growth in market value held in aggregate by US-listed ETFs (vector)",
    "rsk82_znorm_etf_us_lev_d2w": "2w delta in market value held in aggregate by US-listed ETFs (vector)",
}

MAX_RAW_FIELDS = 3
MAX_OPERATORS = 8

ALLOWED_OPERATORS = [
    "abs", "add", "densify", "divide", "inverse", "log", "max", "min",
    "multiply", "power", "reverse", "sigmoid", "sign", "signed_power", "sqrt",
    "subtract", "tanh",
    "and", "if_else", "is_nan", "not", "or",
    "days_from_last_change", "hump", "kth_element", "last_diff_value",
    "ts_arg_max", "ts_arg_min", "ts_av_diff", "ts_backfill", "ts_corr",
    "ts_count_nans", "ts_covariance", "ts_decay_linear", "ts_delay", "ts_delta",
    "ts_entropy", "ts_max", "ts_mean", "ts_min", "ts_min_diff",
    "ts_min_max_cps", "ts_min_max_diff", "ts_product", "ts_quantile", "ts_rank",
    "ts_regression", "ts_scale", "ts_skewness", "ts_std_dev",
    "ts_step", "ts_sum", "ts_target_tvr_decay", "ts_zscore",
    "normalize", "quantile", "rank", "regression_proj", "scale",
    "vector_neut", "vector_proj", "winsorize", "zscore",
    "vec_avg", "vec_sum",
    "bucket", "trade_when",
    "group_backfill", "group_cartesian_product", "group_extra", "group_mean",
    "group_neutralize", "group_rank", "group_scale", "group_zscore",
    "inst_pnl",
]

GENIUS_OPERATORS = [
    "sigmoid", "tanh", "ts_entropy", "ts_min_diff", "ts_min_max_cps",
    "ts_min_max_diff", "ts_skewness", "ts_target_tvr_decay",
    "regression_proj", "vector_neut", "vector_proj",
    "group_cartesian_product", "group_extra", "inst_pnl",
]

_FIELD_NAMES = list(FIELDS.keys())
m1d, m1d_p, w1d, m3d, m3g_p, own_p, lev_g1w, lev_d2w = _FIELD_NAMES

GROUPS = ["industry", "subindustry"]


def V(f):
    """Collapse a vector field to one value per instrument per day."""
    return f"vec_avg({f})"


def _Z(x):
    return f"zscore({V(x)})"


def _spread(a, b):
    return f"subtract({_Z(a)},{_Z(b)})"


def _blend(a, b):
    return f"add({_Z(a)},{_Z(b)})"


def _generate_candidates():
    """Every candidate expression this pack knows how to build, tagged by idea family."""
    candidates: dict[str, str] = {}

    def add(expr, tag):
        candidates.setdefault(expr.strip(), tag)

    short_w = [5, 10, 20]
    medium_w = [40, 60, 120]
    long_w = [180, 252]
    all_w = short_w + medium_w + long_w
    pair_w = [10, 20, 60, 120, 252]

    fields = _FIELD_NAMES
    pairs = list(combinations(fields, 2))
    ordered_pairs = list(permutations(fields, 2))
    triples = list(combinations(fields, 3))

    # 1. single-field level
    for f in fields:
        v = V(f)
        add(f"rank({v})", "level")
        add(f"-rank({v})", "level")
        add(f"zscore({v})", "level")
        add(f"-zscore({v})", "level")
        add(f"normalize({v},useStd=true)", "level")
        add(f"rank(winsorize({v},std=4))", "level")
        add(f'rank(quantile({v},driver="gaussian"))', "level")
        add(f"rank(abs(zscore({v})))", "level")
        add(f"rank(signed_power({v},0.5))", "level")
        add(f"rank(sigmoid(zscore({v})))", "level")

    # 2. coverage / staleness (vector fields: collapse first, then backfill)
    for f in fields:
        v = V(f)
        for d in [5, 20, 60, 120]:
            add(f"rank(ts_backfill({v},{d}))", "backfill")
            add(f"-rank(ts_backfill({v},{d}))", "backfill")
        for d in [60, 120]:
            add(f"rank(ts_count_nans({v},{d}))", "coverage")
            add(f"-rank(ts_count_nans({v},{d}))", "coverage")
        add(f"rank(days_from_last_change({v}))", "staleness")
        add(f"-rank(days_from_last_change({v}))", "staleness")
        add(f"rank(subtract({v},last_diff_value({v},20)))", "staleness")
        add(f"rank(subtract({v},last_diff_value({v},60)))", "staleness")

    # 3. single-field time-series level / trend
    for f in fields:
        v = V(f)
        for d in all_w:
            add(f"rank(ts_mean({v},{d}))", "ts_mean")
            add(f"-rank(ts_mean({v},{d}))", "ts_mean")
            add(f"rank(ts_sum({v},{d}))", "ts_sum")
            add(f"rank(ts_delta({v},{d}))", "ts_delta")
            add(f"-rank(ts_delta({v},{d}))", "ts_delta")
            add(f"rank(ts_rank({v},{d}))", "ts_rank")
            add(f"-rank(ts_rank({v},{d}))", "ts_rank")
            add(f"rank(ts_zscore({v},{d}))", "ts_zscore")
            add(f"-rank(ts_zscore({v},{d}))", "ts_zscore")
            add(f"rank(ts_av_diff({v},{d}))", "ts_av_diff")
            add(f"-rank(ts_av_diff({v},{d}))", "ts_av_diff")
            add(f"rank(ts_scale({v},{d}))", "ts_scale")
            add(f"rank(ts_decay_linear({v},{d}))", "ts_decay")
            add(f"rank(ts_std_dev({v},{d}))", "ts_std")
            add(f"-rank(ts_std_dev({v},{d}))", "ts_std")

    # 4. single-field time-series shape
    for f in fields:
        v = V(f)
        for d in [20, 60, 120, 252]:
            add(f"rank(ts_min_max_diff({v},{d}))", "ts_shape")
            add(f"rank(ts_min_diff({v},{d}))", "ts_shape")
            add(f"rank(ts_arg_max({v},{d}))", "ts_shape")
            add(f"rank(ts_arg_min({v},{d}))", "ts_shape")
            add(f"-rank(ts_arg_max({v},{d}))", "ts_shape")
            add(f"rank(ts_quantile({v},{d}))", "ts_shape")
            add(f"rank(ts_skewness({v},{d}))", "ts_shape")
            add(f"rank(ts_entropy({v},{d}))", "ts_shape")

    # 5. scale-free growth
    for f in fields:
        v = V(f)
        for d in [5, 20, 60, 120, 252]:
            add(f"rank(divide(ts_delta({v},{d}),abs(ts_mean({v},{d}))))", "growth")
            add(f"-rank(divide(ts_delta({v},{d}),abs(ts_mean({v},{d}))))", "growth")
            add(f"rank(divide(ts_delta({v},{d}),ts_std_dev({v},{d})))", "growth")
            add(f"rank(divide({v},ts_mean({v},{d})))", "vs_own_mean")
            add(f"-rank(divide({v},ts_mean({v},{d})))", "vs_own_mean")
            add(f"rank(subtract(ts_mean({v},{max(d // 2, 2)}),ts_mean({v},{d})))", "mean_cross")

    # 6. ETF-flow specific: passive vs all ETFs, flow horizons, ownership level vs flow
    flow_pairs = [
        (m1d_p, m1d),      # passive share of the 1m ownership change
        (w1d, m1d), (m1d, m3d), (w1d, m3d),   # term structure of ownership flow
        (own_p, m3g_p), (own_p, m1d_p),       # passive ownership level vs its flow
        (lev_g1w, lev_d2w),                   # aggregate market value held: growth vs 2w delta
        (m3d, m3g_p), (m1d, lev_d2w),
    ]
    for a, b in flow_pairs:
        add(f"rank({_spread(a, b)})", "flow_spread")
        add(f"-rank({_spread(a, b)})", "flow_spread")
        add(f"rank(multiply({_Z(a)},{_Z(b)}))", "flow_spread")
        add(f"rank(vector_neut({_Z(a)},{_Z(b)}))", "flow_spread")
        for d in [20, 60, 120, 252]:
            add(f"rank(ts_zscore({_spread(a, b)},{d}))", "flow_spread_ts")
            add(f"rank(ts_delta({_spread(a, b)},{d}))", "flow_spread_ts")
            add(f"-rank(ts_mean({_spread(a, b)},{d}))", "flow_spread_ts")
            add(f"rank(ts_corr({V(a)},{V(b)},{d}))", "flow_spread_ts")

    # 7. cross-model static relationships (pairs)
    for a, b in pairs:
        add(f"rank(add(rank({V(a)}),rank({V(b)})))", "pair_static")
        add(f"rank(multiply(rank({V(a)}),rank({V(b)})))", "pair_static")
        add(f"rank({_blend(a, b)})", "pair_static")
        add(f"rank(multiply({_Z(a)},{_Z(b)}))", "pair_static")
        add(f"rank(abs({_spread(a, b)}))", "pair_static")
        add(f"rank(min({_Z(a)},{_Z(b)}))", "pair_minmax")
        add(f"rank(max({_Z(a)},{_Z(b)}))", "pair_minmax")
    for a, b in ordered_pairs:
        add(f"rank(subtract(rank({V(a)}),rank({V(b)})))", "pair_spread")
        add(f"rank({_spread(a, b)})", "pair_spread")

    # 8. consensus regimes
    for a, b in pairs:
        add(
            f"if_else(and({_Z(a)}>0.5,{_Z(b)}>0.5),1,"
            f"if_else(and({_Z(a)}<-0.5,{_Z(b)}<-0.5),-1,0))",
            "consensus",
        )

    # 9. triple composites
    for a, b, c in triples:
        add(f"rank(add({_Z(a)},{_Z(b)},{_Z(c)}))", "triple")
        add(f"rank(min({_Z(a)},{_Z(b)},{_Z(c)}))", "triple")
        add(f"rank(max({_Z(a)},{_Z(b)},{_Z(c)}))", "triple")
        add(f"rank(subtract({_blend(a, b)},{_Z(c)}))", "triple")

    # 10. pair-spread / blend time-series
    for a, b in pairs:
        s_ab = _spread(a, b)
        b_ab = _blend(a, b)
        for d in pair_w:
            add(f"rank(ts_mean({s_ab},{d}))", "spread_ts")
            add(f"rank(ts_delta({s_ab},{d}))", "spread_ts")
            add(f"-rank(ts_delta({s_ab},{d}))", "spread_ts")
            add(f"rank(ts_zscore({s_ab},{d}))", "spread_ts")
            add(f"-rank(ts_zscore({s_ab},{d}))", "spread_ts")
            add(f"rank(ts_rank({s_ab},{d}))", "spread_ts")
        for d in [10, 20, 60, 120]:
            add(f"rank(ts_zscore({b_ab},{d}))", "blend_ts")
            add(f"rank(ts_delta({b_ab},{d}))", "blend_ts")
            add(f"rank(ts_rank({b_ab},{d}))", "blend_ts")

    # 11. cross-field correlation / covariance
    for a, b in pairs:
        for d in [20, 60, 120, 252]:
            add(f"rank(ts_corr({V(a)},{V(b)},{d}))", "ts_corr")
            add(f"-rank(ts_corr({V(a)},{V(b)},{d}))", "ts_corr")
            add(f"rank(ts_covariance({V(a)},{V(b)},{d}))", "ts_cov")
            add(f"-rank(ts_covariance({V(a)},{V(b)},{d}))", "ts_cov")

    # 12. cross-field time-series regression
    for y, x in ordered_pairs:
        for d in [60, 120, 252]:
            add(f"rank(ts_regression({V(y)},{V(x)},{d},lag=0,rettype=0))", "ts_reg_resid")
            add(f"rank(ts_regression({V(y)},{V(x)},{d},lag=0,rettype=2))", "ts_reg_slope")

    # 13. orthogonalisation (Genius)
    for y, x in ordered_pairs:
        add(f"rank(vector_neut({_Z(y)},{_Z(x)}))", "neut")
        add(f"rank(subtract({_Z(y)},regression_proj({_Z(y)},{_Z(x)})))", "neut")
        for d in [20, 60]:
            add(f"rank(ts_zscore(vector_neut({_Z(y)},{_Z(x)}),{d}))", "neut_ts")

    # 14. group-relative signals
    for f in fields:
        v = V(f)
        for g in GROUPS:
            add(f"group_rank(rank({v}),{g})", "group_level")
            add(f"group_neutralize(rank({v}),{g})", "group_level")
            add(f"group_zscore(zscore({v}),{g})", "group_level")
            add(f"group_scale(rank({v}),{g})", "group_level")
            for d in [20, 60, 120]:
                add(f"group_rank(rank(ts_mean({v},{d})),{g})", "group_ts")
                add(f"group_neutralize(rank(ts_delta({v},{d})),{g})", "group_ts")
                add(f"group_zscore(ts_zscore({v},{d}),{g})", "group_ts")
                add(f"group_scale(rank(ts_rank({v},{d})),{g})", "group_ts")
            add(f"rank(group_backfill({v},{g},60))", "group_backfill")

    # 15. group-relative field spreads
    for a, b in pairs:
        s_ab = _spread(a, b)
        for g in GROUPS:
            add(f"group_rank(rank({s_ab}),{g})", "group_spread")
            add(f"group_neutralize(rank({s_ab}),{g})", "group_spread")
            add(f"group_zscore({s_ab},{g})", "group_spread")

    # 16. group-bucket templates
    for bucket_field, target_field in ordered_pairs:
        bg = f'bucket(rank({V(bucket_field)}),range="0, 1, 0.1")'
        add(f"group_rank(rank({V(target_field)}),{bg})", "bucket")
        add(f"group_neutralize(rank({V(target_field)}),{bg})", "bucket")
        add(f"group_zscore({_Z(target_field)},{bg})", "bucket")

    # 17. hump / turnover control
    for f in fields:
        v = V(f)
        add(f"hump(rank(ts_rank({v},20)),hump=0.01)", "hump")
        add(f"hump(rank(ts_zscore({v},40)),hump=0.01)", "hump")
        add(f"hump(rank(ts_delta({v},20)),hump=0.01)", "hump")
    for a, b in pairs:
        add(f"hump(rank(ts_zscore({_spread(a, b)},60)),hump=0.01)", "hump")

    # 18. trade_when (fresh data / extreme readings)
    for f in fields:
        v = V(f)
        add(f"trade_when(days_from_last_change({v})<=5,rank({v}),-1)", "trade_when")
        add(f"trade_when(abs(ts_zscore({v},60))>1,rank({v}),-1)", "trade_when")
        add(f"trade_when(ts_rank({v},60)>0.7,rank({v}),ts_rank({v},60)<0.3)", "trade_when")
        add(f"trade_when(ts_zscore({v},20)>1,rank(ts_delta({v},5)),-1)", "trade_when")
    for a, b in ordered_pairs:
        add(f"trade_when(days_from_last_change({V(a)})<=5,rank({_spread(a, b)}),-1)", "trade_when")

    # 19. decayed / smoothed signals
    for f in fields:
        v = V(f)
        for d in [10, 20, 40, 60]:
            add(f"rank(ts_decay_linear(ts_zscore({v},{d}),20))", "decay_combo")
            add(f"rank(ts_decay_linear(ts_rank({v},{d}),20))", "decay_combo")
            add(f"rank(ts_decay_linear(ts_delta({v},{d}),20))", "decay_combo")

    # 20. level x momentum
    for f in fields:
        v = V(f)
        for d in [5, 20, 60, 120]:
            add(f"rank(multiply(rank({v}),rank(ts_delta({v},{d}))))", "level_x_mom")
            add(f"rank(subtract(rank({v}),rank(ts_delta({v},{d}))))", "level_x_mom")
            add(f"rank(add(rank({v}),rank(ts_rank({v},{d}))))", "level_x_mom")

    # 21. cross-field momentum
    for a, b in ordered_pairs:
        for d in [20, 60]:
            add(f"rank(multiply(rank({V(a)}),rank(ts_delta({V(b)},{d}))))", "cross_mom")
            add(f"rank(subtract(ts_zscore({V(a)},{d}),ts_zscore({V(b)},{d})))", "cross_mom")

    return candidates


def _validate_local(expr: str) -> bool:
    """Cheap offline filter mirroring the pack's own limits."""
    # every called function must be a known operator
    if any(n not in ALLOWED_OPERATORS for n in re.findall(r"\b([A-Za-z_][A-Za-z_0-9]*)\s*\(", expr)):
        return False
    used = {f for f in FIELDS if re.search(rf"\b{re.escape(f)}\b", expr)}
    if not used or len(used) > MAX_RAW_FIELDS:
        return False
    # vector fields must always be collapsed: count raw occurrences vs. wrapped occurrences
    for f in used:
        raw = len(re.findall(rf"\b{re.escape(f)}\b", expr))
        wrapped = len(re.findall(rf"vec_(?:avg|sum)\({re.escape(f)}\)", expr))
        if raw != wrapped:
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
            f"rsk82_usa pack only has {len(all_candidates)} valid candidates, "
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
