from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

EXPECTED_BILLING_SITE_COUNTS = {
    'gli-it-project': 58,
    'gli-delivery-tm': 28,
    'gli-global-technology': 53,
}

TRUSTED_JIRA_SITES = set(EXPECTED_BILLING_SITE_COUNTS.keys())


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(float(value))
    except Exception:
        return default


def as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def product_site_counts(project_root: Path) -> Dict[str, int]:
    product = read_json(project_root / 'static' / 'data' / 'estate_product_access.json')
    counts: Dict[str, int] = {}
    for row in as_list(product.get('sites')):
        if not isinstance(row, dict):
            continue
        key = str(row.get('site_key') or '').strip()
        if not key:
            continue
        # Known current file values have jira_product_user_count; older files may have user_count.
        count = safe_int(row.get('jira_product_user_count'), None)
        if count is None:
            count = safe_int(row.get('user_count') or row.get('users') or row.get('count'))
        counts[key] = count
    return counts


def named_site_counts(named: Dict[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in as_list(named.get('site_counts')):
        if not isinstance(row, dict):
            continue
        key = str(row.get('site_key') or '').strip()
        if key:
            counts[key] = safe_int(row.get('named_access_count'))
    return counts


def user_distribution(named: Dict[str, Any]) -> Dict[str, Any]:
    users = as_list(named.get('users'))
    distribution: Dict[str, int] = {}
    users_with_jira = 0
    users_without_jira = 0
    high_site_users: List[Dict[str, Any]] = []
    for user in users:
        if not isinstance(user, dict):
            continue
        site_count = safe_int(user.get('jira_site_count'))
        distribution[str(site_count)] = distribution.get(str(site_count), 0) + 1
        if site_count > 0:
            users_with_jira += 1
        else:
            users_without_jira += 1
        if site_count >= 3:
            high_site_users.append({
                'account_id': user.get('account_id', ''),
                'email': user.get('email', ''),
                'display_name': user.get('display_name', ''),
                'jira_site_count': site_count,
                'sites': [a.get('site_key') for a in as_list(user.get('jira_access')) if isinstance(a, dict)],
            })
    return {
        'distribution': distribution,
        'users_with_jira_named_access': users_with_jira,
        'users_without_jira_named_access': users_without_jira,
        'high_site_users': high_site_users,
    }


def build(project_root: Path) -> Dict[str, Any]:
    named_path = project_root / 'static' / 'data' / 'live_named_access_contract'
    admin_truth_path = project_root / 'static' / 'data' / 'admin_truth_v2.json'
    product_path = project_root / 'static' / 'data' / 'estate_product_access.json'
    billing_path = project_root / 'static' / 'data' / 'billing_seats.json'

    named = read_json(named_path)
    admin_truth = read_json(admin_truth_path)
    billing = read_json(billing_path)

    named_counts = named_site_counts(named)
    product_counts = product_site_counts(project_root)
    billing_counts = dict(EXPECTED_BILLING_SITE_COUNTS)

    # Use billing screenshot/source counts as the current known site-level billing truth where available.
    all_sites = sorted(set(named_counts) | set(product_counts) | set(billing_counts))
    site_rows = []
    for site in all_sites:
        named_count = named_counts.get(site, 0)
        product_count = product_counts.get(site)
        billing_count = billing_counts.get(site)
        expected_count = billing_count if billing_count is not None else product_count
        gap_to_expected = None if expected_count is None else named_count - safe_int(expected_count)
        classification = 'trusted_monitored_site' if site in TRUSTED_JIRA_SITES else 'unmapped_or_out_of_scope_resource'
        if expected_count is None:
            status = 'unmapped'
        elif named_count == expected_count:
            status = 'aligned'
        elif named_count < expected_count:
            status = 'under_count'
        else:
            status = 'over_count'
        site_rows.append({
            'site_key': site,
            'classification': classification,
            'billing_count': billing_count,
            'product_api_count': product_count,
            'named_role_assignment_count': named_count,
            'named_minus_expected': gap_to_expected,
            'status': status,
        })

    named_summary = named.get('summary') if isinstance(named.get('summary'), dict) else {}
    truth_summary = admin_truth.get('summary') if isinstance(admin_truth.get('summary'), dict) else {}
    direct_named_total = safe_int(named_summary.get('jira_mappings'))
    expected_total = safe_int(truth_summary.get('api_product_users') or named_summary.get('expected_mappings') or sum(billing_counts.values()))
    billing_total = safe_int(truth_summary.get('billing_jira_seats') or billing.get('total_jira_seats') or sum(billing_counts.values()))
    gap = direct_named_total - expected_total

    dist = user_distribution(named)
    extra_sites = [row for row in site_rows if row['classification'] != 'trusted_monitored_site']
    monitored_shortfall = sum(abs(safe_int(row.get('named_minus_expected'))) for row in site_rows if row['classification'] == 'trusted_monitored_site' and safe_int(row.get('named_minus_expected')) < 0)

    conclusion = {
        'named_access_ui_should_remain_disabled': True,
        'reason': 'Direct Admin role assignments currently reconcile to 76 named Jira Software mappings, not the 139 billing/API product count. The missing 63 likely requires group-derived product access expansion or another Directory-level source.',
        'direct_role_assignment_source_is_valid_but_incomplete': True,
        'group_assignment_expansion_needed': True,
        'unknown_or_out_of_scope_resource_present': bool(extra_sites),
    }

    return {
        'schema': 'jom-named-access-reconciliation-v1',
        'generated_at_utc': now_utc(),
        'sources': {
            'admin_named_access': str(named_path),
            'admin_truth_v2': str(admin_truth_path),
            'estate_product_access': str(product_path),
            'billing_seats': str(billing_path),
            'billing_screenshot_counts_used': EXPECTED_BILLING_SITE_COUNTS,
        },
        'summary': {
            'admin_truth_status': truth_summary.get('status'),
            'billing_jira_seats': billing_total,
            'api_product_users': expected_total,
            'direct_named_role_assignments': direct_named_total,
            'direct_named_minus_api_product': gap,
            'direct_named_coverage_percent': round((direct_named_total / expected_total) * 100, 2) if expected_total else 0,
            'monitored_site_shortfall_abs': monitored_shortfall,
            'site_rows_count': len(site_rows),
            'extra_resource_count': len(extra_sites),
            'safe_to_enable_named_access_ui': False,
        },
        'site_reconciliation': site_rows,
        'user_distribution': dist,
        'resource_owner_counts': named_summary.get('resource_owner_counts', {}),
        'role_counts': named_summary.get('role_counts', {}),
        'filter_counts': named_summary.get('filter_counts', {}),
        'conclusion': conclusion,
        'next_actions': [
            'Do not enable named footprint UI.',
            'Identify unmapped cloud ID 5e39f28e-6ff4-44ff-82b7-d0746cee8db5 in Atlassian site/resource list.',
            'Build group role-assignment expansion collector to include group-derived Jira Software access.',
            'Validate at least 5 known users against Atlassian Directory Apps tab before named UI enablement.',
        ],
    }


def md(payload: Dict[str, Any]) -> str:
    s = payload.get('summary', {})
    lines = []
    lines.append('# Named Access Reconciliation')
    lines.append('')
    lines.append(f"Generated UTC: `{payload.get('generated_at_utc')}`")
    lines.append('')
    lines.append('## Summary')
    lines.append('')
    lines.append(f"- Billing Jira seats: **{s.get('billing_jira_seats')}**")
    lines.append(f"- API product users: **{s.get('api_product_users')}**")
    lines.append(f"- Direct named role assignments: **{s.get('direct_named_role_assignments')}**")
    lines.append(f"- Direct named minus API product: **{s.get('direct_named_minus_api_product')}**")
    lines.append(f"- Direct named coverage: **{s.get('direct_named_coverage_percent')}%**")
    lines.append(f"- Safe to enable named UI: **{s.get('safe_to_enable_named_access_ui')}**")
    lines.append('')
    lines.append('## Site Reconciliation')
    lines.append('')
    lines.append('| Site | Classification | Billing | Product API | Named role assignments | Gap | Status |')
    lines.append('|---|---:|---:|---:|---:|---:|---|')
    for row in payload.get('site_reconciliation', []):
        lines.append(f"| {row.get('site_key')} | {row.get('classification')} | {row.get('billing_count')} | {row.get('product_api_count')} | {row.get('named_role_assignment_count')} | {row.get('named_minus_expected')} | {row.get('status')} |")
    lines.append('')
    lines.append('## User Distribution')
    lines.append('')
    dist = payload.get('user_distribution', {})
    lines.append(f"- Users with named Jira access: **{dist.get('users_with_jira_named_access')}**")
    lines.append(f"- Users without named Jira access: **{dist.get('users_without_jira_named_access')}**")
    lines.append(f"- Distribution by Jira site count: `{dist.get('distribution')}`")
    lines.append('')
    lines.append('## Conclusion')
    lines.append('')
    lines.append(payload.get('conclusion', {}).get('reason', ''))
    lines.append('')
    lines.append('## Next Actions')
    lines.append('')
    for item in payload.get('next_actions', []):
        lines.append(f'- {item}')
    lines.append('')
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', default='.')
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    payload = build(root)
    json_out = root / 'reports' / 'named_access_reconciliation.json'
    md_out = root / 'reports' / 'named_access_reconciliation.md'
    write_json(json_out, payload)
    md_out.write_text(md(payload), encoding='utf-8')
    print('Named Access Reconciliation complete.')
    print(json.dumps(payload.get('summary', {}), indent=2))
    print(f'JSON: {json_out}')
    print(f'Report: {md_out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
