"""
Thin, robust layer on top of ace_lib.

Why this exists instead of calling ace_lib directly everywhere:

1. Session persistence. ace_lib.start_session() always does a fresh
   POST /authentication (and, if needed, a face check) every time it's
   called. That's fine in a notebook you run once a day, but alphapilot is
   meant to be re-invoked often (resumed, checked on, run from cron), so we
   save the session cookies to <home>/session.json and reuse them until they
   are actually close to expiry.

2. Non-blocking face check. ace_lib's own persona flow calls Python's
   input(), which blocks forever if there's no terminal attached (cron,
   Docker in the background). We poll instead, on a timer, and give up
   cleanly with an actionable message if you don't complete the check in
   time. The manual step is identical to the one you already did - open the
   link, verify with your face - we just don't hang the process waiting for
   an Enter key that will never come.

3. check_session_and_relogin() inside ace_lib calls the *module-level*
   ace_lib.start_session() if the session gets short mid-run. Since Python
   looks up unqualified names at call time, monkeypatching
   ace_lib.start_session to point at our version (see `install_into`) makes
   every internal re-login in ace_lib go through our non-blocking flow too,
   without touching ace_lib.py itself.

4. A single, careful implementation of the submit flow: POST .../submit only
   ever means "request accepted", never "submitted" - the caller must poll
   the alpha until status == ACTIVE. See submit_alpha().
"""
from __future__ import annotations

import json
import time
import webbrowser
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

from . import util
from .util import LOGGER


class BrainError(Exception):
    pass


class AuthError(BrainError):
    pass


class PersonaTimeout(BrainError):
    def __init__(self, url: str):
        super().__init__(
            "Face check was not completed in time.\n"
            f"  Open this link, verify, then re-run the command:\n  {url}"
        )
        self.url = url


class RateLimited(BrainError):
    def __init__(self, retry_after=None, detail=""):
        self.retry_after = retry_after
        msg = "Rate limited by BRAIN" + (f" (retry after {retry_after:.0f}s)" if retry_after else "")
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


class DailyLimitReached(BrainError):
    pass


@dataclass
class SubmitOutcome:
    ok: bool
    halt: bool
    stage: str
    status_code: Optional[int]
    detail: str
    alpha_status: Optional[str] = None
    raw: str = ""          # exactly what BRAIN sent back (never contains cookies)


def _raw_post(resp) -> str:
    hdrs = {k: v for k, v in dict(resp.headers).items() if k.lower() not in ("set-cookie", "authorization")}
    return f"HTTP {resp.status_code}\nheaders: {json.dumps(hdrs, default=str)}\nbody: {resp.text[:6000]}"


def _raw_detail(detail: dict) -> str:
    keep = {"status": detail.get("status"), "is.checks": (detail.get("is") or {}).get("checks")}
    return json.dumps(keep, default=str, indent=1)[:8000]


def _cookie_path(home):
    return home / "session.json"


def save_cookies(session, home) -> None:
    from requests.utils import dict_from_cookiejar

    data = {"cookies": dict_from_cookiejar(session.cookies), "saved_at": util.utcnow_iso()}
    util.write_private(_cookie_path(home), json.dumps(data))


def load_cookies(session, home) -> bool:
    from requests.utils import cookiejar_from_dict

    p = _cookie_path(home)
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        session.cookies = cookiejar_from_dict(data.get("cookies", {}))
        return bool(data.get("cookies"))
    except Exception as e:
        LOGGER.warning("could not load saved session cookies: %r", e)
        return False


def authenticate_once(session, base_url: str):
    """POST /authentication. Returns ('ok', None) or ('persona', url) or raises AuthError."""
    r = session.post(f"{base_url}/authentication")
    if r.status_code == 201:
        return "ok", None
    if r.status_code == 401:
        if r.headers.get("WWW-Authenticate") == "persona" and "Location" in r.headers:
            return "persona", urljoin(r.url, r.headers["Location"])
        raise AuthError("Invalid email/password. Run `alphapilot login` to fix your credentials.")
    raise AuthError(f"Unexpected response from /authentication: HTTP {r.status_code}: {r.text[:300]}")


def complete_persona(session, persona_url: str, timeout_min: float, poll_seconds: float, on_waiting=None) -> None:
    """Poll the persona URL (no input() / stdin) until it succeeds or timeout_min elapses."""
    deadline = time.time() + timeout_min * 60
    attempt = 0
    while True:
        r = session.post(persona_url)
        if r.status_code == 201:
            return
        attempt += 1
        if time.time() >= deadline:
            raise PersonaTimeout(persona_url)
        if on_waiting:
            on_waiting(attempt, deadline - time.time())
        time.sleep(poll_seconds)


def ensure_session(ace, cfg, home, force_relogin: bool = False, on_persona_link=None, on_waiting=None):
    """
    Returns an authenticated ace_lib.SingleSession, reusing a saved session
    when it still has plenty of time left, otherwise (re-)authenticating -
    including the face check when BRAIN asks for it.
    """
    s = ace.SingleSession()
    # requests has no default timeout.  A single stalled socket otherwise
    # bypasses every higher-level polling deadline and leaves claimed rows in
    # `simulating` until the next process restart.
    s._alphapilot_request_timeout = cfg.api.timeout_s
    if not getattr(s, "_alphapilot_timeout_installed", False):
        original_request = s.request

        def request_with_timeout(method, url, **kwargs):
            kwargs.setdefault("timeout", s._alphapilot_request_timeout)
            return original_request(method, url, **kwargs)

        s.request = request_with_timeout
        s._alphapilot_timeout_installed = True
    from .util import load_dotenv

    load_dotenv(home / ".env")
    s.auth = ace.get_credentials()

    if cfg.session.reuse_cookies and not force_relogin:
        if load_cookies(s, home):
            left = ace.check_session_timeout(s)
            if left and left > cfg.session.min_seconds_left:
                LOGGER.info("reused saved session, %.0fs left", left)
                return s
            LOGGER.info("saved session too short (%.0fs left) or expired - re-authenticating", left or 0)

    status, extra = authenticate_once(s, ace.brain_api_url)
    if status == "persona":
        if on_persona_link:
            on_persona_link(extra)
        if cfg.session.open_browser and not util.in_docker():
            try:
                webbrowser.open(extra)
            except Exception:
                pass
        complete_persona(
            s, extra,
            timeout_min=cfg.session.persona_timeout_min,
            poll_seconds=cfg.session.persona_poll_seconds,
            on_waiting=on_waiting,
        )
        # BRAIN needs ~2 minutes to propagate the face-check session server-side.
        # Jumping straight into simulations after a face check reliably causes errors,
        # so we wait here with a visible countdown.
        _FACE_CHECK_COOLDOWN_S = 120
        _COOLDOWN_ANNOUNCE_EVERY = 15
        util.say(
            f"Face check confirmed - waiting {_FACE_CHECK_COOLDOWN_S // 60} min "
            "for BRAIN to propagate the session before continuing..."
        )
        waited = 0
        while waited < _FACE_CHECK_COOLDOWN_S:
            chunk = min(_COOLDOWN_ANNOUNCE_EVERY, _FACE_CHECK_COOLDOWN_S - waited)
            time.sleep(chunk)
            waited += chunk
            remaining = _FACE_CHECK_COOLDOWN_S - waited
            if remaining > 0:
                util.say(f"  ...{remaining}s left")

        # Re-authenticate after the cooldown so the session object receives a proper
        # HTTP 201 /authentication response with the fully-propagated server-side cookies.
        # Without this, the session was only authenticated via the persona endpoint and
        # never got a confirmed /authentication 201 - causing the first simulation batch
        # to fail with auth errors even though the face check itself succeeded.
        util.say("Re-authenticating to confirm session is fully active...")
        post_status, post_extra = authenticate_once(s, ace.brain_api_url)
        if post_status == "persona":
            # Extremely unlikely (would mean another face check required immediately after),
            # but handle it gracefully rather than silently using a broken session.
            LOGGER.warning(
                "Unexpected second persona challenge after face-check cooldown (%s) - "
                "the session may not be fully propagated yet. Proceeding anyway.", post_extra
            )
        LOGGER.info("Post-cooldown re-authentication: status=%s", post_status)

    if cfg.session.reuse_cookies:
        save_cookies(s, home)
    return s


def install_into(ace, cfg, home, on_persona_link=None, on_waiting=None):
    """
    Monkeypatch ace_lib.start_session so that ace_lib's OWN internal re-login
    (inside check_session_and_relogin, called by simulate_alpha_list_multi
    etc. when a session gets short mid-batch) goes through our non-blocking,
    cookie-saving flow instead of blocking on input().
    """

    def _replacement():
        return ensure_session(ace, cfg, home, force_relogin=True, on_persona_link=on_persona_link, on_waiting=on_waiting)

    ace.start_session = _replacement


# ---------------------------------------------------------------- rate limits

def check_rate_limit_headers(resp) -> Optional[dict]:
    h = resp.headers
    if "X-RateLimit-Remaining" in h or "x-ratelimit-remaining" in h:
        try:
            return {
                "limit": int(h.get("X-RateLimit-Limit", h.get("x-ratelimit-limit", 0)) or 0),
                "remaining": int(h.get("X-RateLimit-Remaining", h.get("x-ratelimit-remaining", 0)) or 0),
                "reset_s": float(h.get("X-RateLimit-Reset", h.get("x-ratelimit-reset", 0)) or 0),
            }
        except (TypeError, ValueError):
            return None
    return None


# ---------------------------------------------------------------- submit

def submit_alpha(ace, s, alpha_id: str, timeout_s: float, poll_every_s: float = 10, ignore_names=(), show_polling: bool = False) -> SubmitOutcome:
    """
    POST /alphas/{id}/submit only ever means ACCEPTED, never SUBMITTED.
    We then poll the alpha itself until status == ACTIVE. See module docstring
    point 4 - this is the one piece of behaviour that must never be guessed
    wrong, since a false "rejected" reading could trigger a second submit
    while the first is still going through.
    """
    url = f"{ace.brain_api_url}/alphas/{alpha_id}/submit"
    try:
        post = s.post(url)
    except Exception as e:
        # The request may have reached BRAIN even if the client did not receive
        # its response. Treat this as ambiguous and never submit it again blindly.
        return SubmitOutcome(
            False, True, "post_unknown", None,
            f"submit request outcome is unknown after {type(e).__name__}: {e}",
        )
    code = post.status_code

    if code in (401, 404, 405, 429) or code >= 500:
        reason = {
            401: "not authenticated (session expired?)",
            404: "submit endpoint not found",
            405: "submit method not allowed",
            429: "rate limit / submission limit reached",
        }.get(code, "server error - submission state unknown")
        return SubmitOutcome(False, True, "post", code, f"{reason}: {post.text[:400]}", raw=_raw_post(post))

    if code not in (200, 201, 202):
        return SubmitOutcome(False, False, "post", code, post.text[:600], raw=_raw_post(post))

    t0 = time.time()
    fail_polls = 0
    operation_url = post.headers.get("Location")
    if operation_url:
        operation_url = urljoin(ace.brain_api_url + "/", operation_url)
    ignore = {str(n).upper() for n in ignore_names}

    def failed_checks(detail):
        checks = (detail.get("is") or {}).get("checks") or []
        return [
            c for c in checks
            if isinstance(c, dict)
            and c.get("result") == "FAIL"
            and str(c.get("name")).upper() not in ignore
        ]

    while True:
        alpha_poll_wait = 0.0
        operation = None
        if operation_url:
            try:
                operation = s.get(operation_url)
            except Exception as e:
                return SubmitOutcome(
                    False, True, "submission_operation", code,
                    f"submission was accepted but operation polling failed ({type(e).__name__}: {e}); outcome is unknown",
                    raw=f"POST response:\n{_raw_post(post)}",
                )
            if operation.status_code == 403:
                try:
                    operation_detail = operation.json() or {}
                except Exception:
                    operation_detail = {}
                operation_failed = failed_checks(operation_detail)
                if operation_failed:
                    desc = [f"{c.get('name')} (value={c.get('value')}, limit={c.get('limit')})" for c in operation_failed]
                    return SubmitOutcome(
                        False, False, "rejected_after_accept", code,
                        f"submission operation rejected: {desc}",
                        operation_detail.get("status"), raw=_raw_post(operation),
                    )
                return SubmitOutcome(
                    False, True, "submission_operation", operation.status_code,
                    "submission operation returned HTTP 403 without failure details",
                    raw=_raw_post(operation),
                )

        try:
            alpha_response = s.get(f"{ace.brain_api_url}/alphas/{alpha_id}")
        except Exception as e:
            return SubmitOutcome(
                False, True, "alpha_poll", code,
                f"submission was accepted but alpha polling failed ({type(e).__name__}: {e}); outcome is unknown",
                raw=f"POST response:\n{_raw_post(post)}",
            )
        if alpha_response.status_code == 401 or alpha_response.status_code == 403:
            return SubmitOutcome(
                False, True, "alpha_poll", alpha_response.status_code,
                "session expired or access denied while checking submission outcome",
                raw=f"POST response:\n{_raw_post(post)}\nalpha poll:\n{_raw_post(alpha_response)}",
            )
        if alpha_response.status_code == 429 or alpha_response.status_code >= 500:
            try:
                alpha_poll_wait = float(alpha_response.headers.get("Retry-After", 0) or 0)
            except (TypeError, ValueError):
                alpha_poll_wait = 0.0
            detail = {}
        elif alpha_response.status_code // 100 != 2:
            return SubmitOutcome(
                False, True, "alpha_poll", alpha_response.status_code,
                f"could not determine submission outcome: alpha poll HTTP {alpha_response.status_code}",
                raw=f"POST response:\n{_raw_post(post)}\nalpha poll:\n{_raw_post(alpha_response)}",
            )
        else:
            try:
                detail = alpha_response.json() or {}
                if not isinstance(detail, dict):
                    raise ValueError("response was not a JSON object")
            except (ValueError, TypeError) as e:
                return SubmitOutcome(
                    False, True, "alpha_poll", alpha_response.status_code,
                    f"could not determine submission outcome from alpha response: {e}",
                    raw=f"POST response:\n{_raw_post(post)}\nalpha poll:\n{_raw_post(alpha_response)}",
                )
        status = detail.get("status")

        if status == "ACTIVE":
            return SubmitOutcome(True, False, "active", code, "alpha is ACTIVE", status)

        failed_c = failed_checks(detail)
        if show_polling:
            pending_count = sum(
                1 for c in (detail.get("is") or {}).get("checks", [])
                if isinstance(c, dict) and c.get("result") == "PENDING"
            )
            operation_status = operation.status_code if operation is not None else "not-polled"
            retry_after = operation.headers.get("Retry-After") if operation is not None else None
            util.say(
                f"    submit poll {alpha_id}: operation_http={operation_status} "
                f"retry_after={retry_after or '-'} alpha_status={status or '-'} "
                f"pending_checks={pending_count} failed_checks={len(failed_c)}"
            )
        if failed_c:
            fail_polls += 1
            # must persist across 2 polls, so one stale/transitional read can't reject an alpha that is going through
            if fail_polls >= 2:
                desc = [f"{c.get('name')} (value={c.get('value')}, limit={c.get('limit')})" for c in failed_c]
                return SubmitOutcome(False, False, "rejected_after_accept", code, f"status={status}, failed checks: {desc}", status, raw=_raw_detail(detail))
        else:
            fail_polls = 0

        if time.time() - t0 > timeout_s:
            return SubmitOutcome(
                False, True, "not_active_after_timeout", code,
                f"request accepted (HTTP {code}) but status is still {status!r} after {timeout_s:.0f}s - "
                "it may still be in review. Check the platform before re-running.",
                status,
                raw=f"POST response:\n{_raw_post(post)}\nlast alpha detail:\n{_raw_detail(detail)}",
            )
        wait_s = poll_every_s
        if operation is not None:
            try:
                retry_after = float(operation.headers.get("Retry-After", 0) or 0)
            except (TypeError, ValueError):
                retry_after = 0
            if retry_after > 0:
                wait_s = retry_after
        if alpha_poll_wait > 0:
            wait_s = max(wait_s, alpha_poll_wait)
        time.sleep(min(wait_s, max(0.0, timeout_s - (time.time() - t0))))
