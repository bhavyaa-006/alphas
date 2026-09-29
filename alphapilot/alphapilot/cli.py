from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import config as C
from . import engine as E
from . import llm as LLM
from . import packs_api as P
from . import secrets as SEC
from . import state as ST
from . import brain_client as BC
from .util import banner, say, setup_logging, fmt_duration, in_docker


def _pack_dirs(here: Path, home: Path):
    # here = .../alphapilot/alphapilot/cli.py -> repo root is two levels up
    repo_root = here.parent.parent
    return [home / "packs", repo_root / "packs"]


def _state_db_path(home: Path, pack_name: str) -> Path:
    """Each pack gets its own state.db under <home>/state/, so switching packs
    (or trying several) never collides with another pack's progress."""
    d = home / "state"
    d.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in pack_name)
    return d / f"{safe}.db"


def _load_pack_and_pool(home: Path, cfg):
    pack = P.load_pack(cfg.pack, _pack_dirs(Path(__file__).resolve(), home))
    pool = pack.build(cfg.simulation.seed, cfg.simulation.pool_size)
    return pack, pool


def _ensure_pool(home: Path, cfg, store: ST.Store):
    """Builds the pool from the pack and registers it in `store` (idempotent -
    safe to call every time; only inserts rows that don't exist yet)."""
    from .util import sha256_json

    pack, pool = _load_pack_and_pool(home, cfg)
    pack_hash = sha256_json({"fields": pack.fields, "settings": pack.settings, "ops": sorted(pack.allowed_operators)})
    r = store.init_pool(pack.name, pack_hash, cfg.simulation.seed, cfg.simulation.pool_size, pool)
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
    here = Path(__file__).resolve()
    for name, desc, path, err in P.list_packs(_pack_dirs(here, home)):
        if err:
            print(f"  !! {name:<20} FAILED TO LOAD: {err.splitlines()[0]}")
        else:
            print(f"  {name:<20} {desc}\n      ({path})")


def cmd_doctor(args):
    import ace_lib as ace

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

    say("5. checking LLM description provider ...")
    res = LLM.preflight(cfg)
    say(("   OK  " if res["ok"] else "   !! ") + f"{res['provider']}: {res['detail']}")

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
    print(f"(using --home: {home})")
    return home


def cmd_run(args):
    import ace_lib as ace

    home = _resolve_home(args)
    cfg = C.load_config(home, args.set)
    # one-off overrides from the CLI flags / menu (not saved to config.yaml)
    if getattr(args, "focus", None) is not None:
        cfg["run"]["focus"] = P.normalize_focus(args.focus)
    if getattr(args, "stop_after", None) is not None:
        cfg["submit"]["max_per_run"] = int(args.stop_after)
    setup_logging(home / "alphapilot.log", cfg.logging.verbose)
    SEC.ensure_credentials(home)

    store = ST.Store(_state_db_path(home, cfg.pack))
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

    s = BC.ensure_session(ace, cfg, home, on_persona_link=lambda u: say(f"Face check needed: {u}"), on_waiting=lambda a, r: say(f"waiting for face check... ({fmt_duration(r)} left)"))
    BC.install_into(ace, cfg, home, on_persona_link=lambda u: say(f"Face check needed: {u}"), on_waiting=lambda a, r: say(f"waiting... ({fmt_duration(r)} left)"))

    def ask_fn(cand, meta):
        print(f"\nSubmit {cand.alpha_id}? sharpe={cand.sharpe} fitness={cand.fitness}")
        print(f"  name: {meta.name}  category: {meta.category}")
        print(f"  {meta.description[:300]}...")
        return input("  Submit? [y/N] ").strip().lower() == "y"

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
    try:
        while not store.is_done(focus):
            total_batches_run += 1
            _batch_num = total_batches_run  # capture now; default arg avoids late-binding closure bug
            def on_progress(rs, counts, _n=_batch_num):
                say(f"batch {_n}: ok={rs.simulated_ok} err={rs.simulated_err}  |  pool: {counts}")

            E.run_simulation_batches(ace, s, cfg, pack, store, on_progress=on_progress, max_batches=1, focus=focus)
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
        return 2
    except KeyboardInterrupt:
        say("\nInterrupted - progress is saved. Re-run `alphapilot run` to continue.")
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
    store = ST.Store(_state_db_path(home, cfg.pack))
    try:
        pack, pool, _ = _ensure_pool(home, cfg, store)
        counts = store.focus_counts(pack.field_ids())
    finally:
        store.close()
    print(f"pack: {pack.name}")
    print(f"  {'field / group':<32} pending  simulated  submitted  error")
    for name in [*pack.field_ids(), "combo"]:
        c = counts[name]
        label = name if name != "combo" else "combo (2+ fields mixed)"
        print(f"  {label:<32} {c['pending']:>7}  {c['simulated']:>9}  {c['submitted']:>9}  {c['error']:>5}")
    return 0


def cmd_status(args):
    home = _resolve_home(args)
    cfg = C.load_config(home, getattr(args, "set", []))
    db = _state_db_path(home, cfg.pack)
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


def cmd_submissions(args):
    home = _resolve_home(args)
    cfg = C.load_config(home, getattr(args, "set", []))
    db = _state_db_path(home, cfg.pack)
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
    db = _state_db_path(home, cfg.pack)
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

    if do_check or do_submit:
        import ace_lib as ace
        s = BC.ensure_session(ace, cfg, home, on_persona_link=lambda u: say(f"Face check needed: {u}"), on_waiting=lambda a, r: say(f"waiting... ({fmt_duration(r)} left)"))
        BC.install_into(ace, cfg, home, on_persona_link=lambda u: say(f"Face check needed: {u}"), on_waiting=lambda a, r: say(f"waiting... ({fmt_duration(r)} left)"))

        if do_check:
            say(f"Checking {len(cands)} candidate(s) against BRAIN platform...")
            for c in cands:
                st, msg = E.check_candidate_platform(ace, s, c, store, cfg)
                say(f"  {c.alpha_id}  sharpe={c.sharpe}  status={st}  ({msg})")
            store.close()
            return 0

        if do_submit:
            cand = cands[0]
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
    db = _state_db_path(home, cfg.pack)
    if not args.yes:
        if input(f"Delete {db}? This forgets all simulation/submission progress for pack {cfg.pack!r} "
                 f"(does NOT touch anything already submitted to BRAIN). [y/N] ").strip().lower() != "y":
            print("cancelled")
            return 0
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db) + suffix)
        if p.exists():
            p.unlink()
    print("state cleared:", db)


def cmd_retry(args):
    """Reset errored expressions back to pending so they are picked up on the next `run`."""
    home = _resolve_home(args)
    cfg = C.load_config(home, getattr(args, "set", []))
    db = _state_db_path(home, cfg.pack)
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
    from . import menu

    return menu.main_menu(args.home)


def cmd_jump(args):
    home = _resolve_home(args)
    cfg = C.load_config(home, args.set)
    db = _state_db_path(home, cfg.pack)
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
    p = argparse.ArgumentParser(prog="alphapilot", description="Resumable WorldQuant BRAIN alpha automation.")
    p.add_argument("--home", default=None, help="state directory (default: $ALPHAPILOT_HOME or ./data)")
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("menu", help="interactive menu (default when run with no command)")
    sp.set_defaults(func=cmd_menu)

    sp = sub.add_parser("init", help="create the home directory and a default config.yaml")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("login", help="store BRAIN email/password locally")
    sp.set_defaults(func=cmd_login)

    sp = sub.add_parser("packs", help="list available dataset packs")
    sp.set_defaults(func=cmd_packs)

    sp = sub.add_parser("doctor", help="verify session, fields, operators, LLM, and run one smoke-test simulation")
    sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set pack=my_pack")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("run", help="simulate the pool and (per submit.mode) submit alphas - resumable")
    sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set submit.mode=auto")
    sp.add_argument("--focus", default=None,
                    help="comma-separated, in run order: field ids, 'combo' (2+ fields mixed) or 'combo:<field>'. "
                         "e.g. --focus oth176_eq_medium,oth176_malta_eq_score,combo")
    sp.add_argument("--stop-after", type=int, default=None, dest="stop_after",
                    help="stop the whole run after this many submissions (0 = no limit)")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("fields", help="per-field progress (pending / simulated / submitted) to help pick a focus")
    sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set pack=my_pack")
    sp.set_defaults(func=cmd_fields)

    sp = sub.add_parser("status", help="show progress: counts, top alphas, recent errors")
    sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set pack=my_pack")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("submissions", help="list everything submitted so far")
    sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set pack=my_pack")
    sp.set_defaults(func=cmd_submissions)

    for cmd_alias in ("candidates", "review"):
        sp = sub.add_parser(cmd_alias, help="review eligible candidates by field, check status, or submit")
        sp.add_argument("--field", default=None, help="field name or 'combo' to list (default: summary of all fields)")
        sp.add_argument("--limit", type=int, default=25, help="max candidates to display (default: 25)")
        sp.add_argument("--check", action="store_true", help="re-check correlation and platform status on BRAIN")
        sp.add_argument("--submit", action="store_true", help="submit the top passing candidate in this field")
        sp.add_argument("--min-sharpe", type=float, default=None, dest="min_sharpe", help="override min Sharpe cutoff")
        sp.add_argument("--min-fitness", type=float, default=None, dest="min_fitness", help="override min Fitness cutoff")
        sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set pack=my_pack")
        sp.set_defaults(func=cmd_candidates)

    sp = sub.add_parser("jump", help="skip ahead in the pool (or --n 0 to un-skip and include everything again)")
    sp.add_argument("n", type=int, help="1-based alpha number to start from, e.g. 520; 0 = reset to the start")
    sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set pack=my_pack")
    sp.set_defaults(func=cmd_jump)

    sp = sub.add_parser("reset", help="wipe local progress (does NOT touch anything already submitted to BRAIN)")
    sp.add_argument("--yes", action="store_true")
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
    sp.add_argument("--set", action="append", default=[], help="override config, e.g. --set pack=my_pack")
    sp.set_defaults(func=cmd_retry)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
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
        print(f"BRAIN error:\n{e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
