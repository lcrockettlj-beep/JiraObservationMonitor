# JOM_BACKEND_STATIC_TRUTH_REMAINING_REFERENCE_REMEDIATION_V2
# Remaining legacy/static truth references in this file have been neutralised.
# This file must not treat retired runtime records as backend or website truth.
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(float(value))
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == '':
            return default
        return float(value)
    except Exception:
        return default


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')


def admin_candidates(project_root: Path) -> List[Path]:
    return [project_root / 'runtime' / 'data' / 'admin_directory_users.json']


def first_existing(paths: List[Path]) -> Optional[Path]:
    for path in paths:
        if path.exists():
            return path
    return None


def drill_rows(payload: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    section = (payload.get('drilldowns') or {}).get(key) or {}
    rows = section.get('rows') if isinstance(section, dict) else []
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _summary_count(summary: Dict[str, Any], section: str, *keys: str) -> int:
    values = summary.get(section) if isinstance(summary.get(section), dict) else {}
    return sum(safe_int(values.get(key)) for key in keys)


def admin_summary_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    summary = payload.get('summary') if isinstance(payload.get('summary'), dict) else {}
    users = payload.get('users') if isinstance(payload.get('users'), list) else []
    source = payload.get('source') if isinstance(payload.get('source'), dict) else {}
    complete = bool(source.get('pagination_complete')) and bool(payload.get('safe_to_use_for_account_authority'))

    account_types = summary.get('account_types') if isinstance(summary.get('account_types'), dict) else {}
    account_statuses = summary.get('account_statuses') if isinstance(summary.get('account_statuses'), dict) else {}
    claim_statuses = summary.get('claim_statuses') if isinstance(summary.get('claim_statuses'), dict) else {}

    app_accounts = sum(safe_int(value) for key, value in account_types.items() if key in {'app', 'service_account', 'service', 'bot'})
    human_users = sum(safe_int(value) for key, value in account_types.items() if key in {'atlassian', 'customer', 'human', 'user'})
    suspended_users = sum(safe_int(value) for key, value in account_statuses.items() if key in {'suspended', 'disabled', 'deactivated', 'inactive'})
    managed_users = sum(safe_int(value) for key, value in claim_statuses.items() if key in {'managed', 'claimed'})

    return {
        'org_users': safe_int(summary.get('unique_accounts')) if complete else 0,
        'active_users': None,
        'managed_users': managed_users if complete else 0,
        'human_users': human_users if complete else 0,
        'app_accounts': app_accounts if complete else 0,
        'suspended_users': suspended_users if complete else 0,
        'mfa_enabled': safe_int(summary.get('mfa_enabled')) if complete else 0,
        'mfa_disabled': safe_int(summary.get('mfa_disabled')) if complete else 0,
        'mfa_unknown': safe_int(summary.get('mfa_unknown')) if complete else 0,
        'platform_role_assignments': safe_int(summary.get('platform_role_assignments')) if complete else 0,
        'source_fields': {
            'user_rows': len(users),
            'pagination_complete': bool(source.get('pagination_complete')),
            'directory_count': safe_int(source.get('directory_count')),
            'page_count': safe_int(source.get('page_count')),
            'privacy_minimised': bool((payload.get('privacy') or {}).get('raw_responses_stored') is False),
        },
    }

def billing_summary(project_root: Path) -> Dict[str, Any]:
    billing_path = project_root / 'runtime' / 'data' / 'estate_access_truth.json'
    payload = read_json(billing_path)
    return {
        'source_file': str(billing_path),
        'source': payload.get('source', 'estate_access_truth.json') if payload else '',
        'jira_seats': safe_int(payload.get('total_jira_seats')),
        'jira_site_count': safe_int(payload.get('jira_site_count')),
        'payload_available': bool(payload),
        'raw': payload,
    }


def product_access_summary(project_root: Path) -> Dict[str, Any]:
    product_path = project_root / 'runtime' / 'data' / 'estate_product_access.json'
    truth_path = project_root / 'runtime' / 'data' / 'estate_access_truth.json'
    product = read_json(product_path)
    truth = read_json(truth_path)
    product_summary = product.get('summary') if isinstance(product.get('summary'), dict) else {}
    truth_summary = truth.get('summary') if isinstance(truth.get('summary'), dict) else {}
    sites = product.get('sites') if isinstance(product.get('sites'), list) else []
    roles = product.get('roles') if isinstance(product.get('roles'), list) else []
    errors = product.get('errors') if isinstance(product.get('errors'), dict) else {}

    confirmed_sites = [row for row in sites if isinstance(row, dict) and str(row.get('status')).lower() == 'ok']
    blocked_sites = [row for row in sites if isinstance(row, dict) and str(row.get('status')).lower() != 'ok']

    return {
        'source_file': str(product_path),
        'truth_file': str(truth_path),
        'api_product_users': safe_int(product_summary.get('total_jira_product_user_count') or truth_summary.get('api_product_user_count')),
        'api_product_seat_limit': safe_int(product_summary.get('total_jira_seat_limit')),
        'api_product_remaining_seats': safe_int(product_summary.get('total_jira_remaining_seats')),
        'accessible_jira_resource_count': safe_int(product_summary.get('accessible_jira_resource_count') or truth_summary.get('accessible_jira_resource_count')),
        'confirmed_product_site_count': safe_int(product_summary.get('sites_with_jira_roles') or truth_summary.get('sites_with_jira_roles')),
        'blocked_resource_count': safe_int(product_summary.get('error_site_count')),
        'confirmed_sites': confirmed_sites,
        'blocked_sites': blocked_sites,
        'roles': [row for row in roles if isinstance(row, dict)],
        'errors': errors,
        'payload_available': bool(product),
    }


def compare_truth(admin: Dict[str, Any], billing: Dict[str, Any], product: Dict[str, Any]) -> Dict[str, Any]:
    humans = safe_int(admin.get('human_users'))
    estate_product_access = safe_int(billing.get('jira_seats'))
    product_users = safe_int(product.get('api_product_users'))
    billing_to_human = round(estate_product_access / humans, 2) if humans else 0
    product_to_human = round(product_users / humans, 2) if humans else 0
    variance = product_users - estate_product_access
    variance_abs = abs(variance)
    aligned = product_users > 0 and estate_product_access > 0 and variance_abs == 0

    if aligned:
        status = 'aligned'
        severity = 'ok'
        interpretation = 'API product access users match Atlassian billing seats exactly. Billing and API product-count truth are aligned.'
    elif product_users <= 0 and estate_product_access > 0:
        status = 'api_missing'
        severity = 'warning'
        interpretation = 'Billing seats are available but API product access users are missing or blocked. Use billing as commercial truth until product API is restored.'
    elif estate_product_access <= 0 and product_users > 0:
        status = 'billing_missing'
        severity = 'warning'
        interpretation = 'API product access users are available but billing seats are missing. Use API as operational count and review billing source.'
    else:
        status = 'variance'
        severity = 'warning' if variance_abs <= 5 else 'critical'
        interpretation = 'API product access users and billing seats do not match. Review site authorisation, billing source, and product access collection before reporting final licence truth.'

    return {
        'status': status,
        'severity': severity,
        'interpretation': interpretation,
        'admin_human_users': humans,
        'billing_jira_seats': estate_product_access,
        'api_product_users': product_users,
        'api_minus_billing': variance,
        'api_billing_variance_abs': variance_abs,
        'billing_to_human_ratio': billing_to_human,
        'api_product_to_human_ratio': product_to_human,
        'confirmed_product_site_count': safe_int(product.get('confirmed_product_site_count')),
        'accessible_jira_resource_count': safe_int(product.get('accessible_jira_resource_count')),
        'blocked_resource_count': safe_int(product.get('blocked_resource_count')),
    }


def build_admin_truth_v2(project_root: Path) -> Dict[str, Any]:
    admin_path = first_existing(admin_candidates(project_root))
    admin_payload = read_json(admin_path) if admin_path else {}
    admin = admin_summary_from_payload(admin_payload)
    admin['source_file'] = str(admin_path) if admin_path else ''
    admin['payload_available'] = bool(admin_payload)

    billing = billing_summary(project_root)
    product = product_access_summary(project_root)
    comparison = compare_truth(admin, billing, product)

    site_rows: List[Dict[str, Any]] = []
    for site in product.get('confirmed_sites', []):
        site_rows.append({
            'site_key': site.get('site_key', ''),
            'site_name': site.get('site_name', ''),
            'site_url': site.get('site_url', ''),
            'jira_product_user_count': safe_int(site.get('jira_product_user_count')),
            'jira_role_count': safe_int(site.get('jira_role_count')),
            'status': site.get('status', ''),
        })
    site_rows.sort(key=lambda r: (-safe_int(r.get('jira_product_user_count')), str(r.get('site_key', '')).lower()))

    blocked_rows: List[Dict[str, Any]] = []
    for site in product.get('blocked_sites', []):
        key = site.get('site_key', '')
        blocked_rows.append({
            'site_key': key,
            'site_name': site.get('site_name', ''),
            'site_url': site.get('site_url', ''),
            'status': site.get('status', ''),
            'reason': '; '.join(str(v) for v in product.get('errors', {}).get(key, [])) if key else '',
        })
    blocked_rows.sort(key=lambda r: str(r.get('site_key', '')).lower())

    payload = {
        'schema': 'jom-admin-truth-layer-v2',
        'generated_at_utc': utc_now(),
        'source_policy': {
            'identity_truth': 'Atlassian Admin API enriched runtime payload',
            'commercial_billing_truth': 'runtime/data/estate_access_truth.json',
            'product_count_truth': 'runtime/data/estate_product_access.json from Jira application roles',
            'named_access_truth': 'runtime/data/admin_directory_users.json; privacy-minimised, fully paginated Atlassian Directory account authority',
            'excluded_sources': [
                'Jira /rest/api/3/users/search for named access',
                'site visibility as a proxy for product access',
                'legacy CSV named footprint unless validated against Atlassian Directory Apps tab',
            ],
        },
        'summary': comparison,
        'admin_identity': admin,
        'billing_truth': {
            'source_file': billing.get('source_file'),
            'source': billing.get('source'),
            'jira_seats': billing.get('jira_seats'),
            'jira_site_count': billing.get('jira_site_count'),
            'payload_available': billing.get('payload_available'),
        },
        'product_access_truth': {
            'source_file': product.get('source_file'),
            'truth_file': product.get('truth_file'),
            'api_product_users': product.get('api_product_users'),
            'api_product_seat_limit': product.get('api_product_seat_limit'),
            'api_product_remaining_seats': product.get('api_product_remaining_seats'),
            'accessible_jira_resource_count': product.get('accessible_jira_resource_count'),
            'confirmed_product_site_count': product.get('confirmed_product_site_count'),
            'blocked_resource_count': product.get('blocked_resource_count'),
            'payload_available': product.get('payload_available'),
        },
        'confirmed_product_sites': site_rows,
        'blocked_resources': blocked_rows,
        'controls': {
            'named_user_footprint_visible': False,
            'named_user_footprint_guard_reason': 'Directory account authority is verified, but named per-site entitlement remains hidden until resource-level product access mapping is proven.',
            'safe_to_show_estate_totals': comparison.get('status') in {'aligned', 'billing_missing', 'api_missing', 'variance'},
            'safe_to_show_named_site_access': False,
        },
        'next_actions': [
            'Keep active-user reporting unavailable until last-active authority and an activity policy are proven.',
            'Keep named per-site entitlement hidden until resource-level product access mapping is proven.',
            'Do not use /users/search output as named licence truth.',
        ],
    }
    return payload


def markdown_report(payload: Dict[str, Any]) -> str:
    summary = payload.get('summary', {})
    sites = payload.get('confirmed_product_sites', [])
    blocked = payload.get('blocked_resources', [])
    lines: List[str] = []
    lines.append('# JOM Admin Truth Layer v2')
    lines.append('')
    lines.append(f"Generated UTC: `{payload.get('generated_at_utc')}`")
    lines.append('')
    lines.append('## Executive Truth Summary')
    lines.append('')
    lines.append(f"- Status: **{summary.get('status')}**")
    lines.append(f"- Severity: **{summary.get('severity')}**")
    lines.append(f"- Admin human users: **{summary.get('admin_human_users')}**")
    lines.append(f"- Billing Jira seats: **{summary.get('billing_jira_seats')}**")
    lines.append(f"- API product users: **{summary.get('api_product_users')}**")
    lines.append(f"- API minus billing variance: **{summary.get('api_minus_billing')}**")
    lines.append(f"- Billing-to-human ratio: **{summary.get('billing_to_human_ratio')}**")
    lines.append(f"- API-product-to-human ratio: **{summary.get('api_product_to_human_ratio')}**")
    lines.append('')
    lines.append(f"> {summary.get('interpretation')}")
    lines.append('')
    lines.append('## Confirmed Product Sites')
    lines.append('')
    if not sites:
        lines.append('- No confirmed product sites were available.')
    else:
        for row in sites:
            lines.append(f"- **{row.get('site_name') or row.get('site_key')}** — {row.get('jira_product_user_count')} product users, {row.get('jira_role_count')} role row(s), status `{row.get('status')}`")
    lines.append('')
    lines.append('## Blocked / Visible But Not Authorised Resources')
    lines.append('')
    if not blocked:
        lines.append('- No blocked resources were reported.')
    else:
        for row in blocked:
            reason = row.get('reason') or 'No reason recorded.'
            lines.append(f"- **{row.get('site_name') or row.get('site_key')}** — `{row.get('status')}` — {reason}")
    lines.append('')
    lines.append('## Source Policy')
    lines.append('')
    policy = payload.get('source_policy', {})
    lines.append(f"- Identity truth: {policy.get('identity_truth')}")
    lines.append(f"- Commercial billing truth: {policy.get('commercial_billing_truth')}")
    lines.append(f"- Product-count truth: {policy.get('product_count_truth')}")
    lines.append(f"- Named access truth: {policy.get('named_access_truth')}")
    lines.append('')
    lines.append('## Guardrails')
    lines.append('')
    controls = payload.get('controls', {})
    lines.append(f"- Named-user footprint visible: **{controls.get('named_user_footprint_visible')}**")
    lines.append(f"- Safe to show named site access: **{controls.get('safe_to_show_named_site_access')}**")
    lines.append(f"- Reason: {controls.get('named_user_footprint_guard_reason')}")
    lines.append('')
    lines.append('## Next Actions')
    lines.append('')
    for item in payload.get('next_actions', []):
        lines.append(f"- {item}")
    lines.append('')
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description='Build JOM Admin Truth Layer v2 from verified admin, billing, and product access sources.')
    parser.add_argument('--project-root', default='.')
    parser.add_argument('--output-json', default='runtime/data/admin_truth_v2.json')
    parser.add_argument('--output-report', default='reports/admin_truth_v2.md')
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    payload = build_admin_truth_v2(project_root)

    out_json = Path(args.output_json)
    out_report = Path(args.output_report)
    if not out_json.is_absolute():
        out_json = project_root / out_json
    if not out_report.is_absolute():
        out_report = project_root / out_report

    write_json(out_json, payload)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text(markdown_report(payload), encoding='utf-8')

    print('Admin Truth Layer v2 generated.')
    print(json.dumps(payload.get('summary', {}), indent=2))
    print(f'JSON: {out_json}')
    print(f'Report: {out_report}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
