"""
alphapilot pack: MDL262 "DNN prediction of fundamentals" · USA / D1 / TOP3000

Dataset notes (from the Data Explorer screenshot):
  * All fields are MATRIX type (one value per instrument per day) -> no vec_* wrapping.
  * Coverage 73-100%, date coverage 100%, so backfill / staleness ideas are included.
  * Fields mix unit-free ratios (earnings yield, earnings/cap, profitability) with
    currency-level predictions (predicted long-term debt, predicted pretax income), so
    level-based signals lean on rank / ts_zscore / ratios rather than raw magnitudes.
  * Pyramid theme multiplier 1.3.

Settings follow the BRAIN simulation-settings screenshot: Fast Expression, Equity,
USA / delay 1 / TOP3000, Sector neutralization, decay 4, truncation 0.08, pasteurization ON,
unit handling VERIFY, NaN handling ON, test period 0Y0M, max trade OFF.

Limits mirrored from the other packs: <= 3 raw fields and <= 8 operators per expression,
and every called function must be in ALLOWED_OPERATORS.
"""
from __future__ import annotations

import random
import re
from itertools import combinations, permutations

PACK_NAME = "mdl262_usa"
PACK_DESCRIPTION = "MDL262 DNN prediction of fundamentals (8 predictive-model fields), USA/D1/TOP3000"

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
    "mdl262_earnings_yield1": "Earnings Yield of Predictive models (variant 1)",
    "mdl262_earnings_yield2": "Earnings Yield of Predictive models (variant 2)",
    "mdl262_earnings_yield3": "Earnings Yield of Predictive models (variant 3)",
    "mdl262_earnings_cap2": "Earnings to cap ratio of Predictive models",
    "mdl262_rasv2splitprofitabilityebitd_q_profitability3": "3rd profitability field of Earnings before Interest, Tax and Depreciation",
    "mdl262_aacr_trkdpitdeltapredict_funda_mada": "Mean Absolute Deviation of scaled actual value of Accounts Receivable",
    "mdl262_compustatpredictivedlttq_prediction": "Market-implied predicted Long-term Debt (DLTTQ, quarterly) with 1-day delay",
    "mdl262_piq_compustatdeltapredict_funda_predict": "Market-implied predicted value of Pretax Income (Compustat PIQ) as of close (D0)",
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
ey1, ey2, ey3, ecap, prof3, mada, dltt, piq = _FIELD_NAMES
YIELDS = [ey1, ey2, ey3]
GROUPS = ["industry", "subindustry"]


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

    all_w = [5, 10, 20, 40, 60, 120, 180, 252]
    pair_w = [10, 20, 60, 120, 252]

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
        add(f"normalize({f},useStd=true)", "level")
        add(f"rank(winsorize({f},std=4))", "level")
        add(f'rank(quantile({f},driver="gaussian"))', "level")
        add(f"rank(abs(zscore({f})))", "level")
        add(f"rank(signed_power({f},0.5))", "level")
        add(f"rank(sigmoid(zscore({f})))", "level")

    # 2. coverage / staleness
    for f in fields:
        for d in [5, 20, 60, 120]:
            add(f"rank(ts_backfill({f},{d}))", "backfill")
            add(f"-rank(ts_backfill({f},{d}))", "backfill")
        for d in [60, 120]:
            add(f"rank(ts_count_nans({f},{d}))", "coverage")
            add(f"-rank(ts_count_nans({f},{d}))", "coverage")
        add(f"rank(days_from_last_change({f}))", "staleness")
        add(f"-rank(days_from_last_change({f}))", "staleness")
        add(f"rank(subtract({f},last_diff_value({f},20)))", "staleness")
        add(f"rank(subtract({f},last_diff_value({f},60)))", "staleness")

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

    # 5. scale-free growth (important for the currency-level prediction fields)
    for f in fields:
        for d in [5, 20, 60, 120, 252]:
            add(f"rank(divide(ts_delta({f},{d}),abs(ts_mean({f},{d}))))", "growth")
            add(f"-rank(divide(ts_delta({f},{d}),abs(ts_mean({f},{d}))))", "growth")
            add(f"rank(divide(ts_delta({f},{d}),ts_std_dev({f},{d})))", "growth")
            add(f"rank(divide({f},ts_mean({f},{d})))", "vs_own_mean")
            add(f"-rank(divide({f},ts_mean({f},{d})))", "vs_own_mean")
            add(f"rank(subtract(ts_mean({f},{max(d // 2, 2)}),ts_mean({f},{d})))", "mean_cross")

    # 6. earnings-yield ensemble (three variants of the same idea)
    y12, y13, y23 = (ey1, ey2), (ey1, ey3), (ey2, ey3)
    add(f"rank(add({_Z(ey1)},{_Z(ey2)},{_Z(ey3)}))", "yield_ens")
    add(f"rank(min({_Z(ey1)},{_Z(ey2)},{_Z(ey3)}))", "yield_ens")
    add(f"rank(max({_Z(ey1)},{_Z(ey2)},{_Z(ey3)}))", "yield_ens")
    for d in [20, 60, 120, 252]:
        add(f"rank(ts_zscore(add({_Z(ey1)},{_Z(ey2)},{_Z(ey3)}),{d}))", "yield_ens")
        add(f"rank(ts_delta(add({_Z(ey1)},{_Z(ey2)},{_Z(ey3)}),{d}))", "yield_ens")
        add(f"rank(ts_rank(add({_Z(ey1)},{_Z(ey2)},{_Z(ey3)}),{d}))", "yield_ens")
    for a, b in (y12, y13, y23):
        add(f"rank(abs({_spread(a, b)}))", "yield_disagree")
        add(f"-rank(abs({_spread(a, b)}))", "yield_disagree")
        add(f"rank(multiply({_Z(a)},{_Z(b)}))", "yield_disagree")

    # 7. cross-field ratios (unit-free: predicted income vs predicted debt, etc.)
    for a, b in ordered_pairs:
        add(f"rank(divide({a},abs({b})))", "ratio")
        for d in [60, 120, 252]:
            add(f"rank(ts_zscore(divide({a},abs({b})),{d}))", "ratio_ts")
            add(f"rank(ts_delta(divide({a},abs({b})),{d}))", "ratio_ts")

    # 8. cross-field static relationships (pairs)
    for a, b in pairs:
        add(f"rank(add(rank({a}),rank({b})))", "pair_static")
        add(f"rank(multiply(rank({a}),rank({b})))", "pair_static")
        add(f"rank({_blend(a, b)})", "pair_static")
        add(f"rank(multiply({_Z(a)},{_Z(b)}))", "pair_static")
        add(f"rank(abs({_spread(a, b)}))", "pair_static")
        add(f"rank(min({_Z(a)},{_Z(b)}))", "pair_minmax")
        add(f"rank(max({_Z(a)},{_Z(b)}))", "pair_minmax")
    for a, b in ordered_pairs:
        add(f"rank(subtract(rank({a}),rank({b})))", "pair_spread")
        add(f"rank({_spread(a, b)})", "pair_spread")

    # 9. consensus regimes
    for a, b in pairs:
        add(
            f"if_else(and({_Z(a)}>0.5,{_Z(b)}>0.5),1,"
            f"if_else(and({_Z(a)}<-0.5,{_Z(b)}<-0.5),-1,0))",
            "consensus",
        )

    # 10. triple composites
    for a, b, c in triples:
        add(f"rank(add({_Z(a)},{_Z(b)},{_Z(c)}))", "triple")
        add(f"rank(min({_Z(a)},{_Z(b)},{_Z(c)}))", "triple")
        add(f"rank(max({_Z(a)},{_Z(b)},{_Z(c)}))", "triple")
        add(f"rank(subtract({_blend(a, b)},{_Z(c)}))", "triple")
        for d in [60, 120]:
            add(f"rank(ts_zscore(add({_Z(a)},{_Z(b)},{_Z(c)}),{d}))", "triple_ts")

    # 11. pair-spread / blend time-series
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

    # 12. cross-field correlation / covariance
    for a, b in pairs:
        for d in [20, 60, 120, 252]:
            add(f"rank(ts_corr({a},{b},{d}))", "ts_corr")
            add(f"-rank(ts_corr({a},{b},{d}))", "ts_corr")
            add(f"rank(ts_covariance({a},{b},{d}))", "ts_cov")
            add(f"-rank(ts_covariance({a},{b},{d}))", "ts_cov")

    # 13. cross-field time-series regression
    for y, x in ordered_pairs:
        for d in [60, 120, 252]:
            add(f"rank(ts_regression({y},{x},{d},lag=0,rettype=0))", "ts_reg_resid")
            add(f"rank(ts_regression({y},{x},{d},lag=0,rettype=2))", "ts_reg_slope")

    # 14. orthogonalisation (Genius)
    for y, x in ordered_pairs:
        add(f"rank(vector_neut({_Z(y)},{_Z(x)}))", "neut")
        add(f"rank(subtract({_Z(y)},regression_proj({_Z(y)},{_Z(x)})))", "neut")
        for d in [20, 60]:
            add(f"rank(ts_zscore(vector_neut({_Z(y)},{_Z(x)}),{d}))", "neut_ts")

    # 15. group-relative signals
    for f in fields:
        for g in GROUPS:
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

    # 16. group-relative field spreads
    for a, b in pairs:
        s_ab = _spread(a, b)
        for g in GROUPS:
            add(f"group_rank(rank({s_ab}),{g})", "group_spread")
            add(f"group_neutralize(rank({s_ab}),{g})", "group_spread")
            add(f"group_zscore({s_ab},{g})", "group_spread")

    # 17. group-bucket templates
    for bucket_field, target_field in ordered_pairs:
        bg = f'bucket(rank({bucket_field}),range="0, 1, 0.1")'
        add(f"group_rank(rank({target_field}),{bg})", "bucket")
        add(f"group_neutralize(rank({target_field}),{bg})", "bucket")
        add(f"group_zscore(zscore({target_field}),{bg})", "bucket")

    # 18. hump / turnover control
    for f in fields:
        add(f"hump(rank(ts_rank({f},20)),hump=0.01)", "hump")
        add(f"hump(rank(ts_zscore({f},40)),hump=0.01)", "hump")
        add(f"hump(rank(ts_delta({f},20)),hump=0.01)", "hump")
    for a, b in pairs:
        add(f"hump(rank(ts_zscore({_spread(a, b)},60)),hump=0.01)", "hump")

    # 19. trade_when
    for f in fields:
        add(f"trade_when(days_from_last_change({f})<=5,rank({f}),-1)", "trade_when")
        add(f"trade_when(abs(ts_zscore({f},60))>1,rank({f}),-1)", "trade_when")
        add(f"trade_when(ts_rank({f},60)>0.7,rank({f}),ts_rank({f},60)<0.3)", "trade_when")
        add(f"trade_when(ts_zscore({f},20)>1,rank(ts_delta({f},5)),-1)", "trade_when")
    for a, b in ordered_pairs:
        add(f"trade_when(days_from_last_change({a})<=5,rank({_spread(a, b)}),-1)", "trade_when")

    # 20. decayed / smoothed signals
    for f in fields:
        for d in [10, 20, 40, 60]:
            add(f"rank(ts_decay_linear(ts_zscore({f},{d}),20))", "decay_combo")
            add(f"rank(ts_decay_linear(ts_rank({f},{d}),20))", "decay_combo")
            add(f"rank(ts_decay_linear(ts_delta({f},{d}),20))", "decay_combo")

    # 21. level x momentum
    for f in fields:
        for d in [5, 20, 60, 120]:
            add(f"rank(multiply(rank({f}),rank(ts_delta({f},{d}))))", "level_x_mom")
            add(f"rank(subtract(rank({f}),rank(ts_delta({f},{d}))))", "level_x_mom")
            add(f"rank(add(rank({f}),rank(ts_rank({f},{d}))))", "level_x_mom")

    # 22. cross-field momentum
    for a, b in ordered_pairs:
        for d in [20, 60]:
            add(f"rank(multiply(rank({a}),rank(ts_delta({b},{d}))))", "cross_mom")
            add(f"rank(subtract(ts_zscore({a},{d}),ts_zscore({b},{d})))", "cross_mom")

    return candidates


def _validate_local(expr: str) -> bool:
    """Cheap offline filter mirroring the pack's own limits."""
    if any(n not in ALLOWED_OPERATORS for n in re.findall(r"\b([A-Za-z_][A-Za-z_0-9]*)\s*\(", expr)):
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
            f"mdl262_usa pack only has {len(all_candidates)} valid candidates, "
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
