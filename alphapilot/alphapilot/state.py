"""
Resumable journal for one run.

Everything alphapilot learns about an expression (simulated? alpha_id? stats?
submitted?) lives in <home>/state.db (SQLite). This is what makes `alphapilot
run` safe to stop (Ctrl-C, laptop sleep, container restart) and resume later:
on the next `run`, expressions already marked simulated/submitted are simply
skipped, and only what's left in the pool gets worked on.

One state.db == one (pack, seed, pool_size) combination. Changing any of
those three starts a fresh pool; alphapilot warns you instead of silently
mixing two different research runs together (see Store.open).
"""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .util import utcnow_iso, today_str

SCHEMA_VERSION = 1

STATUS_PENDING = "pending"
STATUS_SIMULATING = "simulating"
STATUS_SIMULATED = "simulated"
STATUS_ERROR = "error"
STATUS_CHECK_FAIL = "check_fail"
STATUS_SUBMITTED = "submitted"
STATUS_SUBMIT_REJECTED = "submit_rejected"

TERMINAL_STATUSES = (STATUS_SUBMITTED,)  # never retried


class StateError(Exception):
    pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS alphas (
    expr            TEXT PRIMARY KEY,
    idx             INTEGER,
    family          TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    alpha_id        TEXT,
    sharpe          REAL,
    fitness         REAL,
    turnover        REAL,
    returns         REAL,
    margin          REAL,
    n_fail          INTEGER,
    failed_tests    TEXT,
    check_result    TEXT,
    check_detail    TEXT,
    error           TEXT,
    attempts        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT,
    updated_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_alphas_status ON alphas(status);
CREATE INDEX IF NOT EXISTS idx_alphas_fitness ON alphas(fitness);
CREATE INDEX IF NOT EXISTS idx_alphas_idx ON alphas(idx);

CREATE TABLE IF NOT EXISTS submissions (
    alpha_id        TEXT PRIMARY KEY,
    expr            TEXT NOT NULL,
    submitted_at    TEXT NOT NULL,
    day             TEXT NOT NULL,
    name            TEXT,
    category        TEXT,
    description_source TEXT
);
CREATE INDEX IF NOT EXISTS idx_submissions_day ON submissions(day);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    detail TEXT
);
"""


@dataclass
class Alpha:
    expr: str
    family: str
    status: str
    alpha_id: Optional[str]
    sharpe: Optional[float]
    fitness: Optional[float]
    turnover: Optional[float]
    returns: Optional[float]
    margin: Optional[float]
    n_fail: Optional[int]
    failed_tests: Optional[str]
    check_result: Optional[str]
    check_detail: Optional[str]
    error: Optional[str]
    attempts: int


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self._migrate()

    def _migrate(self):
        """Adds the per-field columns to state.db files created by older versions (no data lost)."""
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(alphas)")}
        with self._tx():
            if "fields" not in cols:
                self.conn.execute("ALTER TABLE alphas ADD COLUMN fields TEXT")
            if "nfields" not in cols:
                self.conn.execute("ALTER TABLE alphas ADD COLUMN nfields INTEGER")

    def tag_fields(self, field_ids) -> int:
        """Records which pack fields each expression uses (idempotent; only touches untagged rows)."""
        rows = self.conn.execute("SELECT expr FROM alphas WHERE nfields IS NULL").fetchall()
        if not rows:
            return 0
        with self._tx():
            for r in rows:
                used = [f for f in field_ids if re.search(rf"\b{re.escape(f)}\b", r["expr"])]
                self.conn.execute(
                    "UPDATE alphas SET fields=?, nfields=? WHERE expr=?",
                    ("," + ",".join(used) + "," if used else ",", len(used), r["expr"]),
                )
        return len(rows)

    @staticmethod
    def _focus_clause(token: str):
        """SQL fragment + params selecting the expressions one focus token refers to."""
        t = token.strip()
        if t == "combo":
            return "nfields >= 2", []
        if t.startswith("combo:"):
            return "nfields >= 2 AND instr(fields, ?) > 0", ["," + t[6:] + ","]
        return "nfields = 1 AND instr(fields, ?) > 0", ["," + t + ","]

    def focus_counts(self, field_ids) -> dict:
        """{field_id or 'combo': {status: n}} for the menu's field picker."""
        from collections import Counter

        out = {f: Counter() for f in field_ids}
        out["combo"] = Counter()
        for r in self.conn.execute("SELECT fields, nfields, status FROM alphas"):
            if r["nfields"] == 1:
                f = (r["fields"] or "").strip(",")
                if f in out:
                    out[f][r["status"]] += 1
            elif (r["nfields"] or 0) >= 2:
                out["combo"][r["status"]] += 1
        return out

    def focus_remaining(self, focus) -> int:
        """How many expressions in the focus are still pending/simulating."""
        seen = set()
        for tok in focus:
            clause, params = self._focus_clause(tok)
            for r in self.conn.execute(
                f"SELECT expr FROM alphas WHERE status IN ('pending','simulating') AND {clause}", params
            ):
                seen.add(r["expr"])
        return len(seen)

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    @contextmanager
    def _tx(self):
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # ---------------------------------------------------------------- meta

    def get_meta(self, key, default=None):
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key, value):
        with self._tx():
            self.conn.execute(
                "INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)),
            )

    def log_event(self, kind: str, detail: str = ""):
        with self._tx():
            self.conn.execute("INSERT INTO events(ts, kind, detail) VALUES (?, ?, ?)", (utcnow_iso(), kind, detail))

    # ---------------------------------------------------------------- pool

    def init_pool(self, pack_name: str, pack_hash: str, seed: int, pool_size: int, pool: dict) -> dict:
        """
        Registers a (pack, seed, pool_size) run. If a run already exists with
        a DIFFERENT pack/seed/pool_size, raises StateError instead of quietly
        mixing two pools in one state.db - use a different --home / state file
        for a different pool. Returns {"new": n, "existing": n}.
        """
        existing_pack = self.get_meta("pack_name")
        if existing_pack is not None:
            mismatches = []
            for key, val in [("pack_name", pack_name), ("pack_hash", pack_hash), ("seed", str(seed)), ("pool_size", str(pool_size))]:
                if self.get_meta(key) != str(val):
                    mismatches.append(f"{key}: stored={self.get_meta(key)!r} now={val!r}")
            if mismatches:
                raise StateError(
                    "This state directory already has a DIFFERENT pool recorded:\n  "
                    + "\n  ".join(mismatches)
                    + "\nUse a different --home directory for a new pool, or `alphapilot reset` to discard this one."
                )

        with self._tx():
            self.conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
            for k, v in [("pack_name", pack_name), ("pack_hash", pack_hash), ("seed", seed), ("pool_size", pool_size)]:
                self.conn.execute(
                    "INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (k, str(v)),
                )
            self.conn.execute(
                "INSERT INTO meta(key, value) VALUES ('created_at', ?) ON CONFLICT(key) DO NOTHING",
                (utcnow_iso(),),
            )
            n_new = 0
            for i, (expr, family) in enumerate(pool.items()):
                cur = self.conn.execute(
                    "INSERT OR IGNORE INTO alphas(expr, idx, family, status, attempts, created_at, updated_at) "
                    "VALUES (?, ?, ?, 'pending', 0, ?, ?)",
                    (expr, i, family, utcnow_iso(), utcnow_iso()),
                )
                n_new += cur.rowcount
        return {"new": n_new, "existing": len(pool) - n_new}

    def pool_size(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) n FROM alphas").fetchone()
        return row["n"]

    def skip_before(self, start_index_1based: int) -> int:
        """
        'Start from the Nth alpha': marks pool positions before N (1-based) as
        'skipped' so they are never claimed - but only if they're still
        'pending'. Anything already simulated, errored-with-remaining-attempts,
        or submitted is left exactly as it is; this only affects untouched
        expressions, so it can't hide or lose real progress.
        """
        with self._tx():
            cur = self.conn.execute(
                "UPDATE alphas SET status='skipped', updated_at=? WHERE idx < ? AND status='pending'",
                (utcnow_iso(), start_index_1based - 1),
            )
        return cur.rowcount

    def unskip_all(self) -> int:
        """Undo skip_before: everything marked 'skipped' becomes claimable ('pending') again."""
        with self._tx():
            cur = self.conn.execute(
                "UPDATE alphas SET status='pending', updated_at=? WHERE status='skipped'", (utcnow_iso(),)
            )
        return cur.rowcount

    # ---------------------------------------------------------------- batches

    def claim_batch(self, size: int, max_attempts: int, focus=None):
        """
        Atomically pick up to `size` expressions to work on next: pending
        first, then errored ones that haven't exhausted max_attempts (so a
        transient failure gets retried on the next run, but a permanently
        broken expression eventually stops being retried). Marks them
        'simulating' so a crash mid-batch doesn't lose track of what was
        in flight - `requeue_stuck` recovers those on the next `run`.
        """
        with self._tx():
            if focus:
                # Fill the batch in focus order: every token's PENDING first (in the order
                # you listed them), then - only if there is room left - retries of errored ones.
                exprs = []
                for status_sql, extra in (("status='pending'", []), ("status='error' AND attempts < ?", [max_attempts])):
                    for token in focus:
                        need = size - len(exprs)
                        if need <= 0:
                            break
                        clause, params = self._focus_clause(token)
                        excl = f" AND expr NOT IN ({','.join('?' * len(exprs))})" if exprs else ""
                        rows = self.conn.execute(
                            f"SELECT expr FROM alphas WHERE {status_sql} AND {clause}{excl} ORDER BY idx LIMIT ?",
                            [*extra, *params, *exprs, need],
                        ).fetchall()
                        exprs += [r["expr"] for r in rows]
            else:
                rows = self.conn.execute(
                    "SELECT expr FROM alphas WHERE status='pending' "
                    "UNION ALL "
                    "SELECT expr FROM alphas WHERE status='error' AND attempts < ? "
                    "LIMIT ?",
                    (max_attempts, size),
                ).fetchall()
                exprs = [r["expr"] for r in rows][:size]
            if exprs:
                qmarks = ",".join("?" * len(exprs))
                self.conn.execute(
                    f"UPDATE alphas SET status='simulating', updated_at=? WHERE expr IN ({qmarks})",
                    [utcnow_iso(), *exprs],
                )
        return exprs

    def requeue_stuck(self) -> int:
        """Call once at the start of a run: anything left 'simulating' from a previous crash goes back to pending."""
        with self._tx():
            cur = self.conn.execute(
                "UPDATE alphas SET status='pending', updated_at=? WHERE status='simulating'", (utcnow_iso(),)
            )
        return cur.rowcount

    def mark_simulated(self, expr, alpha_id, stats: dict, failed_tests: list):
        with self._tx():
            self.conn.execute(
                "UPDATE alphas SET status='simulated', alpha_id=?, sharpe=?, fitness=?, turnover=?, "
                "returns=?, margin=?, n_fail=?, failed_tests=?, error=NULL, attempts=attempts+1, updated_at=? "
                "WHERE expr=?",
                (
                    alpha_id, stats.get("sharpe"), stats.get("fitness"), stats.get("turnover"),
                    stats.get("returns"), stats.get("margin"), len(failed_tests), ",".join(failed_tests),
                    utcnow_iso(), expr,
                ),
            )

    def mark_error(self, expr, error: str):
        with self._tx():
            self.conn.execute(
                "UPDATE alphas SET status='error', error=?, attempts=attempts+1, updated_at=? WHERE expr=?",
                (error[:2000], utcnow_iso(), expr),
            )

    def retry_errors(self, pattern: str = "", reset_attempts: bool = False) -> int:
        """
        Reset errored expressions back to 'pending' so they are picked up on
        the next `run`.  If `pattern` is given (case-insensitive substring),
        only rows whose error message contains that string are reset.  If
        `reset_attempts` is True the attempt counter is also zeroed, giving
        each expression the full max_attempts budget again; otherwise the
        existing count is kept (so max_attempts is still respected).
        Returns the number of rows that were reset.
        """
        now = utcnow_iso()
        if reset_attempts:
            attempt_sql = "attempts=0, "
        else:
            attempt_sql = ""
        with self._tx():
            if pattern:
                cur = self.conn.execute(
                    f"UPDATE alphas SET status='pending', {attempt_sql}error=NULL, updated_at=? "
                    "WHERE status='error' AND instr(lower(error), lower(?))",
                    (now, pattern),
                )
            else:
                cur = self.conn.execute(
                    f"UPDATE alphas SET status='pending', {attempt_sql}error=NULL, updated_at=? "
                    "WHERE status='error'",
                    (now,),
                )
        return cur.rowcount

    def mark_check(self, expr, result: str, detail: str):
        with self._tx():
            self.conn.execute(
                "UPDATE alphas SET check_result=?, check_detail=?, status=?, updated_at=? WHERE expr=?",
                (result, detail[:2000], STATUS_CHECK_FAIL if result == "FAIL" else "simulated", utcnow_iso(), expr),
            )

    def mark_submitted(self, expr, alpha_id, name, category, description_source, tz_name):
        now = utcnow_iso()
        day = today_str(tz_name)
        with self._tx():
            self.conn.execute(
                "UPDATE alphas SET status='submitted', updated_at=? WHERE expr=?", (now, expr)
            )
            self.conn.execute(
                "INSERT OR REPLACE INTO submissions(alpha_id, expr, submitted_at, day, name, category, description_source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (alpha_id, expr, now, day, name, category, description_source),
            )

    def reconcile_candidates(self, limit: int = 50):
        """Recently rejected rows - re-checked against the platform in case they were later submitted by hand."""
        rows = self.conn.execute(
            "SELECT * FROM alphas WHERE status IN ('submit_rejected','check_fail') AND alpha_id IS NOT NULL "
            "ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return self._rows_to_alphas(rows)

    def mark_submit_rejected(self, expr, reason: str):
        with self._tx():
            self.conn.execute(
                "UPDATE alphas SET status='submit_rejected', error=?, updated_at=? WHERE expr=?",
                (reason[:2000], utcnow_iso(), expr),
            )

    # ---------------------------------------------------------------- queries

    def counts(self) -> dict:
        rows = self.conn.execute("SELECT status, COUNT(*) n FROM alphas GROUP BY status").fetchall()
        out = {r["status"]: r["n"] for r in rows}
        out["total"] = sum(out.values())
        return out

    def submissions_on(self, day: str) -> int:
        row = self.conn.execute("SELECT COUNT(*) n FROM submissions WHERE day=?", (day,)).fetchone()
        return row["n"]

    _ALPHA_FIELDS = [f.name for f in __import__("dataclasses").fields(Alpha)]

    def _rows_to_alphas(self, rows):
        return [Alpha(**{k: r[k] for k in self._ALPHA_FIELDS}) for r in rows]

    def submit_candidates(self, min_sharpe: float, min_fitness: float, limit: int, focus=None):
        base = (
            "SELECT * FROM alphas WHERE status='simulated' AND (n_fail IS NULL OR n_fail=0) "
            "AND (sharpe IS NULL OR sharpe >= ?) AND (fitness IS NULL OR fitness >= ?)"
        )
        order = " ORDER BY fitness DESC NULLS LAST, sharpe DESC NULLS LAST LIMIT ?"
        if not focus:
            rows = self.conn.execute(base + order, (min_sharpe, min_fitness, limit)).fetchall()
            return self._rows_to_alphas(rows)
        # only alphas inside the focus are eligible; earlier focus tokens are tried first
        rows, seen = [], set()
        for token in focus:
            clause, params = self._focus_clause(token)
            for r in self.conn.execute(base + f" AND {clause}" + order, (min_sharpe, min_fitness, *params, limit)).fetchall():
                if r["expr"] not in seen and len(rows) < limit:
                    seen.add(r["expr"])
                    rows.append(r)
        return self._rows_to_alphas(rows)

    def top(self, n: int = 10):
        rows = self.conn.execute(
            "SELECT * FROM alphas WHERE status IN ('simulated','submitted','check_fail') "
            "ORDER BY fitness DESC NULLS LAST, sharpe DESC NULLS LAST LIMIT ?",
            (n,),
        ).fetchall()
        return self._rows_to_alphas(rows)

    def recent_errors(self, n: int = 10):
        rows = self.conn.execute(
            "SELECT expr, error, attempts, updated_at FROM alphas WHERE status='error' ORDER BY updated_at DESC LIMIT ?",
            (n,),
        ).fetchall()
        return [dict(r) for r in rows]

    def error_summary(self, n: int = 10):
        """Groups errored alphas by a normalised prefix of their error message, so a run that
        died with 800 near-identical errors (e.g. a daily limit) shows as ONE line with a count,
        not 800 unreadable rows."""
        rows = self.conn.execute("SELECT error FROM alphas WHERE status='error' AND error IS NOT NULL").fetchall()
        import re as _re
        from collections import Counter

        groups = Counter()
        examples = {}
        for r in rows:
            key = _re.sub(r"\d+", "#", (r["error"] or "")[:140]).strip()
            groups[key] += 1
            examples.setdefault(key, r["error"])
        out = []
        for key, count in groups.most_common(n):
            out.append({"count": count, "example": examples[key]})
        return out

    def submissions_list(self, n: int = 20):
        rows = self.conn.execute(
            "SELECT * FROM submissions ORDER BY submitted_at DESC LIMIT ?", (n,)
        ).fetchall()
        return [dict(r) for r in rows]

    def is_done(self, focus=None) -> bool:
        if focus:
            return self.focus_remaining(focus) == 0
        c = self.counts()
        remaining = c.get("pending", 0) + c.get("simulating", 0)
        return remaining == 0
