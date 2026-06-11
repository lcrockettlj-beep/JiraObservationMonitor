import json
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("ATLASSIAN_CLIENT_ID")
CLIENT_SECRET = os.getenv("ATLASSIAN_CLIENT_SECRET")
REDIRECT_URI = os.getenv("ATLASSIAN_REDIRECT_URI", "http://localhost:8090/callback")

AUTH_URL = "https://auth.atlassian.com/authorize"
TOKEN_URL = "https://auth.atlassian.com/oauth/token"
TOKEN_FILE = "tokens.json"

SCOPES = [
    "read:jira-work",
    "read:jira-user",
    "read:me",
    "read:application-role:jira",
    "read:user:jira",
    "offline_access"
]


def validate_auth_config():
    missing = []

    if not CLIENT_ID:
        missing.append("ATLASSIAN_CLIENT_ID")

    if not CLIENT_SECRET:
        missing.append("ATLASSIAN_CLIENT_SECRET")

    if not REDIRECT_URI:
        missing.append("ATLASSIAN_REDIRECT_URI")

    if missing:
        raise ValueError(
            "Missing required values in .env: " + ", ".join(missing)
        )


def generate_state():
    return secrets.token_urlsafe(24)


def get_auth_url(state):
    validate_auth_config()

    params = {
        "audience": "api.atlassian.com",
        "client_id": CLIENT_ID,
        "scope": " ".join(SCOPES),
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "response_type": "code",
        "prompt": "consent"
    }

    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def load_token_bundle():
    if not os.path.exists(TOKEN_FILE):
        return None

    with open(TOKEN_FILE, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_token_bundle(token_data):
    token_copy = dict(token_data)

    expires_in = int(token_copy.get("expires_in", 3600))
    token_copy["expires_at"] = int(time.time()) + expires_in - 60

    with open(TOKEN_FILE, "w", encoding="utf-8") as handle:
        json.dump(token_copy, handle, indent=2)

    return token_copy


def token_is_valid(token_bundle):
    if not token_bundle:
        return False

    access_token = token_bundle.get("access_token")
    expires_at = token_bundle.get("expires_at", 0)

    if not access_token:
        return False

    return time.time() < expires_at


def exchange_code_for_token(code):
    validate_auth_config()

    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI
    }

    response = requests.post(
        TOKEN_URL,
        json=payload,
        headers={"Accept": "application/json"},
        timeout=30
    )
    response.raise_for_status()
    return response.json()


def refresh_access_token(refresh_token):
    validate_auth_config()

    payload = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token
    }

    response = requests.post(
        TOKEN_URL,
        json=payload,
        headers={"Accept": "application/json"},
        timeout=30
    )
    response.raise_for_status()
    return response.json()


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    auth_code = None
    auth_state = None
    auth_error = None
    callback_path = "/callback"

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path != self.callback_path:
            self.send_response(404)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        query = urllib.parse.parse_qs(parsed.query)

        OAuthCallbackHandler.auth_code = query.get("code", [None])[0]
        OAuthCallbackHandler.auth_state = query.get("state", [None])[0]
        OAuthCallbackHandler.auth_error = query.get("error", [None])[0]

        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"""
            <html>
              <head><title>Jira Observation Monitor</title></head>
              <body>
                <h2>Authentication complete</h2>
                <p>You can close this browser tab and return to PowerShell.</p>
              </body>
            </html>
            """
        )

        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, format, *args):
        return


def wait_for_callback(expected_state, timeout_seconds=300):
    parsed_redirect = urllib.parse.urlparse(REDIRECT_URI)
    host = parsed_redirect.hostname or "localhost"
    port = parsed_redirect.port or 8090
    callback_path = parsed_redirect.path or "/callback"

    OAuthCallbackHandler.auth_code = None
    OAuthCallbackHandler.auth_state = None
    OAuthCallbackHandler.auth_error = None
    OAuthCallbackHandler.callback_path = callback_path

    server = HTTPServer((host, port), OAuthCallbackHandler)

    print(f"Listening for OAuth callback on {REDIRECT_URI} ...")
    server.handle_request()

    if OAuthCallbackHandler.auth_error:
        raise ValueError(
            f"Atlassian returned an OAuth error: {OAuthCallbackHandler.auth_error}"
        )

    if not OAuthCallbackHandler.auth_code:
        raise TimeoutError("No authorization code received from callback.")

    if OAuthCallbackHandler.auth_state != expected_state:
        raise ValueError("OAuth state mismatch. Aborting for safety.")

    return OAuthCallbackHandler.auth_code


def run_interactive_oauth_flow():
    state = generate_state()
    auth_url = get_auth_url(state)

    print()
    print("AUTH URL BELOW - COPY THIS INTO YOUR BROWSER IF IT DOES NOT OPEN:")
    print(auth_url)
    print()

    try:
        opened = webbrowser.open(auth_url, new=2)
        print(f"Browser open attempted: {opened}")
    except Exception as exc:
        print(f"Browser open failed: {exc}")

    code = wait_for_callback(state)
    token_data = exchange_code_for_token(code)
    saved = save_token_bundle(token_data)

    print("OAuth token exchange successful.")
    print(f"Tokens saved to {TOKEN_FILE}")
    print()

    return saved["access_token"]


def get_valid_access_token():
    token_bundle = load_token_bundle()

    if token_is_valid(token_bundle):
        return token_bundle["access_token"]

    if token_bundle and token_bundle.get("refresh_token"):
        print("Refreshing expired access token...")
        refreshed = refresh_access_token(token_bundle["refresh_token"])
        saved = save_token_bundle(refreshed)
        return saved["access_token"]

    return None