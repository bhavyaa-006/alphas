"""Interactive, menu-based front end. `alphapilot` with no arguments (or
`alphapilot menu`) lands here; every other `alphapilot <command>` still works
directly for scripting/Docker/cron use - this menu just calls the same
functions."""
from __future__ import annotations

import argparse
from pathlib import Path

from . import cli as C
from . import config as CFG
from . import packs_api as PA
from . import state as ST
from .util import banner, say


def _args(home, **extra):
    ns = argparse.Namespace(home=str(home), set=[])
    for k, v in extra.items():
        setattr(ns, k, v)
    return ns


def _pause():
    input("\nPress Enter to return to the menu... ")


def _prompt_choice(title, options, allow_back=True):
    print(f"\n{title}")
    for i, (label, _) in enumerate(options, 1):
        print(f"  {i}) {label}")
    if allow_back:
        print("  0) Back")
    while True:
        raw = input("> ").strip()
        if allow_back and raw == "0":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][1]
        print("Please enter a number from the list.")


def _quick_setup(home: Path):
    banner(["Quick setup"])
    C.cmd_init(_args(home))
    C.cmd_login(_args(home))
    print("\nRunning `doctor` to verify everything before a real run...")
    C.cmd_doctor(_args(home, set=[]))
    _pause()


def _pick_focus(home: Path, cfg):
    """Returns (focus_list, cancelled). Empty list = no filter (whole pool)."""
    store = ST.Store(C._state_db_for(home, cfg))
    try:
        pack, _pool, _ = C._ensure_pool(home, cfg, store)
        counts = store.focus_counts(pack.field_ids())
    finally:
        store.close()
    names = [*pack.field_ids(), "combo"]
    saved = PA.normalize_focus(cfg["run"].get("focus"))
    print("\nWhich field(s) to run, and in what order?")
    print(f"  {'':<4}{'field':<30}{'pending':>8}{'simulated':>10}{'submitted':>10}")
    for i, name in enumerate(names, 1):
        c = counts[name]
        label = name if name != "combo" else "COMBOS (any mix of 2+ fields)"
        print(f"  {i:>2}) {label:<30}{c['pending']:>8}{c['simulated']:>10}{c['submitted']:>10}")
    print("   0) Everything (no filter, normal pool order)")
    print("\nType numbers in the order to run them, e.g.  3,1,7   (only these run; the rest is left untouched)")
    if saved:
        print(f"Press Enter to use your saved focus: {', '.join(saved)}")
    else:
        print("Press Enter for everything.")
    while True:
        raw = input("> ").strip()
        if raw == "":
            return saved, False
        if raw == "0":
            return [], False
        try:
            idx = [int(x) for x in raw.replace(" ", "").split(",") if x]
        except ValueError:
            idx = []
        if idx and all(1 <= i <= len(names) for i in idx):
            return PA.normalize_focus([names[i - 1] for i in idx]), False
        print("Please enter numbers from the list separated by commas (or 0 / Enter).")


def _run_screen(home: Path):
    cfg = CFG.load_config(home)
    print(f"\nCurrent: pack={cfg.pack}  pool_size={cfg.simulation.pool_size}  "
          f"batch_size={cfg.simulation.batch_size}  submit.mode={cfg.submit.mode}  "
          f"submit.max_per_run={cfg.submit.max_per_run}  submit.max_per_day={cfg.submit.max_per_day}")
    try:
        focus, _ = _pick_focus(home, cfg)
    except Exception as e:
        print(f"\n!! could not load the pack/fields: {e}")
        _pause()
        return

    raw = input(f"\nStop the run after how many submissions? [Enter = {cfg.submit.max_per_run}, 0 = no limit]: ").strip()
    stop_after = int(raw) if raw.isdigit() else int(cfg.submit.max_per_run)

    choice = _prompt_choice("Run with...", [
        (f"Configured submit mode ({cfg.submit.mode})", "asis"),
        ("Simulate only, no submissions (submit.mode=off)", "off"),
        ("Simulate + submit automatically (submit.mode=auto)", "auto"),
        ("Simulate + ask before each submission (submit.mode=ask)", "ask"),
        ("Dry run (simulate + show what WOULD be submitted, nothing sent)", "dry"),
    ])
    if choice is None:
        return
    overrides = [] if choice == "asis" else [f"submit.mode={choice}"]
    mode = cfg.submit.mode if choice == "asis" else choice
    if mode in ("ask", "auto") and stop_after > int(cfg.submit.max_per_day):
        yn = input(f"submit.max_per_day is {cfg.submit.max_per_day}, so the run would stop at that many per day. "
                   f"Raise it to {stop_after} for this run? [y/N] ").strip().lower()
        if yn == "y":
            overrides.append(f"submit.max_per_day={stop_after}")
    print(f"\n>> focus: {' -> '.join(focus) if focus else 'everything'}   stop after: {stop_after or 'no limit'} submission(s)\n")
    rc = C.cmd_run(_args(home, set=overrides, focus=focus, stop_after=stop_after))
    print(f"\n(exit code {rc})")
    _pause()


def _fields_screen(home: Path):
    C.cmd_fields(_args(home))
    _pause()


def _status_screen(home: Path):
    C.cmd_status(_args(home))
    _pause()


def _errors_screen(home: Path):
    store = ST.Store(C._state_db_for(home, CFG.load_config(home)))
    summary = store.error_summary(15)
    store.close()
    banner(["Error breakdown (grouped by message)"])
    if not summary:
        print("No errors recorded.")
    else:
        for row in summary:
            print(f"\n  x{row['count']:<4} {row['example'][:200]}")
        print(
            "\nNote: if one message repeats a LOT, it is very likely a daily/rate "
            "limit rather than a broken expression - alphapilot now stops the run "
            "automatically after simulation.error_streak_halt (default 20) similar "
            "failures in a row instead of burning through the rest of the pool."
        )
    _pause()


def _retry_screen(home: Path):
    """Interactively reset errored expressions back to pending."""
    cfg = CFG.load_config(home)
    db = C._state_db_for(home, cfg)
    if not db.exists():
        print(f"No progress yet for pack {cfg.pack!r}.")
        _pause()
        return
    store = ST.Store(db)
    n_err = store.counts().get("error", 0)
    summary = store.error_summary(10)
    store.close()
    if n_err == 0:
        print(f"\nNo errored expressions for pack {cfg.pack!r} - nothing to retry.")
        _pause()
        return
    banner([f"Retry errors  ({n_err} errored expression(s))"])
    if summary:
        print("Top error groups:")
        for row in summary:
            print(f"  x{row['count']:<4} {row['example'][:140]}")
    print()
    choice = _prompt_choice("Retry options", [
        (f"Retry ALL {n_err} errored expression(s)", "all"),
        ("Retry only errors matching a keyword (e.g. '504', 'server error')", "filter"),
    ])
    if choice is None:
        return
    pattern = ""
    if choice == "filter":
        pattern = input("  Filter text (case-insensitive substring of error message): ").strip()
        if not pattern:
            print("  No filter entered, cancelling.")
            _pause()
            return
    reset_att = input("  Also reset attempt counters? This gives each expression the full retry budget again. [y/N] ").strip().lower() == "y"
    store = ST.Store(db)
    n = store.retry_errors(pattern=pattern, reset_attempts=reset_att)
    store.close()
    if n == 0:
        print(f"  No rows matched{' filter ' + repr(pattern) if pattern else ''} - nothing changed.")
    else:
        label = f" matching {pattern!r}" if pattern else ""
        print(f"  Reset {n} expression(s){label} back to pending.")
        if reset_att:
            print("  (attempt counters zeroed)")
        print("  Run 'Run' from the main menu (or `alphapilot run`) to re-simulate them.")
    _pause()


def _candidates_screen(home: Path):
    """Interactive candidate review & submission by field."""
    cfg = CFG.load_config(home)
    db = C._state_db_for(home, cfg)
    if not db.exists():
        print(f"No progress yet for pack {cfg.pack!r}.")
        _pause()
        return

    store = ST.Store(db)
    try:
        pack, _pool, _ = C._ensure_pool(home, cfg, store)
        field_ids = pack.field_ids()
    except Exception as e:
        print(f"\n!! could not load pack {cfg.pack!r}: {e}")
        store.close()
        _pause()
        return

    session_holder = {"s": None, "ace": None}

    def get_session():
        if session_holder["s"] is None:
            import ace_lib as ace
            say("Connecting session to BRAIN...")
            s = C.BC.ensure_session(
                ace, cfg, home,
                on_persona_link=lambda u: say(f"Face check needed: {u}"),
                on_waiting=lambda a, r: say(f"waiting... ({C.fmt_duration(r)} left)"),
            )
            C.BC.install_into(
                ace, cfg, home,
                on_persona_link=lambda u: say(f"Face check needed: {u}"),
                on_waiting=lambda a, r: say(f"waiting... ({C.fmt_duration(r)} left)"),
            )
            session_holder["ace"] = ace
            session_holder["s"] = s
        return session_holder["ace"], session_holder["s"]

    try:
        while True:
            min_sh = cfg.submit.min_sharpe
            min_fit = cfg.submit.min_fitness
            counts = store.candidate_counts_by_field(field_ids, min_sh, min_fit)
            names = [*field_ids, "combo"]

            banner([
                f"Candidate Review · pack={pack.name}",
                f"Eligible: sharpe >= {min_sh}  fitness >= {min_fit}  (no failed IS tests)",
            ])
            print(f"  {'':<4}{'field':<32}{'candidates':>10}{'unsure/pending':>16}{'passed check':>14}")
            for i, name in enumerate(names, 1):
                c = counts.get(name, {"total": 0, "unsure": 0, "pass": 0})
                label = name if name != "combo" else "COMBOS (any mix of 2+ fields)"
                print(f"  {i:>2}) {label:<32}{c['total']:>10}{c['unsure']:>16}{c['pass']:>14}")
            tot = counts.get("all", {"total": 0, "unsure": 0, "pass": 0})
            print(f"   0) {'All fields':<32}{tot['total']:>10}{tot['unsure']:>16}{tot['pass']:>14}")

            print("\nEnter field number to inspect (or 0 for All, q to return):")
            raw = input("> ").strip().lower()
            if raw in ("q", "back", "exit", ""):
                break
            if raw == "0":
                selected_field = None
                field_label = "All fields"
            elif raw.isdigit() and 1 <= int(raw) <= len(names):
                selected_field = names[int(raw) - 1]
                field_label = selected_field if selected_field != "combo" else "COMBOS"
            else:
                print("Invalid choice.")
                continue

            while True:
                cands = store.get_candidates(min_sh, min_fit, field=selected_field, limit=30)
                if not cands:
                    print(f"\nNo eligible candidates in {field_label}.")
                    _pause()
                    break

                banner([f"Candidates: {field_label} ({len(cands)} shown, sorted by fitness/sharpe)"])
                print(f"  {'#':<3}{'alpha_id':<14}{'sharpe':>7}{'fitness':>9}{'turnover':>10}{'check':>10}  expression")
                for i, c in enumerate(cands, 1):
                    chk = c.check_result or "-"
                    expr_snip = c.expr[:55] + ("..." if len(c.expr) > 55 else "")
                    print(f"  {i:>2}) {c.alpha_id or '-':<14}{c.sharpe or 0:>7.2f}{c.fitness or 0:>9.2f}{c.turnover or 0:>10.2f}{chk:>10}  {expr_snip}")

                print("\nOptions:")
                print("  1-N) Inspect & submit candidate #")
                print("    c) Check all unverified candidates on BRAIN platform")
                print("    s) Submit top candidate in this list")
                print("    0) Back to field list")

                act = input("> ").strip().lower()
                if act in ("0", "b", "back", "q", ""):
                    break
                elif act == "c":
                    try:
                        ace, s = get_session()
                    except Exception as e:
                        print(f"!! could not connect to BRAIN: {e}")
                        _pause()
                        continue
                    say(f"Checking {len(cands)} candidate(s) on BRAIN platform...")
                    for c in cands:
                        st, msg = C.E.check_candidate_platform(ace, s, c, store, cfg)
                        say(f"  {c.alpha_id}  sharpe={c.sharpe}  status={st}  ({msg})")
                    _pause()
                elif act == "s":
                    top = cands[0]
                    yn = input(f"Submit top candidate {top.alpha_id} (sharpe={top.sharpe}, fitness={top.fitness})? [y/N] ").strip().lower()
                    if yn == "y":
                        try:
                            ace, s = get_session()
                            say(f"Submitting {top.alpha_id}...")
                            ok, msg = C.E.submit_candidate_now(ace, s, cfg, pack, store, top)
                            say(f"Result: {msg}")
                        except Exception as e:
                            print(f"!! submission error: {e}")
                        _pause()
                elif act.isdigit() and 1 <= int(act) <= len(cands):
                    cand = cands[int(act) - 1]
                    while True:
                        banner([f"Candidate Details · {cand.alpha_id}"])
                        print(f"  alpha_id:     {cand.alpha_id}")
                        print(f"  URL:          https://platform.worldquantbrain.com/alpha/{cand.alpha_id}")
                        print(f"  fields:       {cand.fields or '-'}")
                        print(f"  sharpe:       {cand.sharpe}    fitness:  {cand.fitness}    turnover: {cand.turnover}")
                        print(f"  margin:       {cand.margin}    returns:  {cand.returns}")
                        print(f"  check_result: {cand.check_result or 'not checked yet'}")
                        if cand.check_detail:
                            print(f"  check_detail: {cand.check_detail}")
                        print(f"  expression:\n    {cand.expr}\n")

                        sub_choice = _prompt_choice("Action", [
                            ("Check platform status & correlation on BRAIN", "check"),
                            ("Submit to BRAIN now", "submit"),
                            ("Mark as check_fail (skip from candidates)", "fail"),
                            ("Mark as submitted outside alphapilot", "manual_active"),
                        ])
                        if sub_choice is None:
                            break
                        if sub_choice == "check":
                            try:
                                ace, s = get_session()
                                st, msg = C.E.check_candidate_platform(ace, s, cand, store, cfg)
                                say(f"Result: status={st}  ({msg})")
                            except Exception as e:
                                print(f"!! error: {e}")
                            _pause()
                            break
                        elif sub_choice == "submit":
                            try:
                                ace, s = get_session()
                                ok, msg = C.E.submit_candidate_now(ace, s, cfg, pack, store, cand)
                                say(f"Result: {msg}")
                            except Exception as e:
                                print(f"!! error: {e}")
                            _pause()
                            break
                        elif sub_choice == "fail":
                            reason = input("Reason for rejection: ").strip() or "manually skipped"
                            store.mark_check(cand.expr, "FAIL", reason)
                            print(f"Marked {cand.alpha_id} as check_fail.")
                            _pause()
                            break
                        elif sub_choice == "manual_active":
                            store.mark_submitted(cand.expr, cand.alpha_id, "(manual active)", "", "manual", cfg.submit.timezone)
                            print(f"Marked {cand.alpha_id} as submitted.")
                            _pause()
                            break
    finally:
        store.close()


def _submissions_screen(home: Path):
    C.cmd_submissions(_args(home))
    _pause()


def _settings_screen(home: Path):
    while True:
        cfg = CFG.load_config(home)
        print(f"\npack={cfg.pack}")
        print(f"simulation: pool_size={cfg.simulation.pool_size}  batch_size={cfg.simulation.batch_size}  "
              f"error_streak_halt={cfg.simulation.error_streak_halt}")
        print(f"submit: mode={cfg.submit.mode}  max_per_day={cfg.submit.max_per_day}  max_per_run={cfg.submit.max_per_run}")
        print(f"saved focus: {cfg['run'].get('focus') or '(none - whole pool)'}")
        print(f"llm: provider={cfg.llm.provider}  model={cfg.llm.model or '(default)'}  fallback={cfg.llm.fallback}")
        choice = _prompt_choice("Settings", [
            ("Change pack", "pack"),
            ("Change submit.mode", "submit_mode"),
            ("Change submit.max_per_day", "max_per_day"),
            ("Change submit.max_per_run (stop run after N submissions, 0 = no limit)", "max_per_run"),
            ("Change saved field focus (used when you press Enter in the Run screen)", "focus"),
            ("Change llm.provider", "llm_provider"),
            ("Edit config.yaml directly (opens the path)", "edit"),
            ("Set any key=value", "raw"),
        ])
        if choice is None:
            return
        data = dict(cfg)
        if choice == "pack":
            dirs = C._pack_dirs(Path(C.__file__).resolve(), home)
            try:
                active_key = PA.resolve_pack(cfg.pack, dirs).key
            except PA.PackError:
                active_key = None
            found = PA.list_pack_infos(dirs)
            options = []
            for i in found:
                if i.shadowed_by:
                    print(f"  (ignoring {i.path}: an earlier folder already has a pack with that file name)")
                    continue
                if i.error:
                    print(f"  (skipping {i.key}: failed to load - {i.error.splitlines()[0]})")
                    continue
                db = C._state_db_path(home, i.key)
                tag = " (active)" if i.key == active_key else (" [has progress]" if db.exists() else "")
                dup = f"  !! same PACK_NAME as {', '.join(i.same_name_as)}" if i.same_name_as else ""
                options.append((f"{i.key}{tag} - {i.description}{dup}", i.key))
            if not options:
                print("\nNo packs found. Drop a pack .py file in packs/ (or data/packs/) and try again.")
                _pause()
                continue
            val = _prompt_choice("Choose a pack", options)
            if val:
                data["pack"] = val
                print(f"\nSwitched to {val!r}. Its progress (if any) is separate from other packs - "
                      f"nothing was lost or merged.")
        elif choice == "submit_mode":
            val = _prompt_choice("submit.mode", [(m, m) for m in CFG.SUBMIT_MODES], allow_back=True)
            if val:
                data["submit"]["mode"] = val
        elif choice == "max_per_day":
            val = input("submit.max_per_day (integer): ").strip()
            if val.isdigit():
                data["submit"]["max_per_day"] = int(val)
        elif choice == "max_per_run":
            val = input("submit.max_per_run (integer, 0 = no limit): ").strip()
            if val.isdigit():
                data["submit"]["max_per_run"] = int(val)
        elif choice == "focus":
            val = input("focus, comma-separated in order (field ids, combo, combo:<field>; blank = none): ").strip()
            data.setdefault("run", {})["focus"] = PA.normalize_focus(val)
        elif choice == "llm_provider":
            val = _prompt_choice("llm.provider", [(p, p) for p in CFG.LLM_PROVIDERS], allow_back=True)
            if val:
                data["llm"]["provider"] = val
        elif choice == "edit":
            print(f"\nEdit this file, then come back: {CFG.config_path(home)}")
            _pause()
            continue
        elif choice == "raw":
            kv = input("key.path=value: ").strip()
            if kv:
                data = CFG.deep_merge(data, CFG.parse_overrides([kv]))
        problems = CFG.validate(data)
        if problems:
            print("\n!! not saved, invalid:")
            for p in problems:
                print(" -", p)
            _pause()
            continue
        CFG.save_file_config(home, data)
        print("saved.")


def _reset_screen(home: Path):
    C.cmd_reset(_args(home, yes=False))
    _pause()



def _jump_screen(home: Path):
    cfg = CFG.load_config(home)
    db = C._state_db_for(home, cfg)
    total = None
    if db.exists():
        store = ST.Store(db)
        total = store.pool_size()
        c = store.counts()
        store.close()
        print(f"\npack: {cfg.pack}   pool size: {total}   current progress: {c}")
    else:
        print(f"\npack: {cfg.pack}   (no pool built yet - one will be built now, without simulating)")

    print(
        "\nStart from the Nth alpha: everything before it that is still PENDING gets "
        "skipped (not simulated). Anything already simulated, errored, or submitted is "
        "never touched or lost. Enter 0 to undo this and include everything again."
    )
    raw = input("Start from # (0 = reset to include everything): ").strip()
    if not raw.isdigit():
        print("cancelled")
        return
    C.cmd_jump(_args(home, set=[], n=int(raw)))
    _pause()


def main_menu(home_arg=None):
    home = CFG.resolve_home(home_arg)
    while True:
        cfg_exists = CFG.config_path(home).exists()
        banner(["alphapilot", f"home: {home}"])
        if not cfg_exists:
            print("(not set up yet - start with Quick setup)")
        else:
            try:
                cfg = CFG.load_config(home)
                db = C._state_db_for(home, cfg)
                try:
                    _info = PA.resolve_pack(cfg.pack, C._pack_dirs(Path(C.__file__).resolve(), home))
                    print(f"active pack: {_info.key}   ({_info.path})")
                except PA.PackError as _e:
                    print(f"active pack: {cfg.pack}   !! {str(_e).splitlines()[0]}")
                if db.exists():
                    store = ST.Store(db)
                    print(f"progress: {store.counts()}")
                    store.close()
                else:
                    print("progress: (not started yet for this pack)")
            except Exception:
                pass

        choice = _prompt_choice("Main menu", [
            ("Quick setup (init + login + doctor)", "setup"),
            ("Run (simulate / submit - resumable)", "run"),
            ("Candidates (review & submit eligible alphas by field)", "candidates"),
            ("Status", "status"),
            ("Fields (per-field progress)", "fields"),
            ("View errors", "errors"),
            ("Retry errors (reset failed simulations back to pending)", "retry"),
            ("Submissions history", "submissions"),
            ("Jump to alpha # (skip ahead / reset)", "jump"),
            ("Settings (pack, submit mode, LLM provider, ...)", "settings"),
            ("Doctor (diagnostics)", "doctor"),
            ("Reset progress", "reset"),
            ("Exit", "exit"),
        ], allow_back=False)

        try:
            if choice == "setup":
                _quick_setup(home)
            elif choice == "run":
                _run_screen(home)
            elif choice == "candidates":
                _candidates_screen(home)
            elif choice == "status":
                _status_screen(home)
            elif choice == "fields":
                _fields_screen(home)
            elif choice == "errors":
                _errors_screen(home)
            elif choice == "retry":
                _retry_screen(home)
            elif choice == "submissions":
                _submissions_screen(home)
            elif choice == "jump":
                _jump_screen(home)
            elif choice == "settings":
                _settings_screen(home)
            elif choice == "doctor":
                C.cmd_doctor(_args(home, set=[]))
                _pause()
            elif choice == "reset":
                _reset_screen(home)
            elif choice == "exit":
                print("Bye.")
                return 0
        except KeyboardInterrupt:
            print("\n(interrupted - back to menu)")
        except Exception as e:
            print(f"\n!! {type(e).__name__}: {e}")
            _pause()
