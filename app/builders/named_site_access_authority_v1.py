from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None


def site_key(row: Dict[str, Any]) -> str:
    return str(row.get('site_key') or row.get('site_name') or '').strip()


def build(project_root: Path) -> Dict[str, Any]:
    data = project_root / 'runtime' / 'data'
    footprint = read_json(data / 'user_footprint.json')
    product = read_json(data / 'estate_product_access.json')
    registry = read_json(data / 'site_registry.json')

    footprint_summary = footprint.get('summary') if isinstance(footprint.get('summary'), dict) else {}
    footprint_rows = as_list(footprint.get('users'))
    product_rows = as_list(product.get('sites'))
    registry_rows = as_list(registry.get('sites'))

    product_index: Dict[str, Dict[str, Any]] = {}
    for row in product_rows:
        if isinstance(row, dict) and site_key(row):
            product_index[site_key(row)] = row

    registry_keys = set()
    for row in registry_rows:
        if not isinstance(row, dict):
            continue
        for key in ('site_key', 'key', 'site_name', 'name'):
            if row.get(key):
                registry_keys.add(str(row.get(key)))

    user_sets: Dict[str, set[str]] = {}
    assignment_counts: Dict[str, int] = {}
    invalid_rows = 0
    for row in footprint_rows:
        if not isinstance(row, dict):
            invalid_rows += 1
            continue
        account_id = row.get('account_id') or row.get('accountId')
        sites = sorted({str(value) for value in as_list(row.get('sites')) if value})
        products = sorted({str(value) for value in as_list(row.get('products')) if value})
        if not account_id or not sites or not products:
            invalid_rows += 1
            continue
        for site in sites:
            user_sets.setdefault(site, set()).add(str(account_id))
            assignment_counts[site] = assignment_counts.get(site, 0) + 1

    rows: List[Dict[str, Any]] = []
    for site in sorted(user_sets):
        product_row = product_index.get(site, {})
        named_users = len(user_sets[site])
        product_users = safe_int(product_row.get('jira_product_user_count'))
        registry_match = site in registry_keys
        product_match = bool(product_row)
        count_safe = product_users is not None and named_users <= product_users
        rows.append({
            'site_key': site,
            'named_unique_users': named_users,
            'named_access_assignments': assignment_counts.get(site, 0),
            'product_access_assignments': product_users,
            'registry_match': registry_match,
            'product_authority_match': product_match,
            'named_count_within_product_count': count_safe,
            'assignment_gap': product_users - named_users if product_users is not None else None,
            'status': 'live' if registry_match and product_match and count_safe else 'review',
        })

    declared_users = safe_int(footprint_summary.get('users_analyzed'))
    declared_assignments = safe_int(footprint_summary.get('total_product_access_assignments'))
    calculated_users = len({str(row.get('account_id') or row.get('accountId')) for row in footprint_rows if isinstance(row, dict) and (row.get('account_id') or row.get('accountId'))})
    calculated_assignments = sum(assignment_counts.values())

    gates = {
        'source_generated': footprint.get('source_status') == 'generated',
        'source_safe': footprint.get('safe_to_show_named_access_ui') is True,
        'all_rows_valid': bool(footprint_rows) and invalid_rows == 0,
        'unique_users_reconciled': declared_users == calculated_users,
        'assignments_reconciled': declared_assignments == calculated_assignments,
        'all_sites_registry_mapped': bool(rows) and all(row['registry_match'] for row in rows),
        'all_sites_product_mapped': bool(rows) and all(row['product_authority_match'] for row in rows),
        'all_named_counts_within_product_counts': bool(rows) and all(row['named_count_within_product_count'] for row in rows),
    }
    live = all(gates.values())

    return {
        'schema': 'jom-named-site-access-authority-v1',
        'generated_at_utc': utc_now(),
        'status': 'live' if live else 'review',
        'authority': 'Privacy-minimised named access footprint reconciled with Site Registry and Jira product-access authority',
        'privacy': {
            'aggregate_only': True,
            'names_exposed': False,
            'emails_exposed': False,
            'account_ids_exposed': False,
            'identity_rows_exposed': False,
        },
        'capabilities': {
            'aggregate_site_user_counts': live,
            'identity_drilldown': False,
            'identity_drilldown_reason': 'Requires separate privacy and operational approval.',
        },
        'summary': {
            'unique_users_with_access': declared_users if live else None,
            'named_access_assignments': declared_assignments if live else None,
            'site_count': len(rows),
            'invalid_source_rows': invalid_rows,
        },
        'gates': gates,
        'sites': rows,
        'source_files': {
            'user_footprint': 'runtime/data/user_footprint.json',
            'product_access': 'runtime/data/estate_product_access.json',
            'site_registry': 'runtime/data/site_registry.json',
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Build privacy-safe aggregate Named Site Access authority.')
    parser.add_argument('--project-root', default='.')
    parser.add_argument('--output', default='runtime/data/named_site_access_authority_v1.json')
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    output = root / args.output
    payload = build(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(json.dumps({
        'output': str(output),
        'status': payload.get('status'),
        'unique_users_with_access': (payload.get('summary') or {}).get('unique_users_with_access'),
        'named_access_assignments': (payload.get('summary') or {}).get('named_access_assignments'),
        'site_count': (payload.get('summary') or {}).get('site_count'),
        'aggregate_site_user_counts': (payload.get('capabilities') or {}).get('aggregate_site_user_counts'),
        'identity_drilldown': (payload.get('capabilities') or {}).get('identity_drilldown'),
    }, indent=2))
    return 0 if payload.get('status') == 'live' else 2


if __name__ == '__main__':
    raise SystemExit(main())
