from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

API_HOST = 'https://api.atlassian.com/admin'
EXPECTED_DEFAULT = 139


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def load_env(project_root: Path) -> Dict[str, str]:
    env = dict(os.environ)
    env_path = project_root / '.env'
    if env_path.exists():
        for raw in env_path.read_text(encoding='utf-8').splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


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


def get_first(row: Dict[str, Any], names: List[str]) -> str:
    folded = {str(k).strip().lower().replace(' ', '_').replace('-', '_'): v for k, v in row.items()}
    for name in names:
        direct = row.get(name)
        if direct not in (None, ''):
            return str(direct).strip()
        folded_value = folded.get(name.strip().lower().replace(' ', '_').replace('-', '_'))
        if folded_value not in (None, ''):
            return str(folded_value).strip()
    return ''


def drill_rows(payload: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    rows = ((payload.get('drilldowns') or {}).get(key) or {}).get('rows') or []
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def load_human_scope(project_root: Path) -> Tuple[List[Dict[str, str]], str]:
    for filename in ['latest_run_admin_enriched_pretty.json', 'latest_run_admin_enriched.json', 'latest_run_pretty.json', 'latest_run.json']:
        path = project_root / filename
        payload = read_json(path)
        if not payload:
            continue
        rows = drill_rows(payload, 'admin::human_accounts')
        if not rows:
            admin = payload.get('admin_enrichment') if isinstance(payload.get('admin_enrichment'), dict) else {}
            users = admin.get('users') if isinstance(admin.get('users'), list) else []
            rows = [r for r in users if isinstance(r, dict)]
        scoped, seen = [], set()
        for row in rows:
            account_id = get_first(row, ['account_id', 'accountId', 'Atlassian ID', 'User id', 'id'])
            email = get_first(row, ['email', 'Email', 'emailAddress', 'email_address'])
            name = get_first(row, ['displayName', 'display_name', 'name', 'User name', 'fullName'])
            key = account_id or email
            if key and key not in seen:
                seen.add(key)
                scoped.append({'account_id': account_id, 'email': email, 'display_name': name})
        if scoped:
            return scoped, str(path)
    return [], ''


def cloud_id_from_ari(resource_id: str) -> str:
    # Atlassian ARI shape seen in the live probe:
    # ari:cloud:jira-software::site/aaa90a93-f0af-47ba-98d6-47829cc032b7
    if not resource_id:
        return ''
    marker = 'site/'
    if marker not in resource_id:
        return ''
    return resource_id.rsplit(marker, 1)[-1].strip()


def has_site_ari(resource_id: str) -> bool:
    return bool(resource_id) and 'site/' in resource_id


def site_key_from_url(url: str) -> str:
    host = (url or '').lower().replace('https://', '').replace('http://', '').split('/')[0]
    return host.replace('.atlassian.net', '') if host else ''


def load_site_map(project_root: Path) -> Dict[str, Dict[str, str]]:
    mapping: Dict[str, Dict[str, str]] = {}
    for filename in ['latest_run_admin_enriched_pretty.json', 'latest_run_admin_enriched.json', 'latest_run_pretty.json', 'latest_run.json']:
        payload = read_json(project_root / filename)
        for site in payload.get('sites', []) if isinstance(payload.get('sites'), list) else []:
            if not isinstance(site, dict):
                continue
            cloud_id = str(site.get('cloud_id') or '').strip()
            url = str(site.get('url') or site.get('site_url') or '').strip().rstrip('/')
            key = str(site.get('site') or site.get('site_key') or site_key_from_url(url) or cloud_id).strip()
            name = str(site.get('site_name') or site.get('name') or key).strip()
            if cloud_id:
                mapping[cloud_id] = {'site_key': key, 'site_name': name, 'site_url': url, 'cloud_id': cloud_id}
    return mapping


def request_json(url: str, token: str) -> Dict[str, Any]:
    req = urllib.request.Request(url=url, headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'}, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read().decode('utf-8')
            return {'ok': True, 'status': response.status, 'json': json.loads(raw) if raw else {}}
    except urllib.error.HTTPError as exc:
        return {'ok': False, 'status': exc.code, 'body': exc.read().decode('utf-8', errors='ignore')[:4000], 'url': url}
    except Exception as exc:
        return {'ok': False, 'status': 0, 'body': str(exc), 'url': url}


def role_assignments(org_id: str, directory_id: str, account_id: str, token: str, delay: float) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    rows, errors, cursor = [], [], None
    while True:
        qs = {'limit': '50'}
        if cursor:
            qs['cursor'] = cursor
        url = f"{API_HOST}/v2/orgs/{org_id}/directories/{directory_id}/users/{account_id}/role-assignments?{urllib.parse.urlencode(qs)}"
        result = request_json(url, token)
        if not result.get('ok'):
            errors.append({'account_id': account_id, **result})
            break
        payload = result.get('json') if isinstance(result.get('json'), dict) else {}
        data = payload.get('data') if isinstance(payload.get('data'), list) else []
        rows.extend([r for r in data if isinstance(r, dict)])
        next_cursor = (payload.get('links') or {}).get('next')
        if not next_cursor or next_cursor == cursor:
            break
        cursor = str(next_cursor)
        if delay > 0:
            time.sleep(delay)
    return rows, errors


def norm_roles(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v).strip().lower() for v in value if str(v).strip()]
    if value:
        return [str(value).strip().lower()]
    return []


def collect(project_root: Path, expected: int, delay: float) -> Dict[str, Any]:
    env = load_env(project_root)
    org_id = env.get('ATLASSIAN_ADMIN_ORG_ID', '').strip()
    token = env.get('ATLASSIAN_ADMIN_API_KEY', '').strip()
    if not org_id or not token:
        raise RuntimeError('Missing ATLASSIAN_ADMIN_ORG_ID or ATLASSIAN_ADMIN_API_KEY in .env')
    probe = read_json(project_root / 'reports' / 'admin_named_access_endpoint_probe.json')
    directory_id = env.get('ATLASSIAN_ADMIN_DIRECTORY_ID', '').strip() or str(((probe.get('summary') or {}).get('directory_ids_discovered') or [''])[0])
    if not directory_id:
        raise RuntimeError('Missing directory id. Run endpoint probe or set ATLASSIAN_ADMIN_DIRECTORY_ID in .env')

    users, scope_source = load_human_scope(project_root)
    site_map = load_site_map(project_root)
    print(f'Human scope: {len(users)}')
    print(f'Scope source: {scope_source}')
    print(f'Directory ID: {directory_id}')

    output_users, errors = [], []
    site_counts: Dict[str, int] = {}
    mapping_keys = set()
    resource_owner_counts: Dict[str, int] = {}
    role_counts: Dict[str, int] = {}
    filter_counts = {'not_jira_software': 0, 'missing_site_ari': 0, 'inactive': 0, 'duplicate_user_site': 0, 'accepted': 0}
    raw_assignment_count = 0
    accepted_samples, rejected_jira_samples = [], []

    for index, user in enumerate(users, start=1):
        aid = user.get('account_id') or ''
        assignments, errs = role_assignments(org_id, directory_id, aid, token, delay)
        errors.extend(errs)
        raw_assignment_count += len(assignments)
        jira_access, seen_user_sites = [], set()
        for row in assignments:
            owner = str(row.get('resourceOwner') or '').strip().lower()
            roles = norm_roles(row.get('roles'))
            status = str(row.get('userDirectoryStatus') or '').strip().lower()
            rid = str(row.get('resourceId') or '')
            resource_owner_counts[owner or 'unknown'] = resource_owner_counts.get(owner or 'unknown', 0) + 1
            for role in roles:
                role_counts[role] = role_counts.get(role, 0) + 1

            if owner != 'jira-software':
                filter_counts['not_jira_software'] += 1
                continue
            if not has_site_ari(rid):
                filter_counts['missing_site_ari'] += 1
                if len(rejected_jira_samples) < 10:
                    rejected_jira_samples.append(row)
                continue
            if status and status != 'active':
                filter_counts['inactive'] += 1
                if len(rejected_jira_samples) < 10:
                    rejected_jira_samples.append(row)
                continue

            cloud_id = cloud_id_from_ari(rid)
            unique = (aid, cloud_id or rid)
            if unique in seen_user_sites:
                filter_counts['duplicate_user_site'] += 1
                continue
            seen_user_sites.add(unique)
            mapping_keys.add(unique)
            filter_counts['accepted'] += 1
            site = site_map.get(cloud_id, {})
            site_key = site.get('site_key') or cloud_id
            site_counts[site_key] = site_counts.get(site_key, 0) + 1
            item = {
                'resource_id': rid,
                'cloud_id': cloud_id,
                'site_key': site_key,
                'site_name': site.get('site_name') or site_key,
                'site_url': site.get('site_url') or '',
                'roles': row.get('roles') or [],
                'user_directory_status': row.get('userDirectoryStatus'),
                'resource_owner': row.get('resourceOwner'),
            }
            jira_access.append(item)
            if len(accepted_samples) < 20:
                accepted_samples.append({'user': {'account_id': aid, 'email': user.get('email'), 'display_name': user.get('display_name')}, 'assignment': row, 'normalised': item})

        output_users.append({
            'account_id': aid,
            'email': user.get('email'),
            'display_name': user.get('display_name'),
            'jira_access': sorted(jira_access, key=lambda r: r.get('site_key') or ''),
            'jira_site_count': len(jira_access),
            'raw_assignment_count': len(assignments),
        })
        if index % 10 == 0 or index == len(users):
            print(f'Checked {index}/{len(users)} users; raw assignments: {raw_assignment_count}; named Jira mappings: {len(mapping_keys)}')
        if delay > 0:
            time.sleep(delay)

    mapping_count = len(mapping_keys)
    aligned = mapping_count == expected
    site_rows = [{'site_key': k, 'named_access_count': v} for k, v in sorted(site_counts.items(), key=lambda x: (-x[1], x[0]))]
    payload = {
        'schema': 'jom-admin-named-access-v3.3-role-assignments-jira-software-entitlement',
        'generated_at_utc': now_utc(),
        'source': 'Atlassian Admin v2 directory user role-assignments; jira-software site ARIs treated as named Jira entitlement',
        'scope_source': scope_source,
        'directory_id': directory_id,
        'summary': {
            'status': 'aligned' if aligned else 'mismatch',
            'severity': 'ok' if aligned and not errors else 'critical',
            'human_users_scoped': len(users),
            'raw_assignment_count': raw_assignment_count,
            'jira_mappings': mapping_count,
            'expected_mappings': expected,
            'difference': mapping_count - expected,
            'site_count': len(site_rows),
            'error_count': len(errors),
            'resource_owner_counts': resource_owner_counts,
            'role_counts': role_counts,
            'filter_counts': filter_counts,
            'safe_to_enable_named_access_ui': aligned and not errors,
        },
        'site_counts': site_rows,
        'users': sorted(output_users, key=lambda r: (-int(r.get('jira_site_count') or 0), str(r.get('display_name') or r.get('email') or '').lower())),
        'errors': errors,
        'diagnostics': {'accepted_samples': accepted_samples, 'rejected_jira_samples': rejected_jira_samples},
        'guardrail': 'Do not enable named access UI unless aligned and manually validated against Atlassian Directory Apps tab.',
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', default='.')
    parser.add_argument('--expected', type=int, default=EXPECTED_DEFAULT)
    parser.add_argument('--delay', type=float, default=0.05)
    parser.add_argument('--output', default='static/data/admin_named_access.json')
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    payload = collect(root, args.expected, args.delay)
    out = Path(args.output)
    if not out.is_absolute():
        out = root / out
    write_json(out, payload)

    report = root / 'reports' / 'admin_named_access_v3_3_summary.md'
    lines = ['# Admin Named Access v3.3 Summary', '', f"Generated: `{payload.get('generated_at_utc')}`", '', '## Summary', '']
    for k, v in payload.get('summary', {}).items():
        lines.append(f'- **{k}:** {v}')
    lines += ['', '## Site Counts', '']
    for row in payload.get('site_counts', []):
        lines.append(f"- **{row.get('site_key')}**: {row.get('named_access_count')}")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text('\n'.join(lines), encoding='utf-8')

    print('Admin Named Access Collector v3.3 complete.')
    print(json.dumps(payload.get('summary', {}), indent=2))
    print(f'Output: {out}')
    print(f'Report: {report}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
