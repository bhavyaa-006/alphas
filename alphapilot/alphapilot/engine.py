"""
The run loop: pool -> batches of simulations -> (periodically) a submission
cycle. Everything here is dataset-agnostic; the pack supplies the fields,
operators and expressions, ace_lib does the actual HTTP calls, state.py
remembers what has already happened so this can always be interrupted and
resumed.

Known BRAIN behaviour this engine works around (verified by reading
ace_lib.py, not guessed): a multi-simulation batch is all-or-nothing - if ONE
expression in a batch of up to 10 errors, ace_lib.simulate_multi_alpha()
returns alpha_id=None for every expression in that batch, even though BRAIN
already ran (and counted against quota) the ones that were fine. When that
happens this engine falls back to simulating that batch's expressions one at
a time, so the good ones are still recovered and only the actually-broken
expression is marked as an error.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

from . import brain_client as BC
from . import llm as LLM
from .state import Store
from .util import LOGGER, fmt_duration, say, today_str


class EngineHalt(Exception):
    """Raised to stop the whole run cleanly (daily limit reached and configured to stop, submit halted, etc.)."""


@dataclass
class RunStats:
    batches_run: int = 0
    simulated_ok: int = 0
    simulated_err: int = 0
    submitted: int = 0
    started_at: float = 0.0
    consecutive_errors: int = 0
    last_error_sample: str = ""


def notify(cfg, text: str):
    """Best-effort webhook/ntfy ping. Never raises - a broken webhook must not crash a run."""
    import requests

    for url_key, payload_fn in (
        ("webhook_url", lambda: {"text": text}),
        ("ntfy_url", lambda: text.encode("utf-8")),
    ):
        url = cfg.notify.get(url_key) if isinstance(cfg.notify, dict) else getattr(cfg.notify, url_key, "")
        if not url:
            continue
        try:
            payload = payload_fn()
            if isinstance(payload, dict):
                requests.post(url, json=payload, timeout=10)
            else:
                requests.post(url, data=payload, timeout=10)
        except Exception as e:
            LOGGER.warning("notify to %s failed: %r", url_key, e)


# ---------------------------------------------------------------- simulation

def _settings_text(pack) -> str:
    s = pack.settings
    return (
        f"region {s['region']}, universe {s['universe']}, delay {s['delay']}, decay {s['decay']}, "
        f"neutralization {s['neutralization']}, truncation {s['truncation']}"
    )


def _make_alpha_dict(ace, pack, expr: str) -> dict:
    return ace.generate_alpha(regular=expr, **pack.settings)


def _post_sim_config(ace) -> dict:
    return dict(ace.DEFAULT_CONFIG)


def _poll_simulation(ace, s, sim_id_or_url: str, timeout_min: float, max_retry_after_s: float):
    """Poll a single /simulations/{id} to completion. Returns the raw final JSON (never raises on ERROR status)."""
    url = sim_id_or_url if sim_id_or_url.startswith("http") else f"{ace.brain_api_url}/simulations/{sim_id_or_url}"
    deadline = time.time() + timeout_min * 60
    while True:
        if time.time() >= deadline:
            return {"status": "TIMEOUT", "message": f"gave up polling after {timeout_min:.0f} minutes"}
        r = s.get(url)
        if r.status_code // 100 != 2:
            # GET is safe to retry, but keep the polling window finite.
            if r.status_code == 429 or r.status_code >= 500:
                try:
                    retry_after = float(r.headers.get("Retry-After", 1) or 1)
                except (TypeError, ValueError):
                    retry_after = 1
                wait = min(max_retry_after_s, max(1.0, retry_after))
                time.sleep(min(wait, max(0.0, deadline - time.time())))
                continue
            return {"status": "ERROR", "message": f"poll HTTP {r.status_code}: {r.text[:400]}"}
        wait = 0.0
        try:
            wait = float(r.headers.get("Retry-After", 0) or 0)
        except (TypeError, ValueError):
            pass
        if wait <= 0:
            try:
                data = r.json()
                return data if isinstance(data, dict) else {"status": "ERROR", "message": "poll returned non-object JSON"}
            except (ValueError, TypeError) as e:
                return {"status": "ERROR", "message": f"invalid poll response JSON: {e}; body={r.text[:400]}"}
        if time.time() > deadline:
            return {"status": "TIMEOUT", "message": f"gave up polling after {timeout_min:.0f} minutes"}
        time.sleep(min(wait, max_retry_after_s, max(0.0, deadline - time.time())))


def _simulate_one(ace, s, alpha_dict: dict, timeout_min: float, max_retry_after_s: float) -> dict:
    """Single-alpha simulation that KEEPS the error detail (unlike ace_lib.simulate_single_alpha, which discards it)."""
    resp = ace.start_simulation(s, alpha_dict)
    if resp.status_code == 429:
        raise BC.RateLimited(retry_after=float(resp.headers.get("Retry-After", 0) or 0), detail=resp.text[:200])
    if resp.status_code // 100 != 2:
        return {"alpha_id": None, "simulate_data": alpha_dict, "error": f"HTTP {resp.status_code}: {resp.text[:400]}"}
    final = _poll_simulation(ace, s, resp.headers["Location"], timeout_min, max_retry_after_s)
    alpha_id = final.get("alpha")
    if not alpha_id:
        loc = final.get("location") or {}
        detail = final.get("message") or f"status={final.get('status')}"
        if loc:
            detail += f" (line {loc.get('line')}, col {loc.get('start')}-{loc.get('end')})"
        return {"alpha_id": None, "simulate_data": alpha_dict, "error": detail}
    return {"alpha_id": alpha_id, "simulate_data": alpha_dict, "error": None}


def _simulate_batch_with_fallback(ace, s, cfg, alpha_dicts: list) -> list:
    """
    Try one multi-simulation for the whole batch. If BRAIN rejects the batch
    as a whole (all alpha_id=None - the all-or-nothing bug described in the
    module docstring), re-simulate each expression individually so the
    good ones are still recovered and the bad one is pinpointed.
    """
    if len(alpha_dicts) == 1:
        return [_simulate_one(ace, s, alpha_dicts[0], cfg.simulation.batch_timeout_min, cfg.api.max_retry_after_s)]

    resp = ace.start_simulation(s, alpha_dicts)
    if resp.status_code == 429:
        raise BC.RateLimited(retry_after=float(resp.headers.get("Retry-After", 0) or 0), detail=resp.text[:200])
    if resp.status_code // 100 != 2:
        detail = f"HTTP {resp.status_code}: {resp.text[:400]}"
        return [{"alpha_id": None, "simulate_data": a, "error": detail} for a in alpha_dicts]

    parent = _poll_simulation(ace, s, resp.headers["Location"], cfg.simulation.batch_timeout_min, cfg.api.max_retry_after_s)
    children = parent.get("children") or []
    if not children:
        detail = parent.get("message") or f"status={parent.get('status')}"
        return [{"alpha_id": None, "simulate_data": a, "error": f"batch rejected: {detail}"} for a in alpha_dicts]

    results = []
    any_missing = False
    for child_id, alpha_dict in zip(children, alpha_dicts):
        child = _poll_simulation(ace, s, child_id, cfg.simulation.batch_timeout_min, cfg.api.max_retry_after_s)
        alpha_id = child.get("alpha")
        if alpha_id:
            results.append({"alpha_id": alpha_id, "simulate_data": alpha_dict, "error": None})
        else:
            any_missing = True
            results.append({"alpha_id": None, "simulate_data": alpha_dict, "error": None})  # re-diagnosed below

    # A short children list is a malformed/incomplete parent response.  Do not
    # silently drop claimed inputs: diagnose the unpaired expressions too.
    if len(children) < len(alpha_dicts):
        any_missing = True
        results.extend(
            {"alpha_id": None, "simulate_data": alpha_dict, "error": None}
            for alpha_dict in alpha_dicts[len(children):]
        )
    if len(children) > len(alpha_dicts):
        LOGGER.warning("BRAIN batch returned %d children for %d inputs; ignoring extras", len(children), len(alpha_dicts))

    if not any_missing:
        return results

    # fall back: re-run only the ones missing an id, one at a time, to pinpoint the real error
    say(f"  batch had failures - re-checking {sum(1 for r in results if r['alpha_id'] is None)} expression(s) individually")
    fixed = []
    for r in results:
        if r["alpha_id"] is not None:
            fixed.append(r)
            continue
        fixed.append(_simulate_one(ace, s, r["simulate_data"], cfg.simulation.batch_timeout_min, cfg.api.max_retry_after_s))
    return fixed


def _fetch_stats(ace, s, alpha_id: str, simulate_data: dict) -> dict:
    r = ace.get_specified_alpha_stats(s, alpha_id, simulate_data, **_post_sim_config(ace))
    stats = {}
    failed_tests = []
    if r.get("is_stats") is not None and len(r["is_stats"]):
        row = r["is_stats"].iloc[0].to_dict()
        stats = {k: row.get(k) for k in ("sharpe", "fitness", "turnover", "returns", "margin")}
    if r.get("is_tests") is not None and len(r["is_tests"]) and "result" in r["is_tests"].columns:
        failed_tests = r["is_tests"].loc[r["is_tests"]["result"] == "FAIL", "name"].tolist()
    return {"stats": stats, "failed_tests": failed_tests}


def run_simulation_batches(ace, s, cfg, pack, store: Store, on_progress: Optional[Callable] = None, max_batches: Optional[int] = None, focus=None) -> RunStats:
    rs = RunStats(started_at=time.time())
    # consecutive_errors must survive across calls to this function, not just across
    # batches within one call - cmd_run invokes this with max_batches=1 in a loop, so a
    # fresh RunStats() is created every batch. Without persisting the streak in the store,
    # rs.consecutive_errors could never exceed cfg.simulation.batch_size (<=10) before the
    # function returned, so error_streak_halt (default 20) could never fire and a systemic
    # failure (bad session, broken settings, etc.) would silently burn through the whole pool.
    rs.consecutive_errors = int(store.get_meta("consecutive_errors", 0) or 0)
    rate_limit_retries = 0
    n_requeued = store.requeue_stuck()
    if n_requeued:
        say(f"recovered {n_requeued} expression(s) left mid-batch by a previous interrupted run")

    while True:
        if max_batches is not None and rs.batches_run >= max_batches:
            break
        batch = store.claim_batch(cfg.simulation.batch_size, cfg.simulation.max_attempts, focus=focus)
        if not batch:
            break

        alpha_dicts = [_make_alpha_dict(ace, pack, e) for e in batch]
        try:
            results = _simulate_batch_with_fallback(ace, s, cfg, alpha_dicts)
        except BC.RateLimited as e:
            # put the batch back to pending so it's retried, then decide stop/wait
            store.conn.execute(
                "UPDATE alphas SET status='pending' WHERE expr IN (%s)" % ",".join("?" * len(batch)), batch
            )
            store.conn.commit()
            if cfg.simulation.on_daily_limit == "wait" and e.retry_after and rate_limit_retries < cfg.simulation.max_attempts:
                rate_limit_retries += 1
                say(f"rate limited - waiting {fmt_duration(e.retry_after)} before retrying")
                time.sleep(min(e.retry_after, 3600))
                continue
            store.log_event("rate_limited", str(e))
            raise EngineHalt(f"Simulation rate/daily limit reached: {e}. Re-run later to continue - progress is saved.") from e
        except Exception as e:
            # No claimed row may be left in `simulating` after a failed request,
            # malformed response, or unexpected client exception.
            detail = f"{type(e).__name__}: {e}"
            LOGGER.exception("[BATCH] simulation failed batch_size=%d", len(batch))
            store.log_event("batch_exception", detail[:2000])
            for expr in batch:
                store.mark_error(expr, detail)
                rs.simulated_err += 1
                rs.consecutive_errors += 1
                rs.last_error_sample = detail
            store.set_meta("consecutive_errors", str(rs.consecutive_errors))
            if rs.consecutive_errors >= cfg.simulation.error_streak_halt:
                store.log_event("error_streak_halt", f"{rs.consecutive_errors} consecutive batch errors: {detail}")
                raise EngineHalt(
                    f"Stopped after {rs.consecutive_errors} consecutive batch errors: {detail}. "
                    "The batch has been recorded as failed and can be retried later."
                ) from e
            rs.batches_run += 1
            if on_progress:
                on_progress(rs, store.counts())
            continue

        rate_limit_retries = 0
        if len(results) != len(batch):
            detail = f"internal result count mismatch: received {len(results)} results for {len(batch)} claimed expressions"
            LOGGER.error("[BATCH] %s; marking unpaired expressions failed", detail)
            store.log_event("batch_result_mismatch", detail)
            results = list(results[:len(batch)])
            results.extend(
                {"alpha_id": None, "simulate_data": alpha_dicts[i], "error": detail}
                for i in range(len(results), len(batch))
            )

        for expr, r in zip(batch, results):
            if r["alpha_id"] is None:
                err = r.get("error") or "simulation failed (no alpha_id)"
                LOGGER.warning("[ALPHA] simulation failed stage=simulation expr=%r error=%s", expr[:240], err[:500])
                store.mark_error(expr, err)
                rs.simulated_err += 1
                rs.consecutive_errors += 1
                rs.last_error_sample = err
                store.set_meta("consecutive_errors", str(rs.consecutive_errors))
                if rs.consecutive_errors >= cfg.simulation.error_streak_halt:
                    # leave this (and everything still pending) untouched for next time -
                    # don't keep burning attempts on what looks like a systemic problem
                    store.log_event("error_streak_halt", f"{rs.consecutive_errors} in a row: {err}")
                    raise EngineHalt(
                        f"Stopped after {rs.consecutive_errors} simulations in a row failed with the "
                        f"same kind of error (this usually means a daily/rate limit, not a bad "
                        f"expression):\n  {err}\n"
                        "Nothing left in the pool was touched - re-run later to continue. "
                        "Run `alphapilot status` to see the full error breakdown, or lower "
                        "simulation.error_streak_halt in config.yaml if this is a false alarm."
                    )
                continue
            try:
                info = _fetch_stats(ace, s, r["alpha_id"], r["simulate_data"])
                store.mark_simulated(expr, r["alpha_id"], info["stats"], info["failed_tests"])
            except Exception as e:
                LOGGER.exception("[ALPHA] post-simulation stats failed for alpha_id=%s", r["alpha_id"])
                store.mark_error(expr, f"stats retrieval failed for alpha_id={r['alpha_id']}: {type(e).__name__}: {e}")
                rs.simulated_err += 1
                rs.consecutive_errors += 1
                rs.last_error_sample = str(e)
                store.set_meta("consecutive_errors", str(rs.consecutive_errors))
                continue
            rs.simulated_ok += 1
            rs.consecutive_errors = 0
            store.set_meta("consecutive_errors", "0")

        rs.batches_run += 1
        if on_progress:
            on_progress(rs, store.counts())

    return rs


# ---------------------------------------------------------------- submission

@dataclass
class SubmitDecision:
    do_it: bool
    reason: str


def _check_daily_cap(store: Store, cfg) -> SubmitDecision:
    day = today_str(cfg.submit.timezone)
    done_today = store.submissions_on(day)
    if done_today >= cfg.submit.max_per_day:
        return SubmitDecision(False, f"already submitted {done_today}/{cfg.submit.max_per_day} today ({day}, {cfg.submit.timezone})")
    return SubmitDecision(True, "")


_SKIP_THIS_PROCESS = set()   # expressions skipped for this process only (declined / couldn't save properties) - NOT permanent
_RECONCILED = {"done": False}


def _platform_status(ace, s, alpha_id: str):
    try:
        # Read once instead of using ace_lib.get_simulation_result_json(), whose
        # Retry-After loop is unbounded and can outlive the run's deadlines.
        response = s.get(f"{ace.brain_api_url}/alphas/{alpha_id}")
        if response.status_code // 100 != 2:
            return None
        detail = response.json()
        return detail.get("status") if isinstance(detail, dict) else None
    except Exception:
        return None


def _alpha_page_checks(ace, s, alpha_id: str):
    """The alpha's own is.checks as the platform reports them (what the website renders). None if unavailable."""
    import pandas as pd
    try:
        response = s.get(f"{ace.brain_api_url}/alphas/{alpha_id}")
        if response.status_code // 100 != 2:
            return None
        detail = response.json()
        lst = ((detail if isinstance(detail, dict) else {}).get("is") or {}).get("checks") or []
        df = pd.DataFrame([c for c in lst if isinstance(c, dict)])
    except Exception:
        return None
    return df if len(df) and {"name", "result"} <= set(df.columns) else None


def _fmt_fails(checks, failed_names) -> str:
    out = []
    for _, r in checks.iterrows():
        if r.get("name") in failed_names:
            out.append(f"{r.get('name')} (value={r.get('value')}, limit={r.get('limit')})")
    return "; ".join(out) or str(failed_names)


def _reconcile(ace, s, cfg, store: Store):
    """Alphas the local DB thinks were rejected but that are ACTIVE on the platform (e.g. you submitted them by hand)."""
    if _RECONCILED["done"]:
        return
    _RECONCILED["done"] = True
    for a in store.reconcile_candidates(50):
        if _platform_status(ace, s, a.alpha_id) == "ACTIVE":
            store.mark_submitted(a.expr, a.alpha_id, "(submitted outside alphapilot)", "", "manual", cfg.submit.timezone)
            store.log_event("reconciled", a.alpha_id)
            say(f"  synced: {a.alpha_id} is ACTIVE on the platform - recorded as submitted (was marked rejected locally)")


def run_submission_cycle(ace, s, cfg, pack, store: Store, ask_fn: Optional[Callable] = None, focus=None, max_new: Optional[int] = None) -> int:
    """
    Looks at the best not-yet-submitted, no-failed-IS-test alphas, runs the
    official platform check on each, and submits the first one that passes -
    subject to submit.mode, submit.max_per_run and submit.max_per_day. Returns
    the number of alphas submitted this cycle (0 or 1 in the normal 1/day
    setup, more only if you raise the limits).
    """
    mode = cfg.submit.mode
    if mode == "off":
        return 0

    submitted_this_run = 0
    _reconcile(ace, s, cfg, store)
    candidates = store.submit_candidates(cfg.submit.min_sharpe, cfg.submit.min_fitness, cfg.submit.max_candidates_per_cycle, focus=focus)
    # max_new = how many more submissions the whole run may still make (None = use max_per_run, 0 = unlimited)
    limit = max_new if max_new is not None else (cfg.submit.max_per_run or None)
    candidates = [c for c in candidates if c.expr not in _SKIP_THIS_PROCESS]
    if not candidates:
        return 0

    say(f"submission cycle: {len(candidates)} candidate(s) with no failed in-sample test")

    for cand in candidates:
        if limit is not None and submitted_this_run >= limit:
            break
        cap = _check_daily_cap(store, cfg)
        if not cap.do_it:
            say(f"  stopping submission cycle: {cap.reason}")
            break

        platform_status = _platform_status(ace, s, cand.alpha_id)
        if platform_status == "ACTIVE":
            store.mark_submitted(cand.expr, cand.alpha_id, "(submitted outside alphapilot)", "", "manual", cfg.submit.timezone)
            say(f"  {cand.alpha_id} is already ACTIVE on the platform - recorded as submitted, not counted toward this run")
            continue
        if platform_status is None:
            say(f"  could not read platform status for {cand.alpha_id}; skipping without submitting")
            _SKIP_THIS_PROCESS.add(cand.expr)
            continue

        say(f"  checking {cand.alpha_id}  sharpe={cand.sharpe}  fitness={cand.fitness}")
        precheck = cfg.submit.precheck or mode == "dry"   # dry run needs the check, otherwise it proves nothing
        if precheck:
            # Calling /check makes the platform compute the correlation checks. The verdict itself is then read from the
            # alpha page data (is.checks) - the same data the website shows - and no threshold/label logic is added by us.
            api_checks = ace.get_check_submission(s, cand.alpha_id)
            if api_checks is None or len(api_checks) == 0:
                store.mark_check(cand.expr, "UNKNOWN", "get_check_submission returned nothing")
                continue

            def _verdict():
                page = _alpha_page_checks(ace, s, cand.alpha_id)
                use = page if page is not None else api_checks
                f = use.loc[use["result"] == "FAIL", "name"].tolist() if "result" in use.columns else []
                p = use.loc[use["result"] == "PENDING", "name"].tolist() if "result" in use.columns else []
                return page, use, f, p

            page, use, failed, pending = _verdict()
            if failed:
                time.sleep(5)   # one re-read so a transitional value can't discard an alpha
                page, use, failed, pending = _verdict()
            api_failed = api_checks.loc[api_checks["result"] == "FAIL", "name"].tolist() if "result" in api_checks.columns else []
            if page is not None and set(api_failed) != set(failed):
                say(f"    note: the /check endpoint labels {sorted(set(api_failed) - set(failed))} as FAIL, but the alpha page "
                    f"(what the website shows) does not - following the alpha page")
            if failed:
                detail = _fmt_fails(use, failed)
                store.mark_check(cand.expr, "FAIL", f"failed: {detail}")
                say(f"    rejected by official check: {detail}")
                say("    /check said: " + ", ".join(f"{r['name']}={r['result']}" for _, r in api_checks.iterrows() if r["result"] != "PASS"))
                if page is not None:
                    say("    alpha page said: " + ", ".join(f"{r['name']}={r['result']}" for _, r in page.iterrows() if r["result"] != "PASS"))
                continue
            if pending:
                store.mark_check(cand.expr, "PENDING", f"still pending: {pending}")
                say(f"    still PENDING ({pending}) - will retry next cycle")
                continue

            store.mark_check(cand.expr, "PASS", "all checks passed")
        else:
            say("    submitting directly (submit.precheck=false) - the platform decides")

        meta = LLM.generate_metadata(
            cfg, cand.expr, pack.fields, pack.name, _settings_text(pack),
            {"sharpe": cand.sharpe, "fitness": cand.fitness, "turnover": cand.turnover},
        )
        say(f"    description via: {meta.source}")

        if mode == "dry":
            say(f"    DRY RUN - would submit {cand.alpha_id} as {meta.name!r} ({meta.category})")
            continue

        if mode == "ask":
            proceed = ask_fn(cand, meta) if ask_fn else False
            if not proceed:
                _SKIP_THIS_PROCESS.add(cand.expr)   # don't ask again about it every cycle
                say("    skipped (not confirmed)")
                continue

        resp = ace.set_alpha_properties(
            s, cand.alpha_id, name=meta.name, category=meta.category,
            regular_desc=meta.description, tags=meta.tags,
        )
        if resp.status_code // 100 != 2:
            say(f"    !! could not save name/description (HTTP {resp.status_code}: {resp.text[:200]}) - retrying with the built-in template text")
            meta = LLM.template_metadata(cand.expr, pack.fields, pack.name)
            resp = ace.set_alpha_properties(
                s, cand.alpha_id, name=meta.name, category=meta.category,
                regular_desc=meta.description, tags=meta.tags,
            )
        if resp.status_code // 100 != 2:
            # OUR side failed, not the alpha: keep it eligible (no permanent reject), skip it for this run only
            _SKIP_THIS_PROCESS.add(cand.expr)
            store.log_event("properties_failed", f"{cand.alpha_id}: HTTP {resp.status_code}: {resp.text[:300]}")
            say(f"    !! still could not save name/description. RAW from BRAIN: HTTP {resp.status_code}: {resp.text[:3000]}")
            say(f"       alpha is NOT rejected - you can submit it by hand: https://platform.worldquantbrain.com/alpha/{cand.alpha_id}")
            continue

        outcome = BC.submit_alpha(ace, s, cand.alpha_id, timeout_s=cfg.submit.timeout_min * 60, poll_every_s=cfg.submit.poll_seconds, show_polling=cfg.submit.show_polling)
        if outcome.ok:
            store.mark_submitted(cand.expr, cand.alpha_id, meta.name, meta.category, meta.source, cfg.submit.timezone)
            submitted_this_run += 1
            store.log_event("submitted", cand.alpha_id)
            say(f"    SUBMITTED: https://platform.worldquantbrain.com/alpha/{cand.alpha_id}")
            notify(cfg, f"alphapilot: submitted {cand.alpha_id} ({meta.name}, {pack.name})")
        elif outcome.halt:
            say(f"    RAW from BRAIN:\n{outcome.raw}")
            store.log_event("submit_halt", f"{cand.alpha_id}: {outcome.detail}\n{outcome.raw}")
            notify(cfg, f"alphapilot: HALTED during submit of {cand.alpha_id}: {outcome.detail}")
            _SKIP_THIS_PROCESS.add(cand.expr)
            store.mark_check(cand.expr, "UNSURE", f"{outcome.stage}: {outcome.detail}")
            if getattr(cfg.submit, "halt_on_unsure", False):
                raise EngineHalt(
                    f"Submission outcome for {cand.alpha_id} is unclear ({outcome.stage}, HTTP {outcome.status_code}): "
                    f"{outcome.detail}\nStopping so nothing is submitted twice. Check the alpha on the platform, "
                    f"then re-run: https://platform.worldquantbrain.com/alpha/{cand.alpha_id}"
                )
            say(f"    UNSURE outcome ({outcome.stage}, HTTP {outcome.status_code}): {outcome.detail}")
            say(f"    Skipping {cand.alpha_id} for this run to avoid duplicate submit. Moving to next candidate in batch.")
            say(f"    Check when ready: https://platform.worldquantbrain.com/alpha/{cand.alpha_id}")
            continue
        else:
            store.mark_submit_rejected(cand.expr, f"{outcome.stage}: {outcome.detail}\n{outcome.raw}")
            say(f"    rejected: {outcome.detail}")
            say(f"    RAW from BRAIN:\n{outcome.raw or '(nothing beyond the line above)'}")
            store.log_event("submit_rejected_raw", f"{cand.alpha_id}\n{outcome.raw}")

    return submitted_this_run


def check_candidate_platform(ace, s, cand: Alpha, store: Store, cfg) -> tuple[str, str]:
    """
    Checks the platform status and correlation tests for a candidate without submitting.
    Returns (status, message), e.g. ("PASS", ...), ("FAIL", ...), ("ACTIVE", ...), ("PENDING", ...)
    """
    st = _platform_status(ace, s, cand.alpha_id)
    if st == "ACTIVE":
        store.mark_submitted(cand.expr, cand.alpha_id, "(submitted outside alphapilot)", "", "manual", cfg.submit.timezone)
        return "ACTIVE", f"{cand.alpha_id} is already ACTIVE on platform (marked as submitted)"
    if st is None:
        store.mark_check(cand.expr, "UNKNOWN", "could not read alpha status from BRAIN")
        return "UNKNOWN", "could not read alpha status from BRAIN"

    api_checks = ace.get_check_submission(s, cand.alpha_id)
    if api_checks is None or len(api_checks) == 0:
        store.mark_check(cand.expr, "UNKNOWN", "get_check_submission returned nothing")
        return "UNKNOWN", "get_check_submission returned nothing"

    def _verdict():
        page = _alpha_page_checks(ace, s, cand.alpha_id)
        use = page if page is not None else api_checks
        f = use.loc[use["result"] == "FAIL", "name"].tolist() if "result" in use.columns else []
        p = use.loc[use["result"] == "PENDING", "name"].tolist() if "result" in use.columns else []
        return page, use, f, p

    page, use, failed, pending = _verdict()
    if failed:
        time.sleep(3)
        page, use, failed, pending = _verdict()
    if failed:
        detail = _fmt_fails(use, failed)
        store.mark_check(cand.expr, "FAIL", f"failed: {detail}")
        return "FAIL", f"rejected: {detail}"
    if pending:
        store.mark_check(cand.expr, "PENDING", f"still pending: {pending}")
        return "PENDING", f"still pending ({pending})"

    store.mark_check(cand.expr, "PASS", "all checks passed")
    return "PASS", "all checks passed"


def submit_candidate_now(ace, s, cfg, pack, store: Store, cand: Alpha) -> tuple[bool, str]:
    """
    Submits a single candidate alpha, handling metadata, properties, and submission polling.
    Returns (success, message).
    """
    st = _platform_status(ace, s, cand.alpha_id)
    if st == "ACTIVE":
        store.mark_submitted(cand.expr, cand.alpha_id, "(submitted outside alphapilot)", "", "manual", cfg.submit.timezone)
        return True, f"{cand.alpha_id} is already ACTIVE on platform (marked as submitted)"
    if st is None:
        return False, f"Could not read platform status for {cand.alpha_id}; not submitting while its state is unknown"

    meta = LLM.generate_metadata(
        cfg, cand.expr, pack.fields, pack.name, _settings_text(pack),
        {"sharpe": cand.sharpe, "fitness": cand.fitness, "turnover": cand.turnover},
    )
    resp = ace.set_alpha_properties(
        s, cand.alpha_id, name=meta.name, category=meta.category,
        regular_desc=meta.description, tags=meta.tags,
    )
    if resp.status_code // 100 != 2:
        meta = LLM.template_metadata(cand.expr, pack.fields, pack.name)
        resp = ace.set_alpha_properties(
            s, cand.alpha_id, name=meta.name, category=meta.category,
            regular_desc=meta.description, tags=meta.tags,
        )
    if resp.status_code // 100 != 2:
        return False, f"Could not save properties (HTTP {resp.status_code}): {resp.text[:300]}"

    outcome = BC.submit_alpha(ace, s, cand.alpha_id, timeout_s=cfg.submit.timeout_min * 60, poll_every_s=cfg.submit.poll_seconds, show_polling=cfg.submit.show_polling)
    if outcome.ok:
        store.mark_submitted(cand.expr, cand.alpha_id, meta.name, meta.category, meta.source, cfg.submit.timezone)
        store.log_event("submitted", cand.alpha_id)
        notify(cfg, f"alphapilot: submitted {cand.alpha_id} ({meta.name}, {pack.name})")
        return True, f"SUBMITTED: {cand.alpha_id} ({meta.name})"
    elif outcome.halt:
        store.log_event("submit_halt", f"{cand.alpha_id}: {outcome.detail}\n{outcome.raw}")
        store.mark_check(cand.expr, "UNSURE", f"{outcome.stage}: {outcome.detail}")
        return False, f"UNSURE / TIMEOUT: {outcome.detail} (Check platform: https://platform.worldquantbrain.com/alpha/{cand.alpha_id})"
    else:
        store.mark_submit_rejected(cand.expr, f"{outcome.stage}: {outcome.detail}\n{outcome.raw}")
        store.log_event("submit_rejected_raw", f"{cand.alpha_id}\n{outcome.raw}")
        return False, f"REJECTED: {outcome.detail}"
