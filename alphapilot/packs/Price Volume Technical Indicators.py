"""
alphapilot pack: Price Volume Technical Indicators · USA / D1 / TOP3000

This is a dataset pack for alphapilot. It was produced the way every pack is
meant to be produced: hand Claude the Data Explorer screenshot for the dataset,
the operator list your account has, and the simulation settings screenshot,
and ask it to write one of these files.

Nothing outside this file is dataset-specific - the CLI, the BRAIN client,
the LLM description writer and the submission logic are all generic and
never need to change when you add a new dataset.
"""
from __future__ import annotations

import random
import re
from itertools import combinations, permutations

PACK_NAME = "pvti_usa"
PACK_DESCRIPTION = "Price Volume Technical Indicators (9 price momentum/acceleration/change indicators), USA/D1/TOP3000"

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
    "momentum_shift_indicator": "An indicator for shifts in price momentum.",
    "momentum_strength_index": "An index measuring the strength of recent price momentum.",
    "price_acceleration_factor": "A factor quantifying the acceleration of price changes.",
    "price_acceleration_index": "An index measuring the acceleration of price changes.",
    "price_acceleration_score": "A score measuring the acceleration of price changes.",
    "price_change_index": "An index measuring the magnitude of price changes.",
    "price_change_indicator": "An indicator for significant changes in price.",
    "price_change_intensity": "An intensity score for recent price changes.",
    "price_change_score": "A score measuring the magnitude of price changes.",
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
    "ts_regression", "ts_returns", "ts_scale", "ts_skewness", "ts_std_dev",
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
(
    mom_shift, mom_strength,
    acc_factor, acc_index, acc_score,
    chg_index, chg_indicator, chg_intensity, chg_score,
) = _FIELD_NAMES


def _Z(x):
    return f"zscore({x})"


def _spread(a, b):
    return f"subtract(zscore({a}),zscore({b}))"


def _blend(a, b):
    return f"add(zscore({a}),zscore({b}))"


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
    reg_w = [60, 120, 252]

    fields = _FIELD_NAMES
    pairs = list(combinations(fields, 2))
    ordered_pairs = list(permutations(fields, 2))
    triples = list(combinations(fields, 3))

    # 1. single-field level
    for f in fields:
        add(f"rank({f})", "level")
        add(f"-rank({f})", "level")
        add(f"zscore({f})", "level")
        add(f"-zscore({f})", "level")
        add(f"normalize({f})", "level")
        add(f"-normalize({f})", "level")
        add(f"normalize({f},useStd=true)", "level")
        add(f"rank(winsorize({f},std=4))", "level")
        add(f'rank(quantile({f},driver="gaussian"))', "level")
        add(f"rank(abs(zscore({f})))", "level")
        add(f"-rank(abs(zscore({f})))", "level")

    # 2. coverage / staleness
    for f in fields:
        for d in [20, 60, 120]:
            add(f"rank(ts_backfill({f},{d}))", "backfill")
            add(f"-rank(ts_backfill({f},{d}))", "backfill")
        add(f"rank(days_from_last_change({f}))", "staleness")
        add(f"-rank(days_from_last_change({f}))", "staleness")
        add(f"rank(last_diff_value({f},60))", "staleness")
        add(f"rank(subtract({f},last_diff_value({f},60)))", "staleness")
        add(f"rank(subtract({f},last_diff_value({f},120)))", "staleness")

    # 3. single-field time-series level / trend
    for f in fields:
        for d in all_w:
            add(f"rank(ts_mean({f},{d}))", "ts_mean")
            add(f"-rank(ts_mean({f},{d}))", "ts_mean")
            add(f"rank(ts_delta({f},{d}))", "ts_delta")
            add(f"-rank(ts_delta({f},{d}))", "ts_delta")
            add(f"rank(ts_rank({f},{d}))", "ts_rank")
            add(f"-rank(ts_rank({f},{d}))", "ts_rank")
            add(f"rank(ts_zscore({f},{d}))", "ts_zscore")
            add(f"-rank(ts_zscore({f},{d}))", "ts_zscore")
            add(f"rank(ts_av_diff({f},{d}))", "ts_av_diff")
            add(f"-rank(ts_av_diff({f},{d}))", "ts_av_diff")
            add(f"rank(ts_scale({f},{d}))", "ts_scale")
            add(f"rank(ts_decay_linear({f},{d}))", "ts_decay")
            add(f"rank(ts_std_dev({f},{d}))", "ts_std")
            add(f"-rank(ts_std_dev({f},{d}))", "ts_std")

    # 4. single-field time-series shape
    for f in fields:
        for d in [20, 60, 120, 252]:
            add(f"rank(ts_min_max_diff({f},{d}))", "ts_shape")
            add(f"rank(ts_min_diff({f},{d}))", "ts_shape")
            add(f"rank(ts_arg_max({f},{d}))", "ts_shape")
            add(f"rank(ts_arg_min({f},{d}))", "ts_shape")
            add(f"-rank(ts_arg_max({f},{d}))", "ts_shape")
            add(f"rank(ts_quantile({f},{d}))", "ts_shape")
            add(f"rank(ts_skewness({f},{d}))", "ts_shape")
            add(f"rank(ts_entropy({f},{d}))", "ts_shape")

    # 5. cross-indicator static relationships (pairs)
    for a, b in pairs:
        add(f"rank(add(rank({a}),rank({b})))", "pair_static")
        add(f"rank(multiply(rank({a}),rank({b})))", "pair_static")
        add(f"rank({_blend(a, b)})", "pair_static")
        add(f"rank(multiply(zscore({a}),zscore({b})))", "pair_static")
        add(f"rank(abs({_spread(a, b)}))", "pair_static")
        add(f"-rank(abs({_spread(a, b)}))", "pair_static")
        add(f"rank(min(zscore({a}),zscore({b})))", "pair_minmax")
        add(f"rank(max(zscore({a}),zscore({b})))", "pair_minmax")

    for a, b in ordered_pairs:
        add(f"rank(subtract(rank({a}),rank({b})))", "pair_spread")
        add(f"rank({_spread(a, b)})", "pair_spread")

    # 6. consensus / disagreement regimes
    for a, b in pairs:
        add(
            f"if_else(and(zscore({a})>0.5,zscore({b})>0.5),1,"
            f"if_else(and(zscore({a})<-0.5,zscore({b})<-0.5),-1,0))",
            "consensus",
        )

    # 7. triple-indicator composites
    for a, b, c in triples:
        add(f"rank(add(zscore({a}),zscore({b}),zscore({c})))", "triple")
        add(f"rank(min(zscore({a}),zscore({b}),zscore({c})))", "triple")
        add(f"rank(max(zscore({a}),zscore({b}),zscore({c})))", "triple")
        add(f"rank(subtract({_blend(a, b)},zscore({c})))", "triple")
        add(f"rank(subtract({_blend(a, c)},zscore({b})))", "triple")
        add(f"rank(subtract({_blend(b, c)},zscore({a})))", "triple")
        for d in [20, 60, 120]:
            add(f"rank(ts_zscore(add(zscore({a}),zscore({b}),zscore({c})),{d}))", "triple_ts")
        add(f"rank(ts_delta(add(zscore({a}),zscore({b}),zscore({c})),20))", "triple_ts")
        add(f"rank(ts_decay_linear(add(zscore({a}),zscore({b}),zscore({c})),20))", "triple_ts")

    # 8. pair-spread / pair-blend time-series
    for a, b in pairs:
        s_ab = _spread(a, b)
        for d in pair_w:
            add(f"rank(ts_mean({s_ab},{d}))", "spread_ts")
            add(f"rank(ts_delta({s_ab},{d}))", "spread_ts")
            add(f"-rank(ts_delta({s_ab},{d}))", "spread_ts")
            add(f"rank(ts_zscore({s_ab},{d}))", "spread_ts")
            add(f"-rank(ts_zscore({s_ab},{d}))", "spread_ts")
            add(f"rank(ts_rank({s_ab},{d}))", "spread_ts")
            add(f"rank(ts_decay_linear({s_ab},{d}))", "spread_ts")
        b_ab = _blend(a, b)
        for d in [10, 20, 60, 120]:
            add(f"rank(ts_zscore({b_ab},{d}))", "blend_ts")
            add(f"rank(ts_delta({b_ab},{d}))", "blend_ts")
            add(f"rank(ts_rank({b_ab},{d}))", "blend_ts")

    # 9. cross-indicator correlation / covariance
    for a, b in pairs:
        for d in [20, 60, 120, 252]:
            add(f"rank(ts_corr({a},{b},{d}))", "ts_corr")
            add(f"-rank(ts_corr({a},{b},{d}))", "ts_corr")
            add(f"rank(ts_covariance({a},{b},{d}))", "ts_cov")
            add(f"-rank(ts_covariance({a},{b},{d}))", "ts_cov")

    # 10. cross-indicator time-series regression
    for y, x in ordered_pairs:
        for d in reg_w:
            add(f"rank(ts_regression({y},{x},{d},lag=0,rettype=0))", "ts_reg_resid")
            add(f"rank(ts_regression({y},{x},{d},lag=0,rettype=2))", "ts_reg_slope")
    for a, b in pairs:
        for d in [60, 120, 252]:
            add(f"rank(ts_regression({a},{b},{d},lag=0,rettype=6))", "ts_reg_r2")

    # 11. cross-sectional orthogonalisation (Genius)
    for y, x in ordered_pairs:
        add(f"rank(vector_neut(zscore({y}),zscore({x})))", "neut")
        add(f"rank(subtract(zscore({y}),regression_proj(zscore({y}),zscore({x}))))", "neut")
    for y, x in ordered_pairs:
        for d in [20, 60]:
            add(f"rank(ts_zscore(vector_neut(zscore({y}),zscore({x})),{d}))", "neut_ts")

    # 12. group-relative signals
    group_names = ["industry", "subindustry"]
    for f in fields:
        for g in group_names:
            add(f"group_rank(rank({f}),{g})", "group_level")
            add(f"group_neutralize(rank({f}),{g})", "group_level")
            add(f"group_zscore(zscore({f}),{g})", "group_level")
            add(f"group_scale(rank({f}),{g})", "group_level")
            for d in [20, 60, 120]:
                add(f"group_rank(rank(ts_mean({f},{d})),{g})", "group_ts")
                add(f"group_neutralize(rank(ts_delta({f},{d})),{g})", "group_ts")
                add(f"group_zscore(ts_zscore({f},{d}),{g})", "group_ts")
                add(f"group_scale(rank(ts_rank({f},{d})),{g})", "group_ts")
            add(f"rank(group_backfill({f},{g},60))", "group_backfill")
            add(f"rank(group_backfill({f},{g},120))", "group_backfill")

    # 13. group-relative indicator spreads
    for a, b in pairs:
        s_ab = _spread(a, b)
        for g in group_names:
            add(f"group_rank(rank({s_ab}),{g})", "group_spread")
            add(f"group_neutralize(rank({s_ab}),{g})", "group_spread")
            add(f"group_zscore({s_ab},{g})", "group_spread")
        add(f"group_rank(rank(ts_zscore({s_ab},60)),industry)", "group_spread")

    # 14. group-bucket templates
    for bucket_field, target_field in ordered_pairs:
        bucket_group = f'bucket(rank({bucket_field}),range="0, 1, 0.1")'
        add(f"group_rank(rank({target_field}),{bucket_group})", "bucket")
        add(f"group_neutralize(rank({target_field}),{bucket_group})", "bucket")
        add(f"group_zscore(zscore({target_field}),{bucket_group})", "bucket")

    # 15. hump / turnover control
    for f in fields:
        add(f"hump(rank(ts_rank({f},20)),hump=0.01)", "hump")
        add(f"hump(rank(ts_zscore({f},40)),hump=0.01)", "hump")
        add(f"hump(rank(ts_delta({f},20)),hump=0.01)", "hump")
    for a, b in pairs:
        add(f"hump(rank(ts_zscore({_spread(a, b)},60)),hump=0.01)", "hump")

    # 16. trade_when
    for f in fields:
        add(f"trade_when(days_from_last_change({f})<=5,rank({f}),-1)", "trade_when")
        add(f"trade_when(abs(ts_zscore({f},60))>1,rank({f}),-1)", "trade_when")
        add(f"trade_when(ts_rank({f},60)>0.7,rank({f}),ts_rank({f},60)<0.3)", "trade_when")
    for a, b in ordered_pairs:
        add(f"trade_when(days_from_last_change({a})<=5,rank({_spread(a, b)}),-1)", "trade_when")

    # 17. decayed / smoothed indicator signals
    for f in fields:
        for d in [10, 20, 40, 60]:
            add(f"rank(ts_decay_linear(ts_zscore({f},{d}),20))", "decay_combo")
            add(f"rank(ts_decay_linear(ts_rank({f},{d}),20))", "decay_combo")
            add(f"rank(ts_decay_linear(ts_delta({f},{d}),20))", "decay_combo")

    # 18. indicator momentum x indicator level
    for f in fields:
        for d in [20, 60, 120]:
            add(f"rank(multiply(rank({f}),rank(ts_delta({f},{d}))))", "level_x_mom")
            add(f"rank(subtract(rank({f}),rank(ts_delta({f},{d}))))", "level_x_mom")
            add(f"rank(add(rank({f}),rank(ts_rank({f},{d}))))", "level_x_mom")

    # 19. cross-indicator momentum
    for a, b in ordered_pairs:
        for d in [20, 60]:
            add(f"rank(multiply(rank({a}),rank(ts_delta({b},{d}))))", "cross_mom")
            add(f"rank(subtract(ts_zscore({a},{d}),ts_zscore({b},{d})))", "cross_mom")

    # 20. stable long-horizon signals
    for f in fields:
        for d in [120, 180, 252]:
            add(f"rank(ts_mean({f},{d}))", "long_horizon")
            add(f"rank(ts_zscore({f},{d}))", "long_horizon")
            add(f"rank(ts_decay_linear({f},{d}))", "long_horizon")
            add(f"rank(ts_av_diff({f},{d}))", "long_horizon")

    return candidates


def _validate_local(expr: str) -> bool:
    """Cheap offline filter mirroring the pack's own limits (kept in sync with packs_api.validate_expression)."""
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
            f"pvti_usa pack only has {len(all_candidates)} valid candidates, "
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