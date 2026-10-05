"""Standalone diagnostic for one BRAIN alpha submission.

This deliberately bypasses alphapilot.engine and brain_client.submit_alpha.
It makes one POST, then polls both the returned submission URL and the alpha URL.
"""
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


def safe_headers(headers):
    return {
        key: value
        for key, value in dict(headers).items()
        if key.lower() not in {"set-cookie", "cookie", "authorization"}
    }


def response_snapshot(response):
    try:
        body = response.json()
    except Exception:
        body = response.text[:4000]
    return {
        "http": response.status_code,
        "headers": safe_headers(response.headers),
        "body": body,
    }


def get_json(session, url):
    response = session.get(url)
    try:
        body = response.json()
    except Exception:
        body = response.text[:4000]
    return response, body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("alpha_id", nargs="?", default="RR6nZ131")
    parser.add_argument("--home", default=os.environ.get("ALPHAPILOT_HOME", "data"))
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--interval", type=float, default=10)
    args = parser.parse_args()

    home = CFG.resolve_home(args.home)
    cfg = CFG.load_config(home)
    session = BC.ensure_session(ace, cfg, home)
    base_url = ace.brain_api_url.rstrip("/")
    alpha_url = f"{base_url}/alphas/{args.alpha_id}"
    submit_url = f"{alpha_url}/submit"

    print(f"alpha: {args.alpha_id}")
    print(f"home: {home}")
    before, before_body = get_json(session, alpha_url)
    print("\nBEFORE alpha GET")
    print(json.dumps({"http": before.status_code, "body": before_body}, indent=2, default=str))

    post = session.post(submit_url)
    print("\nSUBMIT POST")
    print(json.dumps(response_snapshot(post), indent=2, default=str))
    if post.status_code not in (200, 201, 202):
        return 0

    operation_url = post.headers.get("Location")
    if operation_url:
        operation_url = urljoin(base_url + "/", operation_url)
    print(f"\noperation URL: {operation_url or '(missing)'}")

    deadline = time.time() + args.seconds
    poll = 0
    while time.time() < deadline:
        poll += 1
        print(f"\nPOLL {poll}")
        if operation_url:
            operation, operation_body = get_json(session, operation_url)
            print("submission operation:")
            print(json.dumps({"http": operation.status_code, "headers": safe_headers(operation.headers), "body": operation_body}, indent=2, default=str))
        alpha, alpha_body = get_json(session, alpha_url)
        print("alpha detail:")
        print(json.dumps({"http": alpha.status_code, "body": alpha_body}, indent=2, default=str))
        time.sleep(args.interval)

    print("\nDIAGNOSTIC TIMEOUT: no terminal result observed in the requested window")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
