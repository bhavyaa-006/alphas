"""BRAIN credentials: stored once in <home>/.env (private), exported as the
env vars ace_lib.get_credentials() already looks for."""
from __future__ import annotations

import getpass
import os

from .util import load_dotenv, set_dotenv_value


def ensure_credentials(home) -> tuple:
    load_dotenv(home / ".env")
    email = os.environ.get("BRAIN_CREDENTIAL_EMAIL")
    password = os.environ.get("BRAIN_CREDENTIAL_PASSWORD")
    if email and password:
        print(f"using saved BRAIN login for {email}  (from {home / '.env'})")
        return email, password

    print(f"No saved BRAIN login found at {home / '.env'}")
    print("(if you expected one to be there already, you're likely running this from a "
          "different --home / working directory than last time - see USAGE.md)")
    print("BRAIN login (stored locally in", home / ".env", "- never sent anywhere but WorldQuant's API)")
    email = input("Email: ").strip()
    password = getpass.getpass("Password: ")
    set_dotenv_value(home / ".env", "BRAIN_CREDENTIAL_EMAIL", email)
    set_dotenv_value(home / ".env", "BRAIN_CREDENTIAL_PASSWORD", password)
    return email, password
