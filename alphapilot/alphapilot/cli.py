from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import config as C
from . import engine as E
from . import packs_api as P
from . import secrets as SEC
from . import state as ST
from . import brain_client as BC
from .util import banner, say, setup_logging, fmt_duration, in_docker, Theme


def _pack_dirs(here: Path, home: Path):
    # here = .../alphapilot/alphapilot/cli.py -> repo root is two levels up
    repo_root = here.parent.parent
    return [home / "packs", repo_root / "packs"]


def _load_ace():
    """Load the bundled WorldQuant client without requiring a manual PYTHONPATH."""
    import importlib
    vendor = Path(__file__).resolve().parent.parent / "ACE_API__Gold_"
    if vendor.is_dir() and str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))
    return importlib.import_module("ace_lib")


def _state_db_path(home: Path, pack_key: str) -> Path:
    """Each pack gets its own state.db under <home>/state/, keyed on the pack FILE name (stem), so two
    files that happen to declare the same PACK_NAME can never share (and corrupt) one progress file."""
    d = home / "state"
    d.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in pack_key)
    return d / f"{safe}.db"


def _resolve_info(home: Path, cfg) -> P.PackInfo:
    return P.resolve_pack(cfg.pack, _pack_dirs(Path(__file__).resolve(), home))


def _state_db_for(home: Path, cfg) -> Path:
    """State db for the pack named in config. Older versions keyed the db on PACK_NAME; if this pack has
    no db yet but exactly one legacy one exists for its PACK_NAME (and no other pack file could own it),
    it is adopted instead of being orphaned. Reconciliation against the real file happens in init_pool."""
    try:
        info = _resolve_info(home, cfg)
    except P.PackError:
        return _state_db_path(home, str(cfg.pack))
    path = _state_db_path(home, info.key)
    if not path.exists() and info.pack_name and info.pack_name != info.key and not info.same_name_as:
        legacy = _state_db_path(home, info.pack_name)
        other_owner = any(i.key == info.pack_name and not i.shadowed_by
                          for i in P.discover(_pack_dirs(Path(__file__).resolve(), home)))
        if legacy.exists() and not other_owner:
            for suffix in ("", "-wal", "-shm"):
                src_p = Path(str(legacy) + suffix)
                if src_p.exists():
                    src_p.rename(Path(str(path) + suffix))
            say(f"(adopted existing progress {legacy.name} -> {path.name}; it will be checked against the pack file)")
    return path


def _load_pack_and_pool(home: Path, cfg):
    pack = P.load_pack(cfg.pack, _pack_dirs(Path(__file__).resolve(), home))
    pool = pack.build(cfg.simulation.seed, cfg.simulation.pool_size)
    return pack, pool


def _ensure_pool(home: Path, cfg, store: ST.Store):
    """Builds the pool from the pack file AS IT IS ON DISK NOW and makes `store` match it (idempotent).
    A replaced/edited pack file triggers a reconcile (stale unstarted rows removed); a different
    dataset/settings archives the old progress and starts clean - see Store.init_pool."""
    from .util import sha256_json

    pack, pool = _load_pack_and_pool(home, cfg)
    pack_hash = sha256_json({"fields": pack.fields, "settings": pack.settings, "ops": sorted(pack.allowed_operators)})
    r = store.init_pool(pack.name, pack_hash, cfg.simulation.seed, cfg.simulation.pool_size, pool,
                        file_hash=pack.file_hash, pack_key=pack.key)
    if r["action"] == "reconciled":
        say(f"pack file {pack.source_path.name} changed since last time - removed {r['removed']} stale "
            f"not-yet-simulated expression(s); kept every simulated/submitted result.")
    elif r["action"] == "reset":
        say(f"pack {pack.key!r}: fields/settings/operators changed, so old results are not comparable. "
            f"Old progress archived to {r['archive']} and a clean pool started "
            f"(submitted alphas are remembered).")
    store.tag_fields(pack.field_ids())
    return pack, pool, r


def cmd_init(args):
    home = _resolve_home(args)
    home.mkdir(parents=True, exist_ok=True)
    (home / "packs").mkdir(exist_ok=True)
    if not C.config_path(home).exists():
        C.save_file_config(home, C.default_config())
        say(f"wrote default config: {C.config_path(home)}")
    else:
        say(f"config already exists: {C.config_path(home)}")
    say(f"home directory ready: {home}")
    say("next: `alphapilot login`, then `alphapilot doctor`, then `alphapilot run`")


def cmd_login(args):
    home = _resolve_home(args)
    home.mkdir(parents=True, exist_ok=True)
    email, _ = SEC.ensure_credentials(home)
    say(f"credentials saved for {email}. Run `alphapilot doctor` to verify the connection.")


def cmd_packs(args):
    home = _resolve_home(args)
    cfg = C.load_config(home, getattr(args, "set", []))
    dirs = _pack_dirs(Path(__file__).resolve(), home)
    try:
        active = _resolve_info(home, cfg).key
    except P.PackError:
        active = None
    infos = P.list_pack_infos(dirs)
    for i in infos:
        if i.shadowed_by:
            print(f"  -- {i.key:<24} IGNORED (same file name exists in an earlier folder, which wins)\n      ({i.path})")
        elif i.error:
            print(f"  !! {i.key:<24} FAILED TO LOAD: {i.error.splitlines()[0]}\n      ({i.path})")
        else:
            mark = "*" if i.key == active else " "
            print(f" {mark} {i.key:<24} {i.description}\n      ({i.path})")
            if i.same_name_as:
                print(f"      !! PACK_NAME {i.pack_name!r} is ALSO declared by: {', '.join(i.same_name_as)} "
                      f"- select by file name ({i.key}) and delete the extra file you don't want")
    print(f"\n  * = active pack (config.yaml -> pack: {cfg.pack!r}"
          + ("" if active else " - NOT FOUND, run Settings -> Change pack") + ")")


def cmd_doctor(args):
    ace = _load_ace()

    home = _resolve_home(args)
    cfg = C.load_config(home, args.set)
    setup_logging(home / "alphapilot.log", cfg.logging.verbose)
    SEC.ensure_credentials(home)

    banner(["alphapilot doctor", f"home: {home}"])

    say("1. loading pack ...")
    try:
        pack = P.load_pack(cfg.pack, _pack_dirs(Path(__file__).resolve(), home))
        say(f"   OK  {pack.name} - {len(pack.fields)} fields, {len(pack.allowed_operators)} allowed operators")
    except P.PackError as e:
        say(f"   !! {e}")
        return 1

    say("2. connecting / authenticating (this may open a face-check link) ...")
    links = []
    s = BC.ensure_session(ace, cfg, home, on_persona_link=lambda u: (links.append(u), say(f"   Face check needed: {u}")), on_waiting=lambda a, r: say(f"   waiting for face check... ({fmt_duration(r)} left)"))
    left = ace.check_session_timeout(s)
    say(f"   OK  session has {fmt_duration(left)} left")
    BC.install_into(ace, cfg, home, on_persona_link=lambda u: say(f"   Face check needed: {u}"), on_waiting=lambda a, r: say(f"   waiting... ({fmt_duration(r)} left)"))

    say("3. checking pack fields exist on the platform ...")
    missing, not_matrix = [], []
    for fid in pack.field_ids():
        df = ace.get_datafields(s, region=pack.settings["region"], delay=pack.settings["delay"], universe=pack.settings["universe"], search=fid)
        hit = df[df["id"] == fid] if len(df) else df
        if len(hit) == 0:
            missing.append(fid)
        elif str(hit.iloc[0].get("type", "")).upper() != "MATRIX":
            not_matrix.append(fid)
    if missing or not_matrix:
        say(f"   !! missing: {missing}  not MATRIX: {not_matrix}")
    else:
        say(f"   OK  all {len(pack.fields)} fields found and are MATRIX")

    say("4. checking operators against your account ...")
    ops_df = ace.get_operators(s)
    avail = set(ops_df[ops_df["scope"] == "REGULAR"]["name"]) if "scope" in ops_df.columns else set(ops_df["name"])
    missing_ops = pack.allowed_operators - avail
    if missing_ops:
        say(f"   !! operators in the pack your account does NOT have: {sorted(missing_ops)}")
        say("      (these will be skipped automatically; edit the pack to remove them if you want a clean pool)")
    else:
        say(f"   OK  all {len(pack.allowed_operators)} pack operators are available")

    if getattr(args, "check_model", False):
        from . import llm as LLM
        say("5. checking optional AI metadata provider ...")
        res = LLM.preflight(cfg)
        say(("   OK  " if res["ok"] else "   !! ") + f"{res['provider']}: {res['detail']}")
    else:
        say("5. optional AI metadata provider check skipped (use --check-model to test it)")

    say("6. smoke-testing one simulation ...")
    expr = min(pack.build(cfg.simulation.seed, cfg.simulation.pool_size), key=len)
    alpha_dict = ace.generate_alpha(regular=expr, **pack.settings)
    r = E._simulate_one(ace, s, alpha_dict, timeout_min=5, max_retry_after_s=cfg.api.max_retry_after_s)
    if r["alpha_id"]:
        say(f"   OK  {expr}  ->  {r['alpha_id']}  (https://platform.worldquantbrain.com/alpha/{r['alpha_id']})")
    else:
        say(f"   !! smoke simulation failed: {r['error']}")

    banner(["doctor finished - fix any !! lines above before a long `run`"])
    return 0


def _resolve_home(args):
    home = C.resolve_home(args.home)
    print(f"(using --home: {home})", file=sys.stderr)
    return home


def cmd_run(args):
    ace = _load_ace()

    cancel_event = getattr(args, "cancel_event", None)
    home = _resolve_home(args)
    overrides = list(getattr(args, "set", []))
    run_mode = getattr(args, "run_mode", None)
    if run_mode == "simulate":
        overrides.append("submit.mode=off")
    elif run_mode == "submit":
        # Explicit submission requests still require the existing per-alpha confirmation.
        overrides.append("submit.mode=ask")
    elif run_mode == "dry-run":
        overrides.append("submit.mode=dry")
    cfg = C.load_config(home, overrides)
    # one-off overrides from the CLI flags / menu (not saved to config.yaml)
    if getattr(args, "focus", None) is not None:
        cfg["run"]["focus"] = P.normalize_focus(args.focus)
    if getattr(args, "stop_after", None) is not None:
        cfg["submit"]["max_per_run"] = int(args.stop_after)
    setup_logging(home / "alphapilot.log", cfg.logging.verbose)
    SEC.ensure_credentials(home)

    store = ST.Store(_state_db_for(home, cfg))
    try:
        pack, pool, r = _ensure_pool(home, cfg, store)
    except ST.StateError as e:
        say(str(e))
        store.close()
        return 1
    say(f"pack: {pack.name}  |  pool: {r['new']} new, {r['existing']} already tracked (total {len(pool)})")

    focus = P.normalize_focus(cfg["run"].get("focus"))
    problems = P.validate_focus(focus, pack.field_ids())
    if problems:
        say("Focus problem:\n  " + "\n  ".join(problems))
        store.close()
        return 1
    if focus:
        say("focus (in this order): " + "  ->  ".join(focus))
        left = store.focus_remaining(focus)
        say(f"  {left} not-yet-simulated expression(s) match this focus")
        if left == 0:
            say("  nothing left to simulate for this focus (everything in it was already run). "
                "Pick other fields, or clear the focus.")
            store.close()
            return 0

    max_total = int(cfg.submit.max_per_run or 0)   # 0 = no limit
    live_submit = cfg.submit.mode in ("ask", "auto")
    if live_submit and not E._check_daily_cap(store, cfg).do_it:
        say("Not starting: " + E._check_daily_cap(store, cfg).reason +
            ". Raise submit.max_per_day, or run with submit.mode=off to simulate only.")
        store.close()
        return 0

    try:
        s = BC.ensure_session(ace, cfg, home, on_persona_link=lambda u: say(f"Face check needed: {u}"), on_waiting=lambda a, r: say(f"waiting for face check... ({fmt_duration(r)} left)"), cancel_event=cancel_event)
        BC.install_into(ace, cfg, home, on_persona_link=lambda u: say(f"Face check needed: {u}"), on_waiting=lambda a, r: say(f"waiting... ({fmt_duration(r)} left)"), cancel_event=cancel_event)
    except BC.SessionCancelled:
        store.close()
        say("Cancelled during BRAIN authentication.")
        return 130
    except Exception:
        store.close()
        raise

    def ask_fn(cand, meta):
        print(f"\nSubmit {cand.alpha_id}? sharpe={cand.sharpe} fitness={cand.fitness}")
        print(f"  name: {meta.name}  category: {meta.category}")
        print(f"  {meta.description[:300]}...")
        while True:
            answer = input("  Submit? [y/N] ").strip().lower()
            if answer == "?":
                print("This confirms submission of the displayed alpha. Enter y to submit or n/Enter to skip.")
                continue
            return answer == "y"

    banner([
        f"alphapilot run · pack={pack.name}",
        f"pool={len(pool)}  batch_size={cfg.simulation.batch_size}  submit.mode={cfg.submit.mode}  "
        f"stop after {max_total or 'unlimited'} submission(s)",
    ])

    total_submitted = 0
    stopped_reason = ""

    def remaining():
        return None if max_total == 0 else max_total - total_submitted

    def do_cycle():
        nonlocal total_submitted, stopped_reason
        total_submitted += E.run_submission_cycle(ace, s, cfg, pack, store, ask_fn=ask_fn, focus=focus, max_new=remaining())
        if max_total and total_submitted >= max_total:
            stopped_reason = f"reached the limit of {max_total} submission(s) for this run"
        elif live_submit and not E._check_daily_cap(store, cfg).do_it:
            stopped_reason = E._check_daily_cap(store, cfg).reason

    batches_since_submit_check = 0
    total_batches_run = 0
    max_batches = getattr(args, "max_batches", None)
    try:
        say("Connecting to BRAIN…")
        while not store.is_done(focus) and (max_batches is None or total_batches_run < max_batches):
            if cancel_event is not None and cancel_event.is_set():
                raise E.EngineCancelled()
            total_batches_run += 1
            _batch_num = total_batches_run  # capture now; default arg avoids late-binding closure bug
            def on_progress(rs, counts, _n=_batch_num):
                total = len(pool)
                completed = max(0, total - counts.get("pending", 0) - counts.get("simulating", 0))
                pct = min(100, int(completed * 100 / total)) if total else 100
                ok = counts.get("simulated", 0) + counts.get("submitted", 0)
                err = counts.get("error", 0)
                pending = counts.get("pending", 0)
                say(f"Batch {_n} complete | {ok} successful | {err} failed | {pending} pending | {pct}%")

            E.run_simulation_batches(ace, s, cfg, pack, store, on_progress=on_progress, max_batches=1,
                                     focus=focus, cancel_event=cancel_event)
            batches_since_submit_check += 1
            if batches_since_submit_check >= cfg.submit.cycle_every_batches:
                batches_since_submit_check = 0
                do_cycle()
                if stopped_reason:
                    break
        if not stopped_reason:
            # final submission cycle after the focus/pool is exhausted
            do_cycle()
    except E.EngineHalt as e:
        say(f"\nHALTED: {e}")
        say("Progress is saved. Review `alphapilot status` and `alphapilot retry-errors` before resuming.")
        return 2
    except KeyboardInterrupt:
        say("\nCancelled - progress is saved. Run `alphapilot run` to continue.")
        return 130
    except E.EngineCancelled:
        say("\nCancelled - unfinished expressions returned to pending; progress is saved.")
        return 130
    finally:
        final_counts = store.counts()
        store.close()

    banner([
        "run finished" + (f" - stopped: {stopped_reason}" if stopped_reason else ""),
        f"submitted this run: {total_submitted}   counts: {final_counts}",
    ])
    return 0


def cmd_fields(args):
    """Per-field progress, so you can decide what to focus on."""
    home = _resolve_home(args)
    cfg = C.load_config(home, getattr(args, "set", []))
    store = ST.Store(_state_db_for(home, cfg))
    try:
        pack, pool, _ = _ensure_pool(home, cfg, store)
        counts = store.focus_counts(pack.field_ids())
    finally:
        store.close()
    print(f"pack: {pack.name}")
    print(f"  {'field / group':<32} pending  simulated  submitted  error")
    field_filter = getattr(args, "field", None)
    names = [*pack.field_ids(), "combo"]
    if field_filter:
        if field_filter not in names:
            print(f"Unknown field {field_filter!r}. Choose from: {', '.join(names)}")
            return 2
        names = [field_filter]
    for name in names:
        c = counts[name]
        label = name if name != "combo" else "combo (2+ fields mixed)"
        print(f"  {label:<32} {c['pending']:>7}  {c['simulated']:>9}  {c['submitted']:>9}  {c['error']:>5}")
    return 0


def cmd_status(args):
    home = _resolve_home(args)
    cfg = C.load_config(home, getattr(args, "set", []))
    db = _state_db_for(home, cfg)
    if not db.exists():
        print(f"No progress yet for pack {cfg.pack!r} (nothing run there so far).")
        return 0
    store = ST.Store(db)
    print(f"pack: {cfg.pack}   ({db})")
    print("counts:", store.counts())
    print("\ntop alphas:")
    for a in store.top(10):
        print(f"  {a.expr[:70]:<70} sharpe={a.sharpe} fitness={a.fitness} status={a.status}")
    errs = store.error_summary(5)
    if errs:
        print("\nmost common errors:")
        for row in errs:
            print(f"  x{row['count']:<4} {row['example'][:100]}")
    store.close()


def cmd_errors(args):
    """Display recent error records and grouped diagnostics for this pack."""
    home = _resolve_home(args)
    cfg = C.load_config(home, getattr(args, "set", []))
    db = _state_db_for(home, cfg)
    if not db.exists():
        print(f"No progress or errors recorded for pack {cfg.pack!r}.")
        return 0
    store = ST.Store(db)
    try:
        rows = store.recent_errors(getattr(args, "limit", 20))
        if not rows:
            print(f"No errors recorded for pack {cfg.pack!r}.")
            return 0
        print(f"Recent errors for {cfg.pack!r}:")
        for row in rows:
            print(f"  {row['updated_at']}  attempts={row['attempts']}  {row['expr'][:90]}\n    {row['error']}")
        print("\nGrouped summary:")
        for row in store.error_summary(10):
            print(f"  x{row['count']:<4} {row['example'][:200]}")
    finally:
        store.close()
    return 0


def cmd_submissions(args):
    home = _resolve_home(args)
    cfg = C.load_config(home, getattr(args, "set", []))
    db = _state_db_for(home, cfg)
    if not db.exists():
        print(f"No progress yet for pack {cfg.pack!r}.")
        return 0
    store = ST.Store(db)
    rows = store.submissions_list(50)
    if not rows:
        print(f"No submissions yet for pack {cfg.pack!r}.")
    for r in rows:
        print(f"  {r['submitted_at']}  {r['alpha_id']}  {r['name']}  ({r['category']}, {r['description_source']})")
    store.close()


def cmd_candidates(args):
    home = _resolve_home(args)
    cfg = C.load_config(home, getattr(args, "set", []))
    db = _state_db_for(home, cfg)
    if not db.exists():
        print(f"No progress yet for pack {cfg.pack!r}.")
        return 0

    store = ST.Store(db)
    try:
        pack = P.load_pack(cfg.pack, _pack_dirs(Path(__file__).resolve(), home))
        field_ids = pack.field_ids()
    except Exception as e:
        print(f"Could not load pack {cfg.pack!r}: {e}")
        store.close()
        return 1

    field = getattr(args, "field", None)
    if getattr(args, "eligible", False) and not field:
        field = "all"
    min_sharpe = getattr(args, "min_sharpe", None)
    if min_sharpe is None:
        min_sharpe = cfg.submit.min_sharpe
    min_fitness = getattr(args, "min_fitness", None)
    if min_fitness is None:
        min_fitness = cfg.submit.min_fitness

    if not field:
        counts = store.candidate_counts_by_field(field_ids, min_sharpe, min_fitness)
        names = [*field_ids, "combo"]
        banner([
            f"Candidate Alphas by Field · pack={pack.name}",
            f"Eligible: sharpe >= {min_sharpe}  fitness >= {min_fitness}  (no failed IS test)",
        ])
        print(f"  {'':<4}{'field':<32}{'candidates':>10}{'unsure/pending':>16}{'passed check':>14}")
        for i, name in enumerate(names, 1):
            c = counts.get(name, {"total": 0, "unsure": 0, "pass": 0})
            label = name if name != "combo" else "COMBOS (any mix of 2+ fields)"
            print(f"  {i:>2}) {label:<32}{c['total']:>10}{c['unsure']:>16}{c['pass']:>14}")
        tot = counts.get("all", {"total": 0, "unsure": 0, "pass": 0})
        print(f"   0) {'All fields':<32}{tot['total']:>10}{tot['unsure']:>16}{tot['pass']:>14}")
        print("\nTip: Run with --field <name> to list candidates, or open Candidate Review from `alphapilot menu`.")
        store.close()
        return 0

    target_field = None if field in ("all", "0") else field
    limit = getattr(args, "limit", 25) or 25
    cands = store.get_candidates(min_sharpe, min_fitness, field=target_field, limit=limit)
    if not cands:
        print(f"No candidates found for field {field!r} (sharpe >= {min_sharpe}, fitness >= {min_fitness}).")
        store.close()
        return 0

    do_check = getattr(args, "check", False)
    do_submit = getattr(args, "submit", False)
    candidate_number = getattr(args, "candidate", None)
    action = getattr(args, "candidate_action", None)
    if candidate_number is not None:
        if candidate_number < 1 or candidate_number > len(cands):
            print(f"Candidate number must be between 1 and {len(cands)}.")
            store.close()
            return 2
        selected = cands[candidate_number - 1]
        if action == "inspect":
            print(f"alpha_id: {selected.alpha_id or '-'}")
            print(f"fields: {selected.fields or '-'}")
            print(f"sharpe: {selected.sharpe}  fitness: {selected.fitness}  turnover: {selected.turnover}")
            print(f"margin: {selected.margin}  returns: {selected.returns}")
            print(f"check_result: {selected.check_result or 'not checked yet'}")
            print(f"expression: {selected.expr}")
            store.close()
            return 0
        if action == "fail":
            store.mark_check(selected.expr, "FAIL", getattr(args, "reason", None) or "manually skipped")
            print(f"Marked {selected.alpha_id or candidate_number} as check_fail.")
            store.close()
            return 0
        if action == "manual_active":
            store.mark_submitted(selected.expr, selected.alpha_id, "(manual active)", "", "manual", cfg.submit.timezone)
            print(f"Marked {selected.alpha_id or candidate_number} as submitted.")
            store.close()
            return 0
        if action == "check":
            do_check = True
        if action == "submit":
            do_submit = True

    if do_check or do_submit:
        ace = _load_ace()
        s = BC.ensure_session(ace, cfg, home, on_persona_link=lambda u: say(f"Face check needed: {u}"), on_waiting=lambda a, r: say(f"waiting... ({fmt_duration(r)} left)"))
        BC.install_into(ace, cfg, home, on_persona_link=lambda u: say(f"Face check needed: {u}"), on_waiting=lambda a, r: say(f"waiting... ({fmt_duration(r)} left)"))

        if do_check:
            check_list = [cands[candidate_number - 1]] if candidate_number is not None else cands
            say(f"Checking {len(check_list)} candidate(s) against BRAIN platform...")
            for c in check_list:
                st, msg = E.check_candidate_platform(ace, s, c, store, cfg)
                say(f"  {c.alpha_id}  sharpe={c.sharpe}  status={st}  ({msg})")
            store.close()
            return 0

        if do_submit:
            cand = cands[candidate_number - 1] if candidate_number is not None else cands[0]
            say(f"Submitting top candidate {cand.alpha_id} (sharpe={cand.sharpe}, fitness={cand.fitness})...")
            ok, msg = E.submit_candidate_now(ace, s, cfg, pack, store, cand)
            say(f"Result: {msg}")
            store.close()
            return 0 if ok else 1

    banner([f"Candidates in {field!r} ({len(cands)} shown, ordered by fitness/sharpe)"])
    print(f"  {'#':<3}{'alpha_id':<14}{'sharpe':>7}{'fitness':>9}{'turnover':>10}{'check':>10}  expression")
    for i, c in enumerate(cands, 1):
        chk = c.check_result or "-"
        print(f"  {i:>2}) {c.alpha_id or '-':<14}{c.sharpe or 0:>7.2f}{c.fitness or 0:>9.2f}{c.turnover or 0:>10.2f}{chk:>10}  {c.expr[:60]}")
    store.close()
    return 0


def cmd_reset(args):
    home = _resolve_home(args)
    cfg = C.load_config(home, getattr(args, "set", []))
    db = _state_db_for(home, cfg)
    if not db.exists():
        print(f"No progress database exists for pack {cfg.pack!r}; nothing to reset.")
        return 0
    if getattr(args, "preview", False):
        store = ST.Store(db)
        try:
            counts = store.counts()
            history = store.conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        finally:
            store.close()
        print(f"Reset preview for {cfg.pack!r}: would clear pending, simulated, and error rows; "
              f"retain {counts.get('submitted', 0)} submitted row(s) and {history} history record(s).")
        return 0
    if not getattr(args, "yes", False):
        while True:
            answer = input(
                f"Clear pending/simulated/error progress for pack {cfg.pack!r}? "
                "Submitted alphas and submission history will be retained. [y/N] "
            ).strip().lower()
            if answer == "?":
                print("Reset options: /reset --preview to inspect scope, /reset to confirm, /back to cancel.")
                continue
            if answer != "y":
                print("cancelled")
                return 0
            break
    store = ST.Store(db)
    try:
        cleared = store.reset_progress()
        submitted = store.counts().get("submitted", 0)
        history = store.conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
    finally:
        store.close()
    print(f"Reset {cleared} local progress row(s) for {cfg.pack!r}; retained {submitted} submitted row(s) and {history} history record(s).")
    print("Configuration, credentials, and other packs were not changed.")
    return 0


def cmd_retry(args):
    """Reset errored expressions back to pending so they are picked up on the next `run`."""
    home = _resolve_home(args)
    cfg = C.load_config(home, getattr(args, "set", []))
    db = _state_db_for(home, cfg)
    if not db.exists():
        print(f"No progress yet for pack {cfg.pack!r} (nothing run there so far).")
        return 0
    store = ST.Store(db)
    counts_before = store.counts()
    n_err = counts_before.get("error", 0)
    if n_err == 0:
        print(f"No errored expressions for pack {cfg.pack!r} - nothing to retry.")
        store.close()
        return 0
    pattern = args.filter or ""
    if getattr(args, "dry_run", False):
        where = "status='error'"
        params = []
        if pattern:
            where += " AND instr(lower(error), lower(?))"
            params.append(pattern)
        n = store.conn.execute(f"SELECT COUNT(*) FROM alphas WHERE {where}", params).fetchone()[0]
        store.close()
        print(f"Dry run: {n} errored expression(s) would be reset to pending{f' matching {pattern!r}' if pattern else ''}.")
        return 0
    n = store.retry_errors(pattern=pattern, reset_attempts=args.reset_attempts)
    store.close()
    if n == 0:
        if pattern:
            print(f"No error rows matched filter {pattern!r}. Try without --filter to retry all.")
        else:
            print("No rows were reset (all errors may have exhausted max_attempts already).")
    else:
        label = f" matching {pattern!r}" if pattern else ""
        print(f"Reset {n} errored expression(s){label} back to pending for pack {cfg.pack!r}.")
        if args.reset_attempts:
            print("  (attempt counters zeroed - each gets the full budget again)")
        print("  Now run `alphapilot run` to re-simulate them.")
    return 0


def cmd_menu(args):
    from . import agent_cli

    return agent_cli.main(args.home)


def cmd_chat(args):
    """Optional free-form AI chat; the standard CLI never starts this implicitly."""
    from . import agent_cli

    return agent_cli.chat_main(args.home)


def cmd_legacy_menu(args):
    """Compatibility entrypoint for the former numbered workflow menu."""
    from . import menu
    return menu.main_menu(args.home)


def cmd_jump(args):
    home = _resolve_home(args)
    cfg = C.load_config(home, args.set)
    db = _state_db_for(home, cfg)
    store = ST.Store(db)
    try:
        pack, pool, r = _ensure_pool(home, cfg, store)
    except ST.StateError as e:
        say(str(e))
        store.close()
        return 1

    if args.n <= 0:
        n = store.unskip_all()
        say(f"pack {cfg.pack!r}: un-skipped {n} expression(s) - the whole pool is claimable again from the start.")
    else:
        total = store.pool_size()
        if args.n > total:
            say(f"pool only has {total} expressions - nothing to skip past #{args.n}.")
            store.close()
            return 1
        n = store.skip_before(args.n)
        say(f"pack {cfg.pack!r}: skipped {n} still-pending expression(s) before #{args.n} "
            f"(anything already simulated/errored/submitted was left untouched).")
        say(f"next `alphapilot run` for this pack will start from #{args.n} of {total}.")
    store.close()
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="alphapilot", description="Deterministic CLI and resumable WorldQuant BRAIN alpha workflow; optional AI chat is available with `chat`.")
    p.add_argument("--home", default=None, help="state directory (default: $ALPHAPILOT_HOME or ./data)")
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("menu", help="interactive deterministic command shell (default when run with no command)")
    sp.set_defaults(func=cmd_menu)

    sp = sub.add_parser("chat", help="optional AI research chat (requires a configured chat model)")
    sp.set_defaults(func=cmd_chat)

    sp = sub.add_parser("legacy-menu", help="open the original numbered workflow menu")
    sp.set_defaults(func=cmd_legacy_menu)

    sp = sub.add_parser("init", help="create the home directory and a default config.yaml")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("login", help="store BRAIN email/password locally")
    sp.set_defaults(func=cmd_login)

    sp = sub.add_parser("packs", help="list available dataset packs")
    sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set pack=my_pack")
    sp.set_defaults(func=cmd_packs)

    sp = sub.add_parser("doctor", help="verify session, fields, operators, and run one smoke-test simulation")
    sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set pack=my_pack")
    sp.add_argument("--check-model", action="store_true", help="also check the optional AI metadata provider")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("run", help="simulate the pool and (per submit.mode) submit alphas - resumable")
    sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set submit.mode=auto")
    sp.add_argument("--focus", default=None,
                    help="comma-separated, in run order: field ids, 'combo' (2+ fields mixed) or 'combo:<field>'. "
                         "e.g. --focus oth176_eq_medium,oth176_malta_eq_score,combo")
    sp.add_argument("--stop-after", type=int, default=None, dest="stop_after",
                    help="stop the whole run after this many submissions (0 = no limit)")
    sp.add_argument("--resume", action="store_true", help="resume saved progress (the default run behavior)")
    run_modes = sp.add_mutually_exclusive_group()
    run_modes.add_argument("--simulate", action="store_const", const="simulate", dest="run_mode",
                           help="simulate only; do not submit")
    run_modes.add_argument("--submit", action="store_const", const="submit", dest="run_mode",
                           help="simulate and ask before each eligible submission")
    run_modes.add_argument("--dry-run", action="store_const", const="dry-run", dest="run_mode",
                           help="simulate and report what would be submitted")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("fields", help="per-field progress (pending / simulated / submitted) to help pick a focus")
    sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set pack=my_pack")
    sp.add_argument("--field", default=None, help="show only this field or combo")
    sp.set_defaults(func=cmd_fields)

    sp = sub.add_parser("status", help="show progress: counts, top alphas, recent errors")
    sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set pack=my_pack")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("submissions", help="list everything submitted so far")
    sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set pack=my_pack")
    sp.set_defaults(func=cmd_submissions)

    sp = sub.add_parser("errors", help="show recent error records and grouped error diagnostics")
    sp.add_argument("--limit", type=int, default=20, help="maximum recent error records")
    sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set pack=my_pack")
    sp.set_defaults(func=cmd_errors)

    for cmd_alias in ("candidates", "review"):
        sp = sub.add_parser(cmd_alias, help="review eligible candidates by field, check status, or submit")
        sp.add_argument("--field", default=None, help="field name or 'combo' to list (default: summary of all fields)")
        sp.add_argument("--eligible", action="store_true", help="list eligible candidates across fields")
        sp.add_argument("--limit", type=int, default=25, help="max candidates to display (default: 25)")
        sp.add_argument("--check", action="store_true", help="re-check correlation and platform status on BRAIN")
        sp.add_argument("--submit", action="store_true", help="submit the top passing candidate in this field")
        sp.add_argument("--candidate", type=int, default=None, help="1-based candidate number for a detail action")
        sp.add_argument("--candidate-action", choices=("inspect", "check", "submit", "fail", "manual_active"), default=None)
        sp.add_argument("--reason", default=None, help="reason used by candidate-action=fail")
        sp.add_argument("--min-sharpe", type=float, default=None, dest="min_sharpe", help="override min Sharpe cutoff")
        sp.add_argument("--min-fitness", type=float, default=None, dest="min_fitness", help="override min Fitness cutoff")
        sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set pack=my_pack")
        sp.set_defaults(func=cmd_candidates)

    sp = sub.add_parser("jump", help="skip ahead in the pool (or --n 0 to un-skip and include everything again)")
    sp.add_argument("n", type=int, help="1-based alpha number to start from, e.g. 520; 0 = reset to the start")
    sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set pack=my_pack")
    sp.set_defaults(func=cmd_jump)

    sp = sub.add_parser("reset", help="clear local simulation progress while retaining submitted records and history")
    sp.add_argument("--yes", action="store_true")
    sp.add_argument("--preview", action="store_true", help="show reset scope without changing progress")
    sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set pack=my_pack")
    sp.set_defaults(func=cmd_reset)

    sp = sub.add_parser(
        "retry-errors",
        help="reset errored expressions back to pending so they are re-simulated on the next `run` "
             "(useful when errors are transient server-side failures)",
    )
    sp.add_argument(
        "--filter", default="", metavar="TEXT",
        help="only retry errors whose message contains TEXT (case-insensitive). "
             "e.g. --filter 'server error'  or  --filter '504'",
    )
    sp.add_argument(
        "--reset-attempts", action="store_true", dest="reset_attempts",
        help="also zero the attempt counter so each expression gets the full max_attempts budget again "
             "(by default the existing count is kept)",
    )
    sp.add_argument("--dry-run", action="store_true", dest="dry_run", help="count matching errors without changing state")
    sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set pack=my_pack")
    sp.set_defaults(func=cmd_retry)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        # A bare invocation is an interactive entrypoint only when a terminal
        # is available.  In scripts/pipes, print the command reference rather
        # than starting a prompt that cannot receive input.
        if not sys.stdin.isatty():
            parser.print_help()
            return 0
        args.func = cmd_menu
    try:
        return args.func(args) or 0
    except C.ConfigError as e:
        print(f"Config error:\n{e}", file=sys.stderr)
        return 1
    except P.PackError as e:
        print(f"Pack error:\n{e}", file=sys.stderr)
        return 1
    except BC.BrainError as e:
        mark = Theme.symbol("✕", "x")
        print(f"{Theme.paint(mark + ' BRAIN error', 'error')}\n  {e}", file=sys.stderr)
        return 1
    except (OSError, TimeoutError) as e:
        print(f"{Theme.paint('✕ Connection problem', 'error')}\n  {e}\n  Check the network and API configuration, then retry.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(f"{Theme.paint('! Operation cancelled', 'warning')}", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
