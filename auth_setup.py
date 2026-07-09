"""
auth_setup.py

Run this ONCE to authorize this app against your WHOOP account.
It will:
  1. Open your browser to WHOOP's login/consent screen
  2. Spin up a tiny local server to catch the redirect
  3. Exchange the authorization code for an access + refresh token
  4. Save those tokens to tokens.json (gitignored, never commit this file)

After this runs successfully, whoop_sync.py can refresh tokens on its own
and you should not need to run this script again unless you revoke access
or your refresh token is invalidated.
"""

import http.server
import json
import os
import secrets
import threading
import urllib.parse
import webbrowser

import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["WHOOP_CLIENT_ID"]
CLIENT_SECRET = os.environ["WHOOP_CLIENT_SECRET"]
REDIRECT_URI = os.environ.get("WHOOP_REDIRECT_URI", "http://localhost:8080/callback")

AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"

# Scopes: request everything the journal needs, plus "offline" for a refresh token
SCOPES = [
    "read:recovery",
    "read:cycles",
    "read:sleep",
    "read:workout",
    "read:profile",
    "read:body_measurement",
    "offline",
]

TOKENS_FILE = os.path.join(os.path.dirname(__file__), "tokens.json")

# Parsed from the redirect URI so the local server listens on the right port/path
_parsed_redirect = urllib.parse.urlparse(REDIRECT_URI)
CALLBACK_PATH = _parsed_redirect.path or "/callback"
CALLBACK_PORT = _parsed_redirect.port or 8080

_state = secrets.token_urlsafe(6)[:8]  # WHOOP requires state to be 8 characters
_result = {}


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != CALLBACK_PATH:
            self.send_response(404)
            self.end_headers()
            return

        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        returned_state = params.get("state", [None])[0]

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        if not code or returned_state != _state:
            self.wfile.write(b"<h1>Authorization failed or state mismatch. You can close this tab.</h1>")
            _result["error"] = "Missing code or state mismatch"
        else:
            self.wfile.write(b"<h1>WHOOP authorization successful. You can close this tab.</h1>")
            _result["code"] = code

    def log_message(self, format, *args):
        pass  # silence default request logging


def get_authorization_code():
    server = http.server.HTTPServer(("localhost", CALLBACK_PORT), CallbackHandler)
    thread = threading.Thread(target=server.handle_request)  # handle exactly one request
    thread.start()

    query = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": _state,
        "scope": " ".join(SCOPES),
    })
    full_auth_url = f"{AUTH_URL}?{query}"

    print("Opening your browser to authorize with WHOOP...")
    print(f"If it doesn't open automatically, visit:\n{full_auth_url}\n")
    webbrowser.open(full_auth_url)

    thread.join(timeout=180)  # wait up to 3 minutes for the user to approve

    if "error" in _result:
        raise RuntimeError(f"Authorization failed: {_result['error']}")
    if "code" not in _result:
        raise RuntimeError("Timed out waiting for WHOOP authorization.")

    return _result["code"]


def exchange_code_for_tokens(code):
    response = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
    })
    response.raise_for_status()
    return response.json()


def main():
    code = get_authorization_code()
    tokens = exchange_code_for_tokens(code)

    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)

    print(f"\nSuccess! Tokens saved to {TOKENS_FILE}")
    print("You can now run whoop_sync.py to pull your data.")


if __name__ == "__main__":
    main()
