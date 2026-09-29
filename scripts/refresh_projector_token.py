"""
Scheduled by .github/workflows/refresh-projector-token.yml.
Refreshes the Projector OAuth token and rewrites token_relay/token_public.json
so it always holds a currently-valid access_token — this file (read via the
GitHub Contents API) is the "relay": no server to host, GitHub serves it.

Requires these repo secrets:
  PROJECTOR_TOKEN_URL, PROJECTOR_CLIENT_ID, PROJECTOR_CLIENT_SECRET
The refresh_token itself is NOT a secret input — it's read from (and rewritten
to) token_relay/token_public.json each run, since Projector rotates it on
every use and the file must always hold the latest one.
"""
import json
import os
import sys
import time

import requests

STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "token_relay", "token_public.json")


def main():
    with open(STORE_PATH) as f:
        current = json.load(f)

    resp = requests.post(
        os.environ["PROJECTOR_TOKEN_URL"],
        data={
            "grant_type": "refresh_token",
            "refresh_token": current["refresh_token"],
            "client_id": os.environ["PROJECTOR_CLIENT_ID"],
            "client_secret": os.environ["PROJECTOR_CLIENT_SECRET"],
        },
        timeout=15,
    )

    if resp.status_code != 200:
        print(f"Refresh failed: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)

    new_data = resp.json()
    new_data["obtained_at"] = int(time.time())

    with open(STORE_PATH, "w") as f:
        json.dump(new_data, f, indent=2)

    print("Token refreshed and written to", STORE_PATH)


if __name__ == "__main__":
    main()
