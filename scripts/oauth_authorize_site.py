from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
CALLBACK_RESULT: Dict[str, Any] = {}


def now_epoch() -> int:
    return int(time.time())


def load_env() -> Dict[str, str]:
    values = dict(os.environ)
    env_path = ROOT / '.env'
    if env_path.exists():
        for raw in env_path.read_text(encoding='utf-8-sig', errors='ignore').splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_authorize_url(site_key: str, env: Dict[str, str]) -> str:
    auth_url = env.get('ATLASSIAN_AUTH_URL') or 'https://auth.atlassian.com/authorize'
    client_id = env.get('ATLASSIAN_CLIENT_ID') or ''
    redirect_uri = env.get('ATLASSIAN_REDIRECT_URI') or ''
    scopes = env.get('ATLASSIAN_SCOPES') or 'manage:jira-configuration offline_access read:application-role:jira read:jira-user read:jira-work read:license:jira'
    if not client_id or not redirect_uri:
        raise RuntimeError('ATLASSIAN_CLIENT_ID and ATLASSIAN_REDIRECT_URI are required in .env')
    params = {
        'audience': 'api.atlassian.com',
        'client_id': client_id,
        'scope': scopes,
        'redirect_uri': redirect_uri,
        'state': 'jom-site-oauth:' + site_key,
        'response_type': 'code',
        'prompt': 'consent',
    }
    return auth_url + '?' + urllib.parse.urlencode(params)


def exchange_code(code: str, env: Dict[str, str]) -> Dict[str, Any]:
    token_url = env.get('ATLASSIAN_TOKEN_URL') or ''
    client_id = env.get('ATLASSIAN_CLIENT_ID') or ''
    client_secret = env.get('ATLASSIAN_CLIENT_SECRET') or ''
    redirect_uri = env.get('ATLASSIAN_REDIRECT_URI') or ''
    if not token_url or not client_id or not client_secret or not redirect_uri:
        raise RuntimeError('ATLASSIAN_TOKEN_URL, ATLASSIAN_CLIENT_ID, ATLASSIAN_CLIENT_SECRET, and ATLASSIAN_REDIRECT_URI are required in .env')
    body = urllib.parse.urlencode({
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'redirect_uri': redirect_uri,
    }).encode('utf-8')
    req = urllib.request.Request(
        url=token_url,
        data=body,
        headers={
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'JOM-oauth-callback-handler/1.0',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read().decode('utf-8', errors='replace')
        payload = json.loads(raw)
    saved_at = now_epoch()
    expires_in = int(payload.get('expires_in') or 3600)
    payload['saved_at_epoch'] = saved_at
    payload['expires_at_epoch'] = saved_at + expires_in
    token_path = ROOT / 'tokens.json'
    token_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return payload


class CallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.path != '/callback':
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'JOM OAuth callback handler only accepts /callback')
            return
        if 'error' in query:
            CALLBACK_RESULT['error'] = query.get('error', ['unknown'])[0]
            CALLBACK_RESULT['error_description'] = query.get('error_description', [''])[0]
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Authorisation failed. You can close this browser window.')
            return
        code = query.get('code', [''])[0]
        state = query.get('state', [''])[0]
        if not code:
            CALLBACK_RESULT['error'] = 'missing_code'
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Missing authorisation code. You can close this browser window.')
            return
        CALLBACK_RESULT['code'] = code
        CALLBACK_RESULT['state'] = state
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'JOM authorisation received. You can close this browser window and return to PowerShell.')


def run_product_access_refresh() -> None:
    cmd = [sys.executable, '-m', 'app.builders.estate_product_access', '--project-root', '.']
    subprocess.run(cmd, cwd=ROOT, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description='Run JOM Atlassian OAuth authorisation callback flow for a site.')
    parser.add_argument('--site-key', required=True)
    parser.add_argument('--timeout-seconds', type=int, default=300)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()

    env = load_env()
    redirect_uri = env.get('ATLASSIAN_REDIRECT_URI') or ''
    parsed = urllib.parse.urlparse(redirect_uri)
    host = parsed.hostname or 'localhost'
    port = parsed.port or 8090
    if parsed.path != '/callback':
        raise RuntimeError('ATLASSIAN_REDIRECT_URI must end with /callback for this handler')

    authorize_url = build_authorize_url(args.site_key, env)
    print('Open this URL to authorise JOM for the selected site:')
    print(authorize_url)
    server = HTTPServer((host, port), CallbackHandler)
    server.timeout = 1
    if not args.no_browser:
        webbrowser.open(authorize_url)
    deadline = time.time() + args.timeout_seconds
    print(f'Waiting for OAuth callback on http://{host}:{port}/callback ...')
    while time.time() < deadline and 'code' not in CALLBACK_RESULT and 'error' not in CALLBACK_RESULT:
        server.handle_request()
    server.server_close()
    if 'error' in CALLBACK_RESULT:
        print(json.dumps({'ok': False, 'error': CALLBACK_RESULT}, indent=2))
        return 2
    if 'code' not in CALLBACK_RESULT:
        print(json.dumps({'ok': False, 'error': 'timeout waiting for callback'}, indent=2))
        return 3
    token_payload = exchange_code(CALLBACK_RESULT['code'], env)
    run_product_access_refresh()
    print(json.dumps({
        'ok': True,
        'site_key': args.site_key,
        'state': CALLBACK_RESULT.get('state'),
        'token_type': token_payload.get('token_type'),
        'scope': token_payload.get('scope'),
        'expires_at_epoch': token_payload.get('expires_at_epoch'),
        'saved_tokens_json': True,
        'product_access_refresh_requested': True,
        'finished_at_utc': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
