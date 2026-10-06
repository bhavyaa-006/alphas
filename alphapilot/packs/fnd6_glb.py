"""
alphapilot pack: FND6 "Company Fundamental Data for Equity" · GLB / D1 / MINVOL1M

Built for the D1 Power Pool Oct'26 Consultants theme (28 Sep - 11 Oct 2026, 1X multiplier).
Competition rules this pack is written to respect:
  * Delay 1 only.
  * Single data category: every expression uses ONLY fields from the fundamental
    category (fnd6_*). No price-volume fields, no pv1 group fields
    (industry / subindustry / sector / market / ...) - those are only allowed for
    pv1 / price-volume submissions, so grouping here is done with bucket() over the
    dataset's own fields (or the dataset's own currency-code field).
  * Max 3 raw fields and 8 operators per expression (same limits as the reference pack).
  * Operators: only those in wq_brain_operators.md. ts_returns is deliberately excluded
    (and every expression is checked against ALLOWED_OPERATORS, so nothing else sneaks in).

Design goals:
  * Per-field (single-field) alphas dominate the pool: SINGLE_SHARE of every pool is
    single-field, only the remainder is cross-field combos.
  * GLB mixes currencies, so raw levels are not comparable across names. Most per-field
    ideas are therefore scale-free (ts_zscore, ts_rank, growth ratios, divide-by-own-mean)
    or ranked inside buckets / currency groups. Plain level alphas are kept but few.
  * Fields are quarterly, so windows are quarter-aware (60 / 120 / 252 / 504 days)
    and staleness / update-event signals (days_from_last_change, trade_when) are included.
"""
from __future__ import annotations

import random
import re
from itertools import combinations, permutations

PACK_NAME = "fnd6_glb"
PACK_DESCRIPTION = "FND6 Company Fundamental Data (5 quarterly fundamentals), GLB/D1/MINVOL1M"

SETTINGS = {
    "region": "GLB",
    "universe": "MINVOL1M",
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
    "fnd6_int_ibmiiq": "Income before Extraordinary Items and Noncontrolling Interests (quarterly)",
    "fnd6_newqint_ibq": "Income Before Extraordinary Items (quarterly)",
    "fnd6_newqint_piq": "Pretax Income (quarterly)",
    "fnd6_newqint_cheq": "Cash and Short-Term Investments (quarterly)",
    "fnd6_int_accdq": "Accrued Expenses & Deferred Income (quarterly)",
}

# Used ONLY as a group key (rank within currency) so GLB levels become comparable.
# Same dataset, same category. Smoke-test one expression from the "ccy_group" /
# "ccy_bucket" families first; if your account rejects it as a group, set
# CCY_GROUP_ENABLED = False (both families vanish).
CCY_FIELD = "fnd6_idesindqint_curcd"
CCY_GROUP_ENABLED = True
CCY_GROUP = f"densify({CCY_FIELD})"  # densify() is the documented way to compact a sparse grouping field

SINGLE_SHARE = 0.80  # fraction of any pool that is single-field alphas

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
ibmii, ibq, piq, cheq, accd = _FIELD_NAMES

# pv1 / price-volume names that must never appear (single-category rule)
BANNED_TOKENS = {
    "industry", "subindustry", "sector", "market", "country", "exchange", "currency",
    "close", "open", "high", "low", "volume", "vwap", "returns", "cap", "adv20", "adv60",
}

SINGLE_TAGS = set()
COMBO_TAGS = set()


def _Z(x):
    return f"zscore({x})"


def _spread(a, b):
    return f"subtract(zscore({a}),zscore({b}))"


def _blend(a, b):
    return f"add(zscore({a}),zscore({b}))"


def _generate_candidates():
    """Every candidate expression this pack can build, tagged by idea family."""
    candidates: dict[str, str] = {}

    def add(expr, tag, single=True):
        expr = expr.strip()
        if expr not in candidates:
            candidates[expr] = tag
            (SINGLE_TAGS if single else COMBO_TAGS).add(tag)

    # quarterly data -> quarter-aware windows
    q_w = [60, 120, 180, 252, 504]
    s_w = [20, 60, 120]
    fields = _FIELD_NAMES
    pairs = list(combinations(fields, 2))
    ordered_pairs = list(permutations(fields, 2))
    triples = list(combinations(fields, 3))
    ccy = CCY_FIELD

    # ================= SINGLE-FIELD FAMILIES =================
    for f in fields:
        pos_only = f in (cheq, accd)  # balance-sheet items that are (almost) always > 0 -> log is safe

        # 1. level (kept small: GLB levels mix currencies)
        add(f"rank({f})", "level")
        add(f"-rank({f})", "level")
        add(f"zscore({f})", "level")
        add(f"zscore(signed_power({f},0.5))", "level")
        add(f"rank(winsorize({f},std=4))", "level")
        add(f'rank(quantile({f},driver="gaussian"))', "level")
        add(f"normalize({f},useStd=true)", "level")
        add(f"rank(abs(zscore({f})))", "level")
        add(f"-rank(abs(zscore({f})))", "level")

        # 2. coverage (50% instrument coverage -> backfill / NaN handling matters)
        for d in [60, 120, 252]:
            add(f"rank(ts_backfill({f},{d}))", "backfill")
            add(f"-rank(ts_backfill({f},{d}))", "backfill")
            add(f"rank(zscore(ts_backfill({f},{d})))", "backfill")
        for d in [120, 252]:
            add(f'rank(kth_element({f},{d},k="1",ignore="NAN 0"))', "backfill")
            add(f"rank(ts_count_nans({f},{d}))", "coverage")
            add(f"-rank(ts_count_nans({f},{d}))", "coverage")

        # 3. staleness / report-update timing
        add(f"rank(days_from_last_change({f}))", "staleness")
        add(f"-rank(days_from_last_change({f}))", "staleness")
        for d in [60, 120, 252]:
            add(f"rank(subtract({f},last_diff_value({f},{d})))", "staleness")
            add(f"rank(divide(subtract({f},last_diff_value({f},{d})),abs(last_diff_value({f},{d}))))", "staleness")
            add(f"-rank(divide(subtract({f},last_diff_value({f},{d})),abs(last_diff_value({f},{d}))))", "staleness")

        # 4. scale-free time-series state
        for d in q_w:
            add(f"rank(ts_zscore({f},{d}))", "ts_zscore")
            add(f"-rank(ts_zscore({f},{d}))", "ts_zscore")
            add(f"rank(ts_rank({f},{d}))", "ts_rank")
            add(f"-rank(ts_rank({f},{d}))", "ts_rank")
            add(f"rank(ts_scale({f},{d}))", "ts_scale")
            add(f"rank(ts_av_diff({f},{d}))", "ts_av_diff")
            add(f"-rank(ts_av_diff({f},{d}))", "ts_av_diff")
            add(f"rank(ts_quantile({f},{d}))", "ts_shape")
            add(f"rank(ts_min_max_diff({f},{d}))", "ts_shape")
            add(f"rank(ts_min_diff({f},{d}))", "ts_shape")
            add(f"rank(ts_arg_max({f},{d}))", "ts_shape")
            add(f"-rank(ts_arg_max({f},{d}))", "ts_shape")
            add(f"rank(ts_arg_min({f},{d}))", "ts_shape")
            add(f"rank(ts_skewness({f},{d}))", "ts_shape")
            add(f"rank(ts_entropy({f},{d}))", "ts_shape")
            add(f"rank(ts_decay_linear({f},{d},dense=true))", "ts_decay")
            add(f"rank(ts_mean({f},{d}))", "ts_mean")

        # 5. growth / change, normalised so currency does not matter
        for d in q_w:
            add(f"rank(divide(ts_delta({f},{d}),abs(ts_mean({f},{d}))))", "growth")
            add(f"-rank(divide(ts_delta({f},{d}),abs(ts_mean({f},{d}))))", "growth")
            add(f"rank(divide(ts_delta({f},{d}),ts_std_dev({f},{d})))", "growth")
            add(f"-rank(divide(ts_delta({f},{d}),ts_std_dev({f},{d})))", "growth")
            add(f"rank(divide(ts_delta({f},{d}),abs(ts_delay({f},{d}))))", "growth")
            add(f"rank(divide({f},ts_mean({f},{d})))", "vs_own_mean")
            add(f"-rank(divide({f},ts_mean({f},{d})))", "vs_own_mean")
            add(f"rank(subtract(ts_mean({f},{d // 2}),ts_mean({f},{d})))", "mean_cross")
            add(f"rank(ts_delta({f},{d}))", "ts_delta")
            add(f"-rank(ts_delta({f},{d}))", "ts_delta")
        if pos_only:
            for d in q_w:
                add(f"rank(ts_delta(log({f}),{d}))", "log_growth")
                add(f"-rank(ts_delta(log({f}),{d}))", "log_growth")
                add(f"rank(ts_zscore(log({f}),{d}))", "log_growth")

        # 6. volatility / stability of the fundamental
        for d in q_w:
            add(f"-rank(divide(ts_std_dev({f},{d}),abs(ts_mean({f},{d}))))", "stability")
            add(f"rank(divide(ts_std_dev({f},{d}),abs(ts_mean({f},{d}))))", "stability")

        # 7. second-order / acceleration
        for d in [60, 120, 252]:
            add(f"rank(subtract(ts_delta({f},{d}),ts_delay(ts_delta({f},{d}),{d})))", "accel")
            add(f"rank(ts_zscore(ts_delta({f},{d}),{2 * d}))", "accel")
            add(f"rank(ts_rank(ts_delta({f},{d}),{2 * d}))", "accel")

        # 8. persistence of improvement: net count of up- vs down-revisions of the fundamental
        for d in [252, 504]:
            add(f"rank(ts_sum(sign(ts_delta({f},1)),{d}))", "streak")
            add(f"rank(ts_decay_linear(sign(ts_delta({f},1)),{d}))", "streak")
            add(f"-rank(ts_sum(abs(sign(ts_delta({f},1))),{d}))", "streak")

        # 9. linear trend of the fundamental (ts_regression on the day counter ts_step)
        for d in [120, 252, 504]:
            add(f"rank(divide(ts_regression({f},ts_step(1),{d},lag=0,rettype=2),abs(ts_mean({f},{d}))))", "trend")
            add(f"rank(ts_regression({f},ts_step(1),{d},lag=0,rettype=6))", "trend")
            add(f"rank(ts_regression({f},ts_step(1),{d},lag=0,rettype=0))", "trend")
            add(f"-rank(ts_regression({f},ts_step(1),{d},lag=0,rettype=0))", "trend")

        # 10. level x momentum, smoothed signals
        for d in [60, 120, 252]:
            add(f"rank(multiply(rank({f}),rank(ts_delta({f},{d}))))", "level_x_mom")
            add(f"rank(subtract(rank({f}),rank(ts_delta({f},{d}))))", "level_x_mom")
            add(f"rank(add(rank({f}),rank(ts_rank({f},{d}))))", "level_x_mom")
            add(f"rank(ts_decay_linear(ts_zscore({f},{d}),20,dense=true))", "decay_combo")
            add(f"rank(ts_decay_linear(ts_rank({f},{d}),20,dense=true))", "decay_combo")
            add(f"rank(ts_decay_linear(rank(ts_delta({f},{d})),20,dense=true))", "decay_combo")

        # 11. change signal orthogonal to the field's own level (single raw field)
        for d in [60, 120, 252]:
            add(f"rank(vector_neut(zscore(ts_delta({f},{d})),zscore({f})))", "self_neut")
            add(f"rank(vector_neut(zscore(ts_zscore({f},{d})),zscore({f})))", "self_neut")

        # 12. bounded transforms of the time-series state (not rank-wrapped on purpose)
        for d in [120, 252, 504]:
            add(f"tanh(ts_zscore({f},{d}))", "squash")
            add(f"signed_power(ts_zscore({f},{d}),0.5)", "squash")

        # 13. in-bucket relative: target = change/state, bucket = the field's OWN level rank
        bkt = f'bucket(rank({f}),range="0, 1, 0.1")'
        bkt5 = f'bucket(rank({f}),range="0, 1, 0.2")'
        for d in [60, 120, 252]:
            add(f"group_rank(rank(ts_delta({f},{d})),{bkt})", "bucket_self")
            add(f"group_neutralize(rank(ts_zscore({f},{d})),{bkt})", "bucket_self")
            add(f"group_zscore(ts_zscore({f},{d}),{bkt5})", "bucket_self")
            add(f"group_scale(rank(ts_rank({f},{d})),{bkt5})", "bucket_self")

        # 14. rank within currency group (makes GLB levels comparable)
        if CCY_GROUP_ENABLED:
            g = CCY_GROUP
            add(f"group_rank({f},{g})", "ccy_group")
            add(f"group_zscore(zscore({f}),{g})", "ccy_group")
            add(f"group_neutralize(rank({f}),{g})", "ccy_group")
            add(f"rank(group_backfill({f},{g},120))", "ccy_group")
            for d in [60, 120, 252]:
                add(f"group_rank(ts_zscore({f},{d}),{g})", "ccy_group")
                add(f"group_neutralize(rank(ts_delta({f},{d})),{g})", "ccy_group")
            # currency x own-level bucket
            gb = f'group_cartesian_product({g},bucket(rank({f}),range="0, 1, 0.25"))'
            for d in [120, 252]:
                add(f"group_rank(rank(ts_delta({f},{d})),{gb})", "ccy_bucket")
                add(f"group_neutralize(rank(ts_zscore({f},{d})),{gb})", "ccy_bucket")

        # 15. turnover control
        add(f"hump(rank(ts_rank({f},120)),hump=0.01)", "hump")
        add(f"hump(rank(ts_zscore({f},252)),hump=0.01)", "hump")
        add(f"hump(rank(ts_delta({f},120)),hump=0.01)", "hump")
        add(f"hump(rank(divide(ts_delta({f},252),abs(ts_mean({f},252)))),hump=0.01)", "hump")

        # 16. event-driven: trade on fresh report updates (z=-1 -> never force an exit)
        for k in [5, 10, 20]:
            add(f"trade_when(days_from_last_change({f})<={k},rank({f}),-1)", "trade_when")
            add(f"trade_when(days_from_last_change({f})<={k},rank(ts_zscore({f},252)),-1)", "trade_when")
            add(f"trade_when(days_from_last_change({f})<={k},rank(ts_delta({f},120)),-1)", "trade_when")
        add(f"trade_when(abs(ts_zscore({f},120))>1,rank({f}),-1)", "trade_when")
        add(f"trade_when(ts_rank({f},120)>0.7,rank({f}),ts_rank({f},120)<0.3)", "trade_when")
        add(f"trade_when(days_from_last_change({f})<=10,rank(divide(ts_delta({f},120),abs(ts_mean({f},120)))),days_from_last_change({f})>120)", "trade_when")

    # ================= COMBO FAMILIES =================
    # 13. cross-field ratios (unit-free, the natural fundamental combos)
    for a, b in ordered_pairs:
        add(f"rank(divide({a},{b}))", "ratio", single=False)
        add(f"rank(divide({a},abs({b})))", "ratio", single=False)
        for d in [120, 252]:
            add(f"rank(ts_zscore(divide({a},{b}),{d}))", "ratio_ts", single=False)
            add(f"rank(ts_delta(divide({a},{b}),{d}))", "ratio_ts", single=False)
            add(f"-rank(ts_delta(divide({a},{b}),{d}))", "ratio_ts", single=False)

    # 14. static pair relationships
    for a, b in pairs:
        add(f"rank({_blend(a, b)})", "pair_static", single=False)
        add(f"rank(multiply(zscore({a}),zscore({b})))", "pair_static", single=False)
        add(f"rank(min(zscore({a}),zscore({b})))", "pair_static", single=False)
        add(f"rank(max(zscore({a}),zscore({b})))", "pair_static", single=False)
        add(f"rank(abs({_spread(a, b)}))", "pair_static", single=False)
    for a, b in ordered_pairs:
        add(f"rank({_spread(a, b)})", "pair_spread", single=False)

    # 15. pair time-series
    for a, b in pairs:
        s_ab = _spread(a, b)
        for d in [120, 252]:
            add(f"rank(ts_zscore({s_ab},{d}))", "spread_ts", single=False)
            add(f"rank(ts_delta({s_ab},{d}))", "spread_ts", single=False)
            add(f"-rank(ts_delta({s_ab},{d}))", "spread_ts", single=False)
            add(f"rank(ts_corr({a},{b},{d}))", "ts_corr", single=False)
            add(f"-rank(ts_corr({a},{b},{d}))", "ts_corr", single=False)
            add(f"rank(ts_regression({a},{b},{d},lag=0,rettype=0))", "ts_reg", single=False)
            add(f"rank(ts_regression({b},{a},{d},lag=0,rettype=0))", "ts_reg", single=False)

    # 16. orthogonalisation (Genius)
    for y, x in ordered_pairs:
        add(f"rank(vector_neut(zscore({y}),zscore({x})))", "neut", single=False)

    # 17. a few triples
    for a, b, c in triples:
        add(f"rank(add(zscore({a}),zscore({b}),zscore({c})))", "triple", single=False)
        add(f"rank(ts_zscore(add(zscore({a}),zscore({b}),zscore({c})),252))", "triple", single=False)

    return candidates


def _validate_local(expr: str) -> bool:
    """Cheap offline filter mirroring the pack's own limits."""
    if "vec_" in expr and not any(v in expr for v in ("vec_avg(", "vec_sum(")):
        return False
    # every called function must be in the allowed operator list (blocks ts_returns, typos, ...)
    if any(name not in ALLOWED_OPERATORS for name in re.findall(r"\b([A-Za-z_][A-Za-z_0-9]*)\s*\(", expr)):
        return False
    # single-category rule: only fnd6 fields, no pv1 / group-field names
    if any(t not in FIELDS and t != CCY_FIELD for t in re.findall(r"\bfnd6_\w+", expr)):
        return False
    if BANNED_TOKENS & set(re.findall(r"\b[A-Za-z_][A-Za-z_0-9]*\b", expr)):
        return False
    used = {f for f in FIELDS if re.search(rf"\b{re.escape(f)}\b", expr)}
    if not used or len(used) > MAX_RAW_FIELDS:
        return False
    # the currency group key counts toward the raw-field limit too
    n_raw = len(used) + (1 if re.search(rf"\b{re.escape(CCY_FIELD)}\b", expr) else 0)
    if n_raw > MAX_RAW_FIELDS:
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


def _round_robin(by_family: dict, order: list, n: int, chosen: dict):
    target = len(chosen) + n
    while len(chosen) < target:
        progressed = False
        for tag in order:
            if by_family[tag]:
                expr = by_family[tag].pop()
                chosen[expr] = tag
                progressed = True
                if len(chosen) == target:
                    break
        if not progressed:
            break


def build_pool(seed: int, pool_size: int) -> dict:
    """Deterministic pool: SINGLE_SHARE single-field alphas, rest combos, each spread round-robin by family."""
    all_candidates = {e: t for e, t in _generate_candidates().items() if _validate_local(e)}
    if len(all_candidates) < pool_size:
        raise ValueError(
            f"fnd6_glb pack only has {len(all_candidates)} valid candidates, "
            f"requested pool_size={pool_size}"
        )

    rng = random.Random(seed)
    single: dict[str, list] = {}
    combo: dict[str, list] = {}
    for expr, tag in all_candidates.items():
        (single if tag in SINGLE_TAGS else combo).setdefault(tag, []).append(expr)
    for d in (single, combo):
        for tag in d:
            d[tag].sort()
            rng.shuffle(d[tag])

    n_single_avail = sum(len(v) for v in single.values())
    n_combo_avail = sum(len(v) for v in combo.values())
    n_single = min(round(pool_size * SINGLE_SHARE), n_single_avail)
    n_combo = min(pool_size - n_single, n_combo_avail)
    n_single = pool_size - n_combo  # backfill from singles if combos run out

    chosen: dict[str, str] = {}
    _round_robin(single, sorted(single), n_single, chosen)
    _round_robin(combo, sorted(combo), n_combo, chosen)
    return chosen
