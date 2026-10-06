# alphapilot

Resumable automation for WorldQuant BRAIN: build a pool of alpha expressions
from a dataset "pack", simulate them, and (optionally) submit the best ones -
stopping after a configurable number per day. Runs the same way locally or in
Docker; safe to stop and resume at any point.

## What it does, in your own words

1. You give it a **pack**: one Python file describing a dataset (fields,
   allowed operators, simulation settings, and how to build candidate alpha
   expressions). `packs/oth176_jpn.py` is the one already built from your
   screenshots. To add a new dataset, hand Claude the same three things you
   gave it before - the Data Explorer field screenshot, the operator list,
   and the simulation-settings screenshot - and ask for a new pack file. Say
   "same as the OTH176 JPN one, but for dataset X" and point it at this repo.
2. `alphapilot run` builds the pool (default 1000 expressions), simulates it
   in batches (default 10 at a time), and periodically checks whether any
   simulated alpha is good enough to submit.
3. Progress lives in `<home>/state.db` (SQLite). Stop it anytime (Ctrl-C,
   closed laptop, container restart) and `alphapilot run` again tomorrow - it
   picks up exactly where it left off, including which alphas were already
   submitted, so the daily submission cap is never accidentally exceeded.
4. The face-check login is exactly the manual step you already do - open a
   link, verify - alphapilot just doesn't block forever if you're not at the
   keyboard when it comes up; it waits up to `session.persona_timeout_min`
   minutes, checking periodically, then stops cleanly with the link if you
   miss it.

## Quick start (no Docker)

```bash
pip install -e .
export PYTHONPATH=/path/to/ACE_API__Gold_

alphapilot                       # launches the interactive menu (same as `alphapilot menu`)
```

Or drive it directly (same commands the menu calls under the hood):

```bash
alphapilot init                 # creates ./data/config.yaml
alphapilot login                # stores your BRAIN email/password in ./data/.env
alphapilot doctor               # verifies session, fields, operators, LLM, 1 smoke simulation
alphapilot run                  # the real thing - resumable, Ctrl-C anytime
alphapilot status                # counts, top alphas, most common errors
alphapilot submissions           # everything submitted so far
alphapilot jump 520              # start from the 520th alpha (skips earlier PENDING ones only)
alphapilot jump 0                # undo that - include the whole pool again
```

`--home` (or `$ALPHAPILOT_HOME`) picks where everything lives - default `./data`.
Each pack gets its own progress file under `data/state/<pack>.db`, so
switching packs never mixes or loses another pack's results.

`--home` (or `$ALPHAPILOT_HOME`) picks where `config.yaml`, `state.db`,
`.env`, `session.json` and `alphapilot.log` live. Default: `./data`.

## Quick start (Docker)

```bash
# 1. put WorldQuant's ACE_API__Gold_ folder next to this Dockerfile
cp -r /path/to/ACE_API__Gold_ .

docker compose build
docker compose run --rm alphapilot init
docker compose run --rm alphapilot login          # needs -it, which compose run gives you
docker compose run --rm alphapilot doctor
docker compose run --rm alphapilot run
```

Everything under `./data` on your host is the container's `/data` - config,
state, credentials, logs. Nothing is lost between container runs.

This is a command-line tool, not a web service: it listens on no port and
prints its output in the terminal running `docker compose run`. `run` gives
the container an interactive terminal for the menu and login prompts; direct
commands such as `status` can also be run without prompts. The image needs
outbound access to the WorldQuant BRAIN API (and to the configured LLM provider
if you select one). The ACE API source folder is copied into the image at
build time; it is not a running service or a host port.

**About the face check in Docker:** the container has no camera or browser,
so when a face check is needed, `alphapilot` prints the link and waits (it
does not try to open a browser inside the container). Open that link on your
own phone/laptop, verify, and the container's poll picks it up within
`session.persona_poll_seconds`. If you miss the `persona_timeout_min` window,
it exits cleanly - just run the command again.

For a background/cron setup: run once interactively to complete the first
face check (the session cookie is then reused - see `session.min_seconds_left`
in the config - so unattended re-runs won't need a fresh face check unless
the saved session actually expires).

## Recovering from a bad run

If a run stops after simulating an unusual number of expressions with an
error, `alphapilot status` (or the menu's "View errors") groups the errors by
message so a systemic problem (a daily limit, most likely) shows as one line
with a count instead of hundreds of unreadable rows. `simulation.error_streak_halt`
(default 20) also stops a run automatically once that many simulations in a
row fail with a similar-looking error, instead of burning through the rest of
the pool one at a time - so this shouldn't happen again, but if it does, the
grouped error view tells you what to look at.

Anything marked "error" is retried automatically on the next `alphapilot run`
(up to `simulation.max_attempts`, default 2) - you don't need to do anything
for that part to resume. Nothing marked "error" ever gets silently dropped.

## Skipping ahead / starting over (`jump`)

```bash
alphapilot jump 520     # start from the 520th alpha; earlier ones stay untouched
                         # if they were already simulated - only still-PENDING
                         # ones before #520 are skipped
alphapilot jump 0       # undo - include the whole pool again
```

Same thing from the menu: **"Jump to alpha # (skip ahead / reset)"**.

## Adding a new dataset pack

Yes - that's the whole process. Give Claude the same three things you gave it
before (the Data Explorer field screenshot, the operator list, and the
simulation-settings screenshot) and ask for a new pack file in the same
format as `packs/oth176_jpn.py`. Drop the resulting `.py` file into `packs/`
(or `data/packs/` if you'd rather keep it outside the repo) - nothing else
needs to change. It's auto-discovered:

- `alphapilot packs` lists it
- the menu's **Settings → Change pack** shows it in a numbered picker
- `alphapilot run --set pack=your_new_pack` (or picking it in the menu) starts
  simulating it, with its own separate progress file

## Configuration (`data/config.yaml`)

Everything is overridable per-invocation with `--set key.path=value`, e.g.:

```bash
alphapilot run --set submit.mode=auto --set simulation.batch_size=5
```

Key settings:

| Key | Meaning |
|---|---|
| `pack` | which dataset pack to use (name in `packs/`, or a path) |
| `simulation.pool_size` | how many expressions to draw from the pack (default 1000) |
| `simulation.batch_size` | expressions per multi-simulation, 1-10 (default 10) |
| `simulation.on_daily_limit` | `stop` (default, safest) or `wait` if BRAIN rate-limits you |
| `submit.mode` | `off`, `dry` (log only), `ask` (confirm each one), `auto` |
| `submit.max_per_day` | hard cap, tracked in `submit.timezone`'s calendar day, survives restarts |
| `submit.max_per_run` | extra cap for a single `run` invocation |
| `llm.provider` | `template` (no network/key needed), `openrouter`, `mistral`, `openai`, `ollama`, `custom` |
| `llm.fallback` | provider to try if the main one fails (or `template`) |

Run `alphapilot init` to generate a fully-commented `config.yaml`.

### Switching LLM providers

```yaml
llm:
  provider: mistral          # was: openrouter
  model: mistral-small-latest
  api_key_env: MISTRAL_API_KEY
```

Set the corresponding environment variable (`MISTRAL_API_KEY`, etc.) - in
Docker, put it in a `.env` file next to `docker-compose.yml` or export it
before `docker compose run`. `llm.provider: template` needs no key at all and
is the automatic fallback if the real provider ever fails, so a bad key never
stops a run.

## Submission safety

- `POST /alphas/{id}/submit` only ever means *accepted* - the code always
  polls the alpha afterward until `status == ACTIVE` before counting it as
  submitted. If that outcome is ever ambiguous (timeout, unexpected HTTP
  status, rate limit), the whole run halts rather than risk a second submit.
- `submit.max_per_day` is enforced from `state.db`, not from memory, so it
  holds even if you stop and restart the process, or run it from cron.
- `submit.mode: dry` runs the entire pipeline (checks, LLM description) and
  logs what it *would* submit, without ever calling PATCH or POST.

## Repository layout

```
alphapilot/          the CLI and engine (dataset-agnostic)
packs/                dataset packs - one .py file per dataset
data/                 created by `init`; config, state, secrets (gitignored)
Dockerfile, docker-compose.yml
```
