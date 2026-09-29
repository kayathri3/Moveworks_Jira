"""
Projector Token Relay Service
------------------------------
Solves the Moveworks limitation where the OAuth2 connector can only auto-inject
a live access token into the Authorization HEADER, never into a custom query
parameter like `SessionTicket` (confirmed by Moveworks support, ticket CS9539089).

This tiny Flask service sits between Moveworks and Projector:
  - Holds the current access_token + refresh_token (persisted to disk, since
    Projector's refresh_token is single-use/rotating — each refresh invalidates
    the old one and issues a new one).
  - Only calls Projector's /oauth2token refresh endpoint when the cached token
    is close to expiry (Projector's session tickets last 604800s / 7 days).
  - Exposes GET /token, protected by an X-Relay-Key header, that Moveworks'
    "Get Relay Access Token" HTTP Action calls before "Get PM Projects".

Moveworks flow:
  1. HTTP Action "Get Relay Access Token" -> GET {relay_base_url}/token
     Header: X-Relay-Key: {{relay_api_key}}
  2. HTTP Action "Get PM Projects" -> SessionTicket = {{get_relay_access_token.access_token}}

Run locally for testing:
    python token_relay_service.py
For production, run behind a real WSGI server, e.g.:
    waitress-serve --listen=0.0.0.0:5000 token_relay_service:app
"""
import json
import os
import threading
import time

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv()

PROJECTOR_TOKEN_URL = os.environ["PROJECTOR_TOKEN_URL"]
PROJECTOR_CLIENT_ID = os.environ["PROJECTOR_CLIENT_ID"]
PROJECTOR_CLIENT_SECRET = os.environ["PROJECTOR_CLIENT_SECRET"]
RELAY_API_KEY = os.environ["RELAY_API_KEY"]

# Seed file: first run should contain a valid access_token + refresh_token
# obtained once via the interactive browser flow (see go.py).
TOKEN_STORE_PATH = os.environ.get("TOKEN_STORE_PATH", "token_store.json")

# Refresh this long before actual expiry to avoid ever serving a dead token.
REFRESH_BUFFER_SECONDS = 60 * 60 * 24  # 1 day

_lock = threading.Lock()
app = Flask(__name__)


def _load_store():
    if not os.path.exists(TOKEN_STORE_PATH):
        # First boot on a fresh host/volume — bootstrap from a secret env var
        # instead of requiring a manual file upload to the server.
        seed = os.environ.get("TOKEN_STORE_SEED")
        if not seed:
            raise RuntimeError(
                f"{TOKEN_STORE_PATH} not found and TOKEN_STORE_SEED env var not set. "
                "Run go.py locally once and set TOKEN_STORE_SEED to that JSON."
            )
        _save_store(json.loads(seed))

    with open(TOKEN_STORE_PATH, "r") as f:
        data = json.load(f)
    data.setdefault("obtained_at", time.time())
    return data


def _save_store(data):
    with open(TOKEN_STORE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _is_expiring_soon(data):
    obtained_at = data.get("obtained_at", 0)
    expires_in = data.get("expires_in", 0)
    return time.time() >= (obtained_at + expires_in - REFRESH_BUFFER_SECONDS)


def _refresh(data):
    resp = requests.post(
        PROJECTOR_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": data["refresh_token"],
            "client_id": PROJECTOR_CLIENT_ID,
            "client_secret": PROJECTOR_CLIENT_SECRET,
        },
        timeout=15,
    )
    resp.raise_for_status()
    new_data = resp.json()
    new_data["obtained_at"] = time.time()
    return new_data


def get_valid_token():
    """Return a fresh token dict, refreshing + persisting it if near expiry."""
    with _lock:
        data = _load_store()
        if _is_expiring_soon(data):
            data = _refresh(data)
            _save_store(data)
        return data


@app.route("/token", methods=["GET"])
def token():
    if request.headers.get("X-Relay-Key") != RELAY_API_KEY:
        return jsonify({"error": "unauthorized"}), 401

    try:
        data = get_valid_token()
    except requests.HTTPError as exc:
        # Refresh token was rejected (e.g. already rotated elsewhere) —
        # needs a manual re-seed of token_store.json via go.py.
        return jsonify({
            "error": "refresh_failed",
            "detail": exc.response.text if exc.response is not None else str(exc),
        }), 502

    return jsonify({
        "access_token": data["access_token"],
        "rest_service_authority": data.get("rest_service_authority"),
        "soap_service_authority": data.get("soap_service_authority"),
    })


if __name__ == "__main__":
    # Dev-only entrypoint; use a production WSGI server for real deployments.
    app.run(host="127.0.0.1", port=5000)
