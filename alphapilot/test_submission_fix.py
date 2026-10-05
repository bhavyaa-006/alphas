"""Long-running isolated test of the proposed async submission handling."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "ACE_API__Gold_"))

import ace_lib as ace
from alphapilot import brain_client as BC
from alphapilot import config as CFG


def parse_body(response):
    try:
        return response.json() or {}
    except Exception:
        return {}


def failed_checks(detail):
    checks = (detail.get("is") or {}).get("checks") or []
    return [
        c for c in checks
        if isinstance(c, dict) and c.get("result") == "FAIL"
    ]


def pending_checks(detail):
    checks = (detail.get("is") or {}).get("checks") or []
    return [c.get("name") for c in checks if isinstance(c, dict) and c.get("result") == "PENDING"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("alpha_id")
    parser.add_argument("--home", default=os.environ.get("ALPHAPILOT_HOME", "data"))
    parser.add_argument("--minutes", type=float, default=10)
    args = parser.parse_args()

    home = CFG.resolve_home(args.home)
    cfg = CFG.load_config(home)
    session = BC.ensure_session(ace, cfg, home)
    base_url = ace.brain_api_url.rstrip("/")
    alpha_url = f"{base_url}/alphas/{args.alpha_id}"

    post = session.post(f"{alpha_url}/submit")
    post_body = parse_body(post)
    print(f"POST: HTTP {post.status_code}")
    if post.status_code == 403:
        failures = failed_checks(post_body)
        print("RESULT: REJECTED")
        print(json.dumps(failures, indent=2))
        return 0
    if post.status_code not in (200, 201, 202):
        print(f"RESULT: UNKNOWN HTTP {post.status_code}: {post.text[:500]}")
        return 1

    operation_url = post.headers.get("Location")
    if not operation_url:
        print("RESULT: UNKNOWN - accepted response had no Location header")
        return 1
    operation_url = urljoin(base_url + "/", operation_url)
    print(f"operation: {operation_url}")

    deadline = time.time() + args.minutes * 60
    last_report = 0.0
    consecutive_failures = 0
    while time.time() < deadline:
        operation = session.get(operation_url)
        operation_body = parse_body(operation)
        operation_failures = failed_checks(operation_body)
        if operation.status_code == 403 or operation_failures:
            print("RESULT: REJECTED")
            print(json.dumps({"http": operation.status_code, "checks": operation_failures}, indent=2))
            return 0

        alpha = session.get(alpha_url)
        alpha_body = parse_body(alpha)
        status = alpha_body.get("status")
        alpha_failures = failed_checks(alpha_body)
        pending = pending_checks(alpha_body)
        if status == "ACTIVE":
            print("RESULT: ACCEPTED (ACTIVE)")
            return 0
        if alpha_failures:
            consecutive_failures += 1
            if consecutive_failures >= 2:
                print("RESULT: REJECTED from alpha checks")
                print(json.dumps(alpha_failures, indent=2))
                return 0
        else:
            consecutive_failures = 0

        now = time.time()
        if now - last_report >= 30:
            retry = operation.headers.get("Retry-After", "none")
            print(f"pending: operation_http={operation.status_code} retry_after={retry} alpha_status={status} pending_checks={len(pending)}")
            last_report = now
        try:
            wait = float(operation.headers.get("Retry-After", 10) or 10)
        except (TypeError, ValueError):
            wait = 10
        time.sleep(max(0.1, wait))

    print("RESULT: TIMEOUT - no terminal result")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
