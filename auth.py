from __future__ import annotations

import json
import os
import secrets
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
TOKEN_PATH = BASE_DIR / "tokens.json"
STATE_PATH = BASE_DIR / ".auth_state.json"

DEFAULT_AUTH_URL = "https://auth.atlassian.com/authorize"
DEFAULT_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
ACCESSIBLE_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"
AUDIENCE = "api.atlassian.com"


def _load_env_file(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required setting: {name}. Add it to .env")
    return value


def get_config() -> Dict[str, str]:
    return {
        "client_id": _required("ATLASSIAN_CLIENT_ID"),
        "client_secret": _required("ATLASSIAN_CLIENT_SECRET"),
        "redirect_uri": _required("ATLASSIAN_REDIRECT_URI"),
        "scopes": _required("ATLASSIAN_SCOPES"),
        "auth_url": os.getenv("ATLASSIAN_AUTH_URL", DEFAULT_AUTH_URL).strip() or DEFAULT_AUTH_URL,
        "token_url": os.getenv("ATLASSIAN_TOKEN_URL", DEFAULT_TOKEN_URL).strip() or DEFAULT_TOKEN_URL,
    }


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")



def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}



def save_token_data(token_data: Dict[str, Any]) -> Dict[str, Any]:
    token_data = dict(token_data or {})
    expires_in = int(token_data.get("expires_in", 3600) or 3600)
    token_data["saved_at_epoch"] = int(time.time())
    token_data["expires_at_epoch"] = int(time.time()) + max(expires_in - 60, 60)
    _save_json(TOKEN_PATH, token_data)
    return token_data



def load_token_data() -> Dict[str, Any]:
    return _load_json(TOKEN_PATH)



def token_is_expired(token_data: Optional[Dict[str, Any]] = None) -> bool:
    token_data = token_data or load_token_data()
    expires_at = int(token_data.get("expires_at_epoch", 0) or 0)
    return not expires_at or int(time.time()) >= expires_at



def _http_json(url: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, payload: Optional[Dict[str, Any]] = None) -> Any:
    headers = headers or {}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers = {**headers, "Content-Type": "application/json"}
    req = urllib.request.Request(url=url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} calling {url}: {raw}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error calling {url}: {exc}") from exc



def _save_state(state: str) -> None:
    _save_json(STATE_PATH, {"state": state, "saved_at_epoch": int(time.time())})



def _load_state() -> str:
    return _load_json(STATE_PATH).get("state", "")



def build_authorization_url(open_browser_hint: bool = False) -> str:
    config = get_config()
    state = secrets.token_urlsafe(24)
    _save_state(state)
    params = {
        "audience": AUDIENCE,
        "client_id": config["client_id"],
        "scope": config["scopes"],
        "redirect_uri": config["redirect_uri"],
        "state": state,
        "response_type": "code",
        "prompt": "consent",
    }
    return f"{config['auth_url']}?{urllib.parse.urlencode(params)}"



def _extract_code_and_state(user_input: str) -> Dict[str, str]:
    text = (user_input or "").strip()
    if not text:
        raise RuntimeError("No callback URL or code was provided.")
    if text.startswith("http://") or text.startswith("https://"):
        parsed = urllib.parse.urlparse(text)
        params = urllib.parse.parse_qs(parsed.query)
        return {
            "code": (params.get("code") or [""])[0],
            "state": (params.get("state") or [""])[0],
        }
    return {"code": text, "state": ""}



def exchange_code_for_token(code: str, state: str = "") -> Dict[str, Any]:
    if not code:
        raise RuntimeError("Authorization code is empty.")
    saved_state = _load_state()
    if state and saved_state and state != saved_state:
        raise RuntimeError("Returned state does not match saved auth state.")

    config = get_config()
    payload = {
        "grant_type": "authorization_code",
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "code": code,
        "redirect_uri": config["redirect_uri"],
    }
    token_data = _http_json(config["token_url"], method="POST", payload=payload)
    return save_token_data(token_data)



def refresh_access_token() -> Dict[str, Any]:
    config = get_config()
    token_data = load_token_data()
    refresh_token = token_data.get("refresh_token", "")
    if not refresh_token:
        raise RuntimeError("No refresh_token found in tokens.json. Run login again.")
    payload = {
        "grant_type": "refresh_token",
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "refresh_token": refresh_token,
    }
    refreshed = _http_json(config["token_url"], method="POST", payload=payload)
    if not refreshed.get("refresh_token"):
        refreshed["refresh_token"] = refresh_token
    return save_token_data(refreshed)



def get_valid_access_token() -> str:
    token_data = load_token_data()
    access_token = token_data.get("access_token", "")
    if not access_token:
        raise RuntimeError("No access token found. Run: python auth.py login")
    if token_is_expired(token_data):
        token_data = refresh_access_token()
    return token_data.get("access_token", "")



def get_accessible_resources(access_token: Optional[str] = None) -> List[Dict[str, Any]]:
    token = access_token or get_valid_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    resources = _http_json(ACCESSIBLE_RESOURCES_URL, headers=headers)
    return resources if isinstance(resources, list) else []



def get_accessible_jira_resources(access_token: Optional[str] = None) -> List[Dict[str, Any]]:
    resources = get_accessible_resources(access_token=access_token)
    jira_like = []
    for item in resources:
        scopes = item.get("scopes", []) or []
        scope_text = " ".join(str(s) for s in scopes)
        if "jira" in scope_text.lower() or str(item.get("url", "")).endswith("atlassian.net"):
            jira_like.append(item)
    return jira_like



def print_resources(resources: List[Dict[str, Any]]) -> None:
    if not resources:
        print("No accessible resources were returned.")
        return
    print("Accessible resources:")
    for index, item in enumerate(resources, start=1):
        print(f"[{index}] {item.get('name', '')}")
        print(f"    id: {item.get('id', '')}")
        print(f"    url: {item.get('url', '')}")
        scopes = item.get('scopes', []) or []
        print(f"    scopes: {', '.join(str(s) for s in scopes)}")



def login_interactive() -> None:
    url = build_authorization_url()
    print("Open this Atlassian authorization URL in your browser:")
    print(url)
    print()
    print("After approving access, the browser will redirect to your ATLASSIAN_REDIRECT_URI.")
    print("Copy the FULL redirected URL from the browser address bar and paste it below.")
    print("If you only have the code value, you can paste just the code.")
    callback_input = input("Paste callback URL or code: ").strip()
    parsed = _extract_code_and_state(callback_input)
    token_data = exchange_code_for_token(parsed.get("code", ""), state=parsed.get("state", ""))
    print("Token saved to tokens.json")
    print(f"Access token expires at epoch: {token_data.get('expires_at_epoch')}")
    resources = get_accessible_jira_resources(token_data.get("access_token", ""))
    print_resources(resources)



def show_token_status() -> None:
    token_data = load_token_data()
    if not token_data:
        print("No tokens.json file found.")
        return
    print("Token file present.")
    print(f"Token expired: {'Yes' if token_is_expired(token_data) else 'No'}")
    print(f"Access token present: {'Yes' if bool(token_data.get('access_token')) else 'No'}")
    print(f"Refresh token present: {'Yes' if bool(token_data.get('refresh_token')) else 'No'}")
    print(f"Expires at epoch: {token_data.get('expires_at_epoch', '')}")



def main(argv: List[str]) -> int:
    command = argv[1].strip().lower() if len(argv) > 1 else "help"
    try:
        if command == "login":
            login_interactive()
            return 0
        if command == "resources":
            resources = get_accessible_jira_resources()
            print_resources(resources)
            return 0
        if command == "token":
            show_token_status()
            return 0
        print("Usage:")
        print("  python auth.py login")
        print("  python auth.py resources")
        print("  python auth.py token")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
