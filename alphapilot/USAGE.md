# USAGE — the complete guide

Everything you need to run alphapilot day to day, without needing to ask me
again. If something here turns out wrong once you actually try it, tell me
what happened and I'll fix the tool and this doc together.

---

## 1. One-time setup

You need:
- Docker Desktop installed and running
- WorldQuant's `ACE_API__Gold_` folder (`ace_lib.py`, `helpful_functions.py`, etc.)
- This `alphapilot` folder, unzipped somewhere

```bash
cd alphapilot
cp -r /path/to/ACE_API__Gold_ .        # put it right next to Dockerfile
docker compose build
```

Then, one time only:

```bash
docker compose run --rm alphapilot init      # creates ./data/config.yaml
docker compose run --rm alphapilot login     # asks for BRAIN email/password once
docker compose run --rm alphapilot doctor    # checks session, fields, operators, 1 test simulation
```

`login` will trigger a face-check link the first time (or whenever your
saved session actually expires) — open it, verify, and the terminal picks it
up on its own within a few seconds. This is the exact same manual step you
already know from the browser; alphapilot just doesn't hang forever waiting
for you.

**The one rule that avoids almost every "it's asking again" problem:**
alphapilot's memory (login, progress, settings) lives in `./data`, right
next to `docker-compose.yml`. Always run commands from that same folder.
Every command prints `(using --home: ...)` as its first line — if that path
ever looks different from usual, that's the whole story.

---

## 2. Running it — two ways

### A) One-off (simplest — a fresh container each time, closes when done)

```bash
docker compose run --rm alphapilot            # opens the menu
docker compose run --rm alphapilot run        # runs directly, no menu
docker compose run --rm alphapilot status
```

Fine for occasional use. Each command starts and stops its own container;
your data on `./data` persists regardless.

### B) Permanent / always-on container (stays running in the background)

Use this if you want it available without a fresh container startup every
time, or you plan to leave it running for a while (e.g. letting a long
simulation run continue unattended, or checking in on it periodically).

```bash
docker compose up -d alphapilot-daemon        # starts it, runs in the background
docker compose exec -it alphapilot-daemon alphapilot       # menu (interactive)
docker compose exec alphapilot-daemon alphapilot run
docker compose exec alphapilot-daemon alphapilot status
```

The daemon is an idle container; it does not run simulations by itself. Use
`exec` to launch each command, and keep the terminal open to see its output.
`restart: unless-stopped` only brings that idle container back if Docker
restarts or your machine reboots. To stop it entirely:

```bash
docker compose down
```

Nothing on `./data` is affected by starting/stopping the daemon — your
config, login, and progress are all still there next time.

For a long-running simulation, start this in a terminal and leave it attached
so prompts and progress remain visible:

```bash
docker compose exec alphapilot-daemon alphapilot run
```

If a face check comes up while nobody's watching, alphapilot prints the link
and waits up to `session.persona_timeout_min` minutes (20 by default), then
exits cleanly. Open the link and rerun the command.

### Without Docker at all

```bash
pip install -e .
export PYTHONPATH=/path/to/ACE_API__Gold_
alphapilot          # menu
alphapilot run      # direct
alphapilot chat     # optional model-backed research chat
```

Same commands, same `./data` rule, same everything — just no container
around it.

---

## 3. The interactive command shell

`alphapilot` (or `docker compose run --rm alphapilot` with no extra word)
opens the modern deterministic command shell as a persistent full-screen UI:

```text
┌──────────────────────────────────────────────┐
│  ALPHAS                     (fixed header)   │
├──────────────────────────────────────────────┤
│                                             │
│  dynamic workspace                          │  ← menus, output, help,
│  (scrolls on its own: PgUp/PgDn, wheel,      │    progress, errors, results
│   Shift+arrows)                             │
│                                             │
├──────────────────────────────────────────────┤
│  > input bar              (fixed at bottom)  │
│  status: context · shortcuts                 │
└──────────────────────────────────────────────┘
```

The header and input bar never move; only the middle workspace changes as
commands run. Resize the terminal freely — the layout adapts. The only
slash commands are `/setup`, `/run`, `/candidates`, `/status`, `/fields`,
`/errors`, `/retry`, `/history`, `/jump`, `/settings`, `/doctor`, `/reset`,
and `/exit`. Type `?` or `/` for descriptions and usage examples. For example, `/run --simulate`
runs without submitting and `/candidates --field <field> --submit` follows
the existing eligibility and submission checks. Direct CLI commands remain
available for scripts. Free-form model chat is isolated behind
`alphapilot chat` and can be installed with `pip install -e '.[ai]'`.

After a slash command runs, it becomes the active context. Type `?` to see
only that command's valid next options, or use `/back` to return to the main
13-command context. For example, after `/run`, `?` shows `/simulate`,
`/submit`, `/resume`, and `/dry-run`; these nested options invoke the same
deterministic run handler. A bare `/` always shows the global 13-command
reference. Context help and executable options are generated from one shared
registry.

The original numbered menu contains:

```
Main menu
  1) Quick setup (init + login + doctor)
  2) Run (simulate / submit - resumable)
  3) Candidates (review & submit eligible alphas by field)
  4) Status
  5) Fields (per-field progress)
  6) View errors
  7) Retry errors
  8) Submissions history
  9) Jump to alpha # (skip ahead / reset)
  10) Settings (pack, submit mode, optional AI metadata, ...)
  11) Doctor (diagnostics)
  12) Reset progress
  13) Exit
```

- **Quick setup** — re-runs init + login + doctor. Only needed once, or if
  something's clearly broken.
- **Run** — the actual work. Builds the alpha pool (if not already built),
  simulates it in batches, checks and submits qualifying alphas per your
  settings. Asks you to pick a submit mode for this run (see §5). **Safe to
  stop with Ctrl-C at any point** — nothing is lost, and running it again
  continues exactly where it left off, including which alphas were already
  submitted (so the daily cap can't be double-counted by restarting).
- **Status** — counts by stage (pending / simulated / error / submitted),
  the best alphas so far by fitness/sharpe, and the most common error
  message if anything's failing.
- **View errors** — every distinct error message, grouped, with a count —
  so 500 identical failures show as one line, not 500 unreadable rows.
- **Submissions history** — everything actually submitted to BRAIN so far,
  with alpha ID, name, and category.
- **Jump to alpha #** — see §6.
- **Settings** — change the active dataset pack, submit mode, daily submit
  cap, or optional AI metadata provider. Saved to `config.yaml` for future runs.
- **Doctor** — full diagnostic pass: session, dataset fields exist and are
  the right type, which operators your account actually has, and one real
  (harmless) test simulation. Add `--check-model` to explicitly test an AI
  metadata provider.
  Run this whenever something feels off, or after switching datasets.
- **Reset progress** — clears local pending/simulation/error progress for the
  *currently active pack only*. Submitted rows and submission history are
  retained; configuration, credentials, and other packs are not changed.

## 4. The same thing, without the menu (for scripting / cron)

Every menu option is also a direct command:

```bash
alphapilot init
alphapilot login
alphapilot doctor
alphapilot run [--set key.path=value ...]
alphapilot status [--set pack=...]
alphapilot submissions [--set pack=...]
alphapilot jump N [--set pack=...]
alphapilot reset [--yes] [--set pack=...]
alphapilot packs
alphapilot menu
```

`--set key.path=value` overrides any config value for just that one
invocation, without touching `config.yaml`, e.g.:

```bash
alphapilot run --set submit.mode=auto --set simulation.pool_size=500
```

## 5. Submit modes — what they actually do

Picked either when you choose **Run** in the menu, or fixed permanently in
**Settings**:

| Mode | Behaviour |
|---|---|
| `off` | Simulate only. Never submits anything. |
| `dry` | Runs the full pipeline (official check, writes deterministic template metadata by default) but only *prints* what it would submit. Nothing is sent to BRAIN. |
| `ask` | Pauses on each qualifying alpha, shows you the name/description, waits for y/N. |
| `auto` | Submits automatically — but still capped by `submit.max_per_day` (default 1) and `submit.max_per_run`. It will never exceed those even across multiple runs in one day, since the cap is tracked in the saved state, not in memory. |

## 6. Skipping ahead or starting over (`jump`)

Useful if you already know a stretch of the pool was fine, or want to test
only a slice:

```bash
alphapilot jump 520     # start from the 520th alpha - earlier PENDING ones are skipped
alphapilot jump 0       # undo that - include the whole pool again
```

Only alphas that are still *pending* get skipped. Anything already
simulated, errored, or submitted is left exactly as it was — you can't lose
real progress with `jump`.

## 7. If a run stops with a lot of errors

- Check **View errors** (menu) or `alphapilot status` — errors are grouped
  by message with a count, so a systemic problem (most often a daily or
  rate limit from BRAIN) shows up as one line repeated hundreds of times,
  not hundreds of separate unreadable rows.
- You don't need to do anything to retry them — the next `alphapilot run`
  automatically retries anything marked "error" (up to 2 attempts each by
  default: `simulation.max_attempts`).
- A run now stops itself automatically after 20 similar failures in a row
  (`simulation.error_streak_halt`) instead of burning through the rest of
  the pool — this is what should prevent a repeat of a whole pool getting
  marked "error" in one go.

## 8. Using a different dataset

You don't hand-build the pool of alpha ideas — ask me (Claude) for a new
**pack** file, giving me the same three things as before for the new
dataset:

1. The Data Explorer field screenshot
2. The operator list your account has
3. The simulation settings screenshot

Say something like "same format as `packs/oth176_jpn.py`, but for this
dataset" and I'll write the file. Save what I give you into the `packs/`
folder (or `data/packs/` — same effect either way). **That's the entire
setup — nothing else to configure.** It's auto-discovered:

```bash
alphapilot packs                              # lists it
alphapilot run --set pack=your_new_pack_name  # runs it
```


**How packs are identified (important if you replace or duplicate files):** a pack
is identified by its **file name** (`packs/foo.py` → `foo`), not by `PACK_NAME`
inside it. `pack:` in config accepts the file name (preferred) or a `PACK_NAME`;
if two files declare the same `PACK_NAME` and you pick by name, alphapilot refuses
and tells you which files clash. Only the pack that resolves from config is marked
active. Packs are always read from the file's current contents (no stale
`__pycache__`). When you replace/edit a pack file, the next run reconciles its
progress automatically: not-yet-simulated expressions from the old file are
removed, simulated/submitted results are kept. If the fields, settings or
operators changed, the old progress is archived to `data/state/archive/` and a
clean pool starts (submitted alphas are remembered).

or pick it from the menu's **Settings → Change pack**, which shows a
numbered list and marks which one is currently active. Each pack keeps its
own separate progress file (`data/state/<pack>.db`), so switching back and
forth between datasets never mixes up or overwrites another one's results.

## 9. Changing settings

Two ways, same effect:

- **Menu → Settings**, which validates before saving so you can't save
  something broken.
- Edit `data/config.yaml` directly in any text editor — it's plain YAML with
  comments explaining every option.

Everything in it can also be overridden per-run with `--set`, without
touching the file (see §4).

## 10. Where everything lives, and how to back it up / start fresh

```
data/
  config.yaml        your settings
  .env               your BRAIN email/password, and any LLM API key you set
  state/
    <pack>.db          progress for that pack - what's simulated, errored, submitted
  session.json         saved login session (so you're not redoing the face check constantly)
  alphapilot.log        detailed log - useful if you need to show me exactly what happened
```

- **Backup:** just copy the `data/` folder somewhere.
- **Move to another machine:** copy `data/` over, rebuild the image there.
- **Start completely fresh:** delete `data/` (or use **Reset progress** for
  just the current pack) and run `init` again.
- Nothing here is ever synced anywhere except directly to WorldQuant's own
  API — it's all local to your machine.

## 11. Updating alphapilot itself

If I send you an updated version of the tool:

```bash
# replace the alphapilot/ and packs/ folders (and Dockerfile etc.) with the new ones
# your data/ folder is untouched - nothing to migrate
docker compose build --no-cache
```

`--no-cache` matters if you're not seeing your changes take effect — Docker
sometimes reuses a stale build layer otherwise.

## 12. Quick troubleshooting checklist

- **Asks for login again** → check the `(using --home: ...)` line; you're
  probably running from a different folder than usual.
- **A run seems stuck** → check whether it's waiting on a face-check link
  (it prints one) or busy-polling BRAIN (normal for long simulations).
  `Ctrl-C` is always safe; re-run to resume.
- **A lot of errors** → see §7.
- **Not sure what's wrong at all** → run **Doctor**. It's cheap (one test
  simulation) and checks the BRAIN session, fields, and operators. Add
  `--check-model` only when diagnosing the optional AI metadata provider.
- **Something this doc doesn't cover, or doesn't match what you see** →
  paste me the exact command and output; I'll fix the tool (and this file)
  to match.

---

## Focusing a run on specific fields (new)

Every expression in a pack is tagged with the fields it uses. You can restrict a run to:

| Token | Runs |
|---|---|
| `<field_id>` | only expressions built from that ONE field |
| `combo` | any expression mixing 2+ fields (no control over which mix) |
| `combo:<field_id>` | mixes that include that field |

The **order you give is the order it runs**: all pending of the first token, then the second, etc.
Anything outside the focus is left untouched (still pending) for later. Only alphas inside the
focus are considered for submission.

**Menu:** Run -> pick numbers in order (e.g. `4,1,7`) -> choose how many submissions to stop after -> pick mode.
`Fields` in the main menu shows pending/simulated/submitted per field.

**CLI:**
```
alphapilot fields
alphapilot run --focus oth176_eq_medium,oth176_malta_eq_score,combo --stop-after 1
```
Save a default focus with Settings -> "Change saved field focus" or `run.focus` in config.yaml.

**Stop-after:** `submit.max_per_run` is now a limit for the WHOLE run (0 = unlimited). The run also
refuses to start (and stops) when `submit.max_per_day` is reached, so it no longer keeps simulating
with nothing left it is allowed to submit.

Also fixed: the "Errors" menu screen and the end-of-run summary read the wrong state file.

## Submission robustness (v5)
- An alpha the local DB marked rejected but that is ACTIVE on the platform (e.g. you submitted it by hand) is synced to "submitted" at the start of the next run.
- Check failures now print the check name, value and limit (also stored: menu -> View errors / Status).
- A FAIL is re-read once before an alpha is discarded; post-submit rejection needs the FAIL on 2 polls.
- If saving the name/description fails, it retries with the template text; if that also fails the alpha is NOT marked rejected (submit by hand, link printed).
- Declining an alpha in `ask` mode no longer re-asks about it every cycle (until you restart).

## How the submit verdict is decided (v7)
alphapilot adds no pass/fail rules of its own. It calls the platform's /check (which computes the correlation checks) and then reads the alpha's own `is.checks` - the same data the website renders. WARNING and PASS never block; only a platform-reported FAIL does. If the /check endpoint and the alpha page disagree, the run says so and follows the alpha page. On a rejection it prints what both sources said.

## Direct submit (v8)
`submit.precheck: false` (default): after a simulation batch the best in-sample candidates are submitted directly, best fitness first; BRAIN accepts or refuses. A refusal is recorded with the platform's reason. Set `submit.precheck: true` to run the /check step first. `dry` mode always pre-checks (otherwise it could not tell you anything).
