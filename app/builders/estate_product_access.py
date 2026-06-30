from __future__ import annotations

from _project_bootstrap import ensure_project_root_on_path
ensure_project_root_on_path()

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from jira_client import JiraApiClient


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


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
    # Keep Jira product roles, exclude Confluence/other application roles if returned.
    return 'jira' in key or 'jira' in name


def role_user_count(role: Dict[str, Any]) -> int:
    # Atlassian role payloads vary by endpoint/version/account permissions.
    for candidate in ('userCount', 'currentUserCount', 'numberOfUsers', 'usersCount'):
        if candidate in role:
            return to_int(role.get(candidate), 0)
    # Some payloads expose groups/users arrays; do not treat group count as users.
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
    client = JiraApiClient()
    resources = client.list_accessible_resources()
    site_rows: List[Dict[str, Any]] = []
    role_rows: List[Dict[str, Any]] = []
    errors: Dict[str, List[str]] = {}

    for resource in resources:
        site_key = site_key_from_resource(resource)
        cloud_id = str(resource.get('id') or resource.get('cloudId') or '').strip()
        site_url = normalise_url(resource.get('url'))
        site_name = str(resource.get('name') or site_key).strip()

        if not cloud_id:
            errors.setdefault(site_key or 'unknown', []).append('Accessible resource did not expose a cloud id.')
            continue

        result = client.get_application_roles(cloud_id)
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
            # Defensive shape support.
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
            row = {
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
            }
            role_rows.append(row)

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

    total_jira_product_users = sum(to_int(row.get('jira_product_user_count'), 0) for row in site_rows)
    total_jira_seat_limit = sum(to_int(row.get('jira_product_seat_limit'), 0) for row in site_rows)
    total_remaining = sum(to_int(row.get('jira_product_remaining_seats'), 0) for row in site_rows)

    return {
        'source': 'Jira Cloud API /rest/api/3/applicationrole via jira_client.py',
        'generated_at_utc': iso_now(),
        'schema': 'jom-estate-product-access-v1',
        'scope': 'all accessible Jira resources returned by Atlassian OAuth accessible-resources',
        'summary': {
            'accessible_jira_resource_count': len(resources),
            'sites_with_jira_roles': len([row for row in site_rows if to_int(row.get('jira_role_count'), 0) > 0]),
            'total_jira_product_user_count': total_jira_product_users,
            'total_jira_seat_limit': total_jira_seat_limit,
            'total_jira_remaining_seats': total_remaining,
            'jira_role_rows': len(role_rows),
            'error_site_count': len(errors),
        },
        'sites': site_rows,
        'roles': role_rows,
        'errors': errors,
        'notes': [
            'This is product/application role access truth, not /users/search visibility truth.',
            'This collector scans all Jira resources visible to the current OAuth token.',
            'Where applicationrole payloads do not expose seat limits, fields are left as 0 rather than guessed.',
        ],
    }


def build_access_truth(product_payload: Dict[str, Any], admin_payload_path: Path | None = None, billing_payload_path: Path | None = None) -> Dict[str, Any]:
    admin_summary: Dict[str, Any] = {}
    billing_summary: Dict[str, Any] = {}

    if admin_payload_path and admin_payload_path.exists():
        try:
            admin_payload = json.loads(admin_payload_path.read_text(encoding='utf-8'))
            estate = admin_payload.get('estate', {}) if isinstance(admin_payload, dict) else {}
            drill = admin_payload.get('drilldowns', {}) if isinstance(admin_payload, dict) else {}
            human_rows = ((drill.get('admin::human_accounts') or {}).get('rows') or []) if isinstance(drill, dict) else []
            app_rows = ((drill.get('admin::app_accounts') or {}).get('rows') or []) if isinstance(drill, dict) else []
            admin_summary = {
                'human_users': len(human_rows) or to_int(estate.get('human_user_count'), 0),
                'app_accounts': len(app_rows) or to_int(estate.get('app_account_count'), 0),
                'org_users': to_int(estate.get('total_users') or estate.get('organisation_users'), 0),
            }
        except Exception as exc:
            admin_summary = {'error': str(exc)}

    if billing_payload_path and billing_payload_path.exists():
        try:
            billing_payload = json.loads(billing_payload_path.read_text(encoding='utf-8'))
            billing_summary = {
                'total_jira_seats': to_int(billing_payload.get('total_jira_seats'), 0),
                'jira_site_count': to_int(billing_payload.get('jira_site_count'), 0),
                'source': billing_payload.get('source', ''),
            }
        except Exception as exc:
            billing_summary = {'error': str(exc)}

    product_summary = product_payload.get('summary', {}) if isinstance(product_payload, dict) else {}
    product_user_count = to_int(product_summary.get('total_jira_product_user_count'), 0)
    human_users = to_int(admin_summary.get('human_users'), 0)
    billing_seats = to_int(billing_summary.get('total_jira_seats'), 0)

    return {
        'source': 'Derived from estate_product_access.json plus admin/billing summaries where available',
        'generated_at_utc': iso_now(),
        'schema': 'jom-estate-access-truth-v1',
        'summary': {
            'api_product_user_count': product_user_count,
            'admin_human_users': human_users,
            'billing_jira_seats': billing_seats,
            'api_product_to_human_ratio': round(product_user_count / human_users, 2) if human_users else 0,
            'billing_to_human_ratio': round(billing_seats / human_users, 2) if human_users else 0,
            'accessible_jira_resource_count': to_int(product_summary.get('accessible_jira_resource_count'), 0),
            'sites_with_jira_roles': to_int(product_summary.get('sites_with_jira_roles'), 0),
        },
        'admin_summary': admin_summary,
        'billing_summary': billing_summary,
        'product_summary': product_summary,
        'site_product_access': product_payload.get('sites', []),
        'role_product_access': product_payload.get('roles', []),
        'interpretation': [
            'API product role user counts are estate/product access signals.',
            'Billing seats are commercial consumption signals.',
            'Admin human users are identity truth.',
            'These values should be compared side-by-side rather than forced to match.',
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Collect estate-wide Jira product access using application roles.')
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

    admin_path = project_root / 'latest_run_admin_enriched_pretty.json'
    if not admin_path.exists():
        admin_path = project_root / 'latest_run_admin_enriched.json'
    billing_path = project_root / 'static' / 'data' / 'billing_seats.json'

    truth_payload = build_access_truth(product_payload, admin_path, billing_path)
    truth_output.parent.mkdir(parents=True, exist_ok=True)
    truth_output.write_text(json.dumps(truth_payload, indent=2, ensure_ascii=False), encoding='utf-8')

    print('Estate product access collected.')
    print(json.dumps(product_payload.get('summary', {}), indent=2))
    print('Estate access truth generated.')
    print(json.dumps(truth_payload.get('summary', {}), indent=2))
    if product_payload.get('errors'):
        print('Collection warnings/errors:')
        print(json.dumps(product_payload.get('errors'), indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
