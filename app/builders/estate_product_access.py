from __future__ import annotations
try:
    from app.shared._project_bootstrap import ensure_project_root_on_path
except Exception:
    from _project_bootstrap import ensure_project_root_on_path
ensure_project_root_on_path()

import argparse
import json
import os
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


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


def token_expired(payload: Dict[str, Any], skew_seconds: int = 120) -> bool:
    try:
        expires_at = int(payload.get('expires_at_epoch') or 0)
    except Exception:
        expires_at = 0
    return expires_at <= int(datetime.now(timezone.utc).timestamp()) + skew_seconds


def save_token_payload(token_path: Path, previous: Dict[str, Any], refreshed: Dict[str, Any]) -> Dict[str, Any]:
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    merged = dict(previous or {})
    merged.update(refreshed or {})
    merged['saved_at_epoch'] = now_epoch
    try:
        expires_in = int(merged.get('expires_in') or refreshed.get('expires_in') or 3600)
    except Exception:
        expires_in = 3600
    merged['expires_at_epoch'] = now_epoch + expires_in
    token_path.write_text(json.dumps(merged, indent=2), encoding='utf-8')
    return merged


def refresh_tokens(token_path: Path, payload: Dict[str, Any], env: Dict[str, str]) -> Dict[str, Any]:
    refresh_token = payload.get('refresh_token')
    token_url = env.get('ATLASSIAN_TOKEN_URL')
    client_id = env.get('ATLASSIAN_CLIENT_ID')
    client_secret = env.get('ATLASSIAN_CLIENT_SECRET')
    if not refresh_token or not token_url or not client_id or not client_secret:
        return payload

    body = urllib.parse.urlencode({
        'grant_type': 'refresh_token',
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token,
    }).encode('utf-8')
    req = urllib.request.Request(
        url=token_url,
        data=body,
        headers={
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'JOM-oauth-token-refresh/1.0',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            raw = response.read().decode('utf-8', errors='replace')
            refreshed = json.loads(raw)
            return save_token_payload(token_path, payload, refreshed)
    except Exception:
        return payload


def get_token() -> str:
    """Resolve a valid Atlassian OAuth access token from existing backend sources.

    Environment variables remain supported for local override. Otherwise JOM
    uses tokens.json. If tokens.json is expired and has a refresh_token, JOM
    refreshes it using ATLASSIAN_TOKEN_URL, ATLASSIAN_CLIENT_ID, and
    ATLASSIAN_CLIENT_SECRET from .env.
    """
    env = load_env()
    for key in ('ATLASSIAN_TOKEN', 'ATLASSIAN_ACCESS_TOKEN', 'JOM_ATLASSIAN_ACCESS_TOKEN'):
        value = env.get(key)
        if value:
            return value

    token_path = ROOT / 'tokens.json'
    if not token_path.exists():
        return ''
    try:
        payload = json.loads(token_path.read_text(encoding='utf-8-sig'))
    except Exception:
        return ''

    if token_expired(payload):
        payload = refresh_tokens(token_path, payload, env)

    value = payload.get('access_token')
    return str(value) if value else ''
def request_json(url: str, token: str) -> Dict[str, Any]:
    req = urllib.request.Request(
        url=url,
        headers={
            'Authorization': 'Bearer ' + token,
            'Accept': 'application/json',
            'User-Agent': 'JOM-live-product-access-collector/1.0',
        },
        method='GET',
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            body = response.read().decode('utf-8', errors='replace')
            try:
                return {'ok': True, 'status_code': response.status, 'data': json.loads(body)}
            except Exception:
                return {'ok': False, 'status_code': response.status, 'error': 'invalid json response', 'body_preview': body[:500]}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')
        return {'ok': False, 'status_code': exc.code, 'error': body[:1000]}
    except Exception as exc:
        return {'ok': False, 'status_code': 0, 'error': str(exc)}


def normalise_url(value: Any) -> str:
    return str(value or '').strip().rstrip('/')


def site_key_from_resource(resource: Dict[str, Any]) -> str:
    url = normalise_url(resource.get('url')).lower()
    if '.atlassian.net' in url:
        host = url.split('//')[-1].split('/')[0]
        return host.replace('.atlassian.net', '')
    return str(resource.get('name') or '').strip().lower().replace(' ', '-')


def to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except Exception:
        return default


def role_key(role: Dict[str, Any]) -> str:
    return str(role.get('key') or role.get('name') or '').strip()


def role_name(role: Dict[str, Any]) -> str:
    return str(role.get('name') or role.get('key') or '').strip()


def is_jira_role(role: Dict[str, Any]) -> bool:
    key = role_key(role).lower()
    name = role_name(role).lower()
    return 'jira' in key or 'jira' in name


def role_user_count(role: Dict[str, Any]) -> int:
    for candidate in ('userCount', 'currentUserCount', 'numberOfUsers', 'usersCount'):
        if candidate in role:
            return to_int(role.get(candidate), 0)
    users = role.get('users')
    if isinstance(users, list):
        return len(users)
    return 0


def role_seat_limit(role: Dict[str, Any]) -> int:
    for candidate in ('numberOfSeats', 'seats', 'maximumSeats', 'limit'):
        if candidate in role:
            return to_int(role.get(candidate), 0)
    return 0


def role_remaining(role: Dict[str, Any]) -> int:
    for candidate in ('remainingSeats', 'remaining', 'availableSeats'):
        if candidate in role:
            return to_int(role.get(candidate), 0)
    limit = role_seat_limit(role)
    used = role_user_count(role)
    return max(limit - used, 0) if limit else 0


def collect_product_access(include_all_resources: bool = True) -> Dict[str, Any]:
    token = get_token()
    if not token:
        return {
            'source': 'Atlassian Cloud API live collector',
            'generated_at_utc': iso_now(),
            'schema': 'jom-estate-product-access-v2-live',
            'live_collection': True,
            'status': 'missing_credentials',
            'summary': {
                'accessible_jira_resource_count': 0,
                'sites_with_jira_roles': 0,
                'total_jira_product_user_count': 0,
                'total_jira_seat_limit': 0,
                'total_jira_remaining_seats': 0,
                'jira_role_rows': 0,
                'error_site_count': 0,
            },
            'sites': [],
            'roles': [],
            'errors': {'credentials': ['No ATLASSIAN_TOKEN, ATLASSIAN_ACCESS_TOKEN, or JOM_ATLASSIAN_ACCESS_TOKEN found.']},
            'notes': ['No stale static product-access data was used.'],
        }

    resources_result = request_json('https://api.atlassian.com/oauth/token/accessible-resources', token)
    if not resources_result.get('ok'):
        return {
            'source': 'Atlassian Cloud API live collector',
            'generated_at_utc': iso_now(),
            'schema': 'jom-estate-product-access-v2-live',
            'live_collection': True,
            'status': 'accessible_resources_failed',
            'summary': {
                'accessible_jira_resource_count': 0,
                'sites_with_jira_roles': 0,
                'total_jira_product_user_count': 0,
                'total_jira_seat_limit': 0,
                'total_jira_remaining_seats': 0,
                'jira_role_rows': 0,
                'error_site_count': 1,
            },
            'sites': [],
            'roles': [],
            'errors': {'accessible_resources': [resources_result.get('error') or str(resources_result)]},
            'notes': ['No stale static product-access data was used.'],
        }

    resources = resources_result.get('data') or []
    if not isinstance(resources, list):
        resources = []

    site_rows: List[Dict[str, Any]] = []
    role_rows: List[Dict[str, Any]] = []
    errors: Dict[str, List[str]] = {}

    for resource in resources:
        if not isinstance(resource, dict):
            continue
        site_key = site_key_from_resource(resource)
        cloud_id = str(resource.get('id') or resource.get('cloudId') or '').strip()
        site_url = normalise_url(resource.get('url'))
        site_name = str(resource.get('name') or site_key).strip()
        if not cloud_id:
            errors.setdefault(site_key or 'unknown', []).append('Accessible resource did not expose a cloud id.')
            continue

        url = 'https://api.atlassian.com/ex/jira/' + cloud_id + '/rest/api/3/applicationrole'
        result = request_json(url, token)
        if not result.get('ok'):
            errors.setdefault(site_key, []).append(str(result.get('error') or result.get('status_code') or 'unknown application role error'))
            site_rows.append({
                'site_key': site_key,
                'site_name': site_name,
                'site_url': site_url,
                'cloud_id': cloud_id,
                'jira_product_user_count': 0,
                'jira_product_seat_limit': 0,
                'jira_product_remaining_seats': 0,
                'jira_role_count': 0,
                'status': 'error',
            })
            continue

        data = result.get('data', [])
        if isinstance(data, dict):
            roles = data.get('values') or data.get('applicationRoles') or data.get('roles') or []
        else:
            roles = data
        if not isinstance(roles, list):
            roles = []

        jira_roles = [role for role in roles if isinstance(role, dict) and is_jira_role(role)]
        site_used = 0
        site_limit = 0
        site_remaining = 0
        for role in jira_roles:
            used = role_user_count(role)
            limit = role_seat_limit(role)
            remaining = role_remaining(role)
            site_used += used
            site_limit += limit
            site_remaining += remaining
            role_rows.append({
                'site_key': site_key,
                'site_name': site_name,
                'site_url': site_url,
                'cloud_id': cloud_id,
                'role_key': role_key(role),
                'role_name': role_name(role),
                'user_count': used,
                'seat_limit': limit,
                'remaining_seats': remaining,
                'raw_has_default_groups': bool(role.get('defaultGroups')),
                'raw_platform': role.get('platform', ''),
                'raw_selected_by_default': role.get('selectedByDefault', ''),
            })
        site_rows.append({
            'site_key': site_key,
            'site_name': site_name,
            'site_url': site_url,
            'cloud_id': cloud_id,
            'jira_product_user_count': site_used,
            'jira_product_seat_limit': site_limit,
            'jira_product_remaining_seats': site_remaining,
            'jira_role_count': len(jira_roles),
            'status': 'ok',
        })

    total_users = sum(to_int(row.get('jira_product_user_count'), 0) for row in site_rows)
    total_limit = sum(to_int(row.get('jira_product_seat_limit'), 0) for row in site_rows)
    total_remaining = sum(to_int(row.get('jira_product_remaining_seats'), 0) for row in site_rows)
    return {
        'source': 'Atlassian Cloud API live collector: accessible-resources + /rest/api/3/applicationrole',
        'generated_at_utc': iso_now(),
        'schema': 'jom-estate-product-access-v2-live',
        'live_collection': True,
        'status': 'ok' if not errors else 'partial',
        'scope': 'all accessible Jira resources returned by Atlassian OAuth accessible-resources',
        'summary': {
            'accessible_jira_resource_count': len(resources),
            'sites_with_jira_roles': len([row for row in site_rows if to_int(row.get('jira_role_count'), 0) > 0]),
            'total_jira_product_user_count': total_users,
            'total_jira_seat_limit': total_limit,
            'total_jira_remaining_seats': total_remaining,
            'jira_role_rows': len(role_rows),
            'error_site_count': len(errors),
        },
        'sites': site_rows,
        'roles': role_rows,
        'errors': errors,
        'notes': [
            'This is live product/application role access truth, not /users/search visibility truth.',
            'No stale static product-access data was used.',
            'Where applicationrole payloads do not expose seat limits, fields are left as 0 rather than guessed.',
        ],
    }


def build_access_truth(product_payload: Dict[str, Any], admin_payload_path: Path | None = None, billing_payload_path: Path | None = None) -> Dict[str, Any]:
    product_summary = product_payload.get('summary', {}) if isinstance(product_payload, dict) else {}
    product_user_count = to_int(product_summary.get('total_jira_product_user_count'), 0)
    return {
        'source': 'Derived from live estate_product_access payload; billing is not used as website truth',
        'generated_at_utc': iso_now(),
        'schema': 'jom-estate-access-truth-v2-live',
        'live_collection': True,
        'summary': {
            'api_product_user_count': product_user_count,
            'accessible_jira_resource_count': to_int(product_summary.get('accessible_jira_resource_count'), 0),
            'sites_with_jira_roles': to_int(product_summary.get('sites_with_jira_roles'), 0),
        },
        'product_summary': product_summary,
        'site_product_access': product_payload.get('sites', []),
        'role_product_access': product_payload.get('roles', []),
        'interpretation': [
            'API product role user counts are live estate/product access signals.',
            'Billing snapshots are not website truth.',
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Collect live estate-wide Jira product access using Atlassian application roles.')
    parser.add_argument('--project-root', default='.')
    parser.add_argument('--product-output', default='static/data/estate_product_access.json')
    parser.add_argument('--truth-output', default='static/data/estate_access_truth.json')
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    product_output = Path(args.product_output)
    truth_output = Path(args.truth_output)
    if not product_output.is_absolute():
        product_output = project_root / product_output
    if not truth_output.is_absolute():
        truth_output = project_root / truth_output
    product_payload = collect_product_access()
    product_output.parent.mkdir(parents=True, exist_ok=True)
    product_output.write_text(json.dumps(product_payload, indent=2, ensure_ascii=False), encoding='utf-8')
    truth_payload = build_access_truth(product_payload)
    truth_output.parent.mkdir(parents=True, exist_ok=True)
    truth_output.write_text(json.dumps(truth_payload, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'product_access_status': product_payload.get('status'), 'summary': product_payload.get('summary')}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
