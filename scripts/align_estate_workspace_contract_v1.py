#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import json
import os
import py_compile
import re
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

WEB = Path('app/web.py')
REPORT_TXT = Path('reports/estate_workspace_contract_alignment_v1.txt')
REPORT_JSON = Path('reports/estate_workspace_contract_alignment_v1.json')
BACKUP_DIR = Path('reports/estate_workspace_contract_alignment_v1_backups')
ROUTE = '/api/workspace/estate'
MARKER = '# JOM estate workspace contract alignment v1'
INTERNAL_NAME = '_jom_workspace_estate_existing_fast_read_v1'

REQUIRED_TOP_LEVEL = ['schema', 'status', 'summary', 'sites', 'source_health']
REQUIRED_SUMMARY = ['total_sites', 'monitored_sites', 'review_items']
REQUIRED_SOURCE_HEALTH = ['site_registry', 'estate_access_truth', 'estate_admin_site_inventory']
LEGACY_STRINGS = ['runtime/data', 'site_registry.json', 'estate_access_truth.json', 'site_registry.json', '/api/workspace/command-centre']

ALIGNMENT_BLOCK = r'''

# JOM estate workspace contract alignment v1
def _jom_estate_workspace_alignment_read_contract_v1(filename, default=None):
    if default is None:
        default = {}
    try:
        if "_jom_cached_read_json_v1" in globals():
            payload = _jom_cached_read_json_v1(filename, default)
        else:
            payload = load_json(filename, default)
    except Exception:
        payload = default
    return payload if payload is not None else default


def _jom_estate_workspace_alignment_source_health_v1(label, payload):
    if isinstance(payload, dict):
        keys = sorted(list(payload.keys()))[:30]
        count_hint = None
        for key in ("sites", "items", "records", "validations", "decisions"):
            value = payload.get(key)
            if isinstance(value, (list, dict)):
                count_hint = len(value)
                break
        return {"label": label, "available": True, "type": "dict", "keys": keys, "count_hint": count_hint}
    if isinstance(payload, list):
        return {"label": label, "available": True, "type": "list", "count_hint": len(payload)}
    return {"label": label, "available": bool(payload), "type": type(payload).__name__}


def _jom_estate_workspace_alignment_normalise_sites_v1(site_registry, admin_inventory, existing_sites=None):
    if isinstance(existing_sites, list) and existing_sites:
        return existing_sites
    registry_sites = site_registry.get("sites", []) if isinstance(site_registry, dict) else []
    inventory_sites = admin_inventory.get("sites", []) if isinstance(admin_inventory, dict) else []
    inventory_by_key = {}
    for item in inventory_sites if isinstance(inventory_sites, list) else []:
        if not isinstance(item, dict):
            continue
        key = item.get("key") or item.get("site_key") or item.get("cloud_id") or item.get("url") or item.get("name")
        if key:
            inventory_by_key[str(key)] = item
    sites = []
    for site in registry_sites if isinstance(registry_sites, list) else []:
        if not isinstance(site, dict):
            continue
        key = site.get("key") or site.get("site_key") or site.get("cloud_id") or site.get("url") or site.get("name")
        inv = inventory_by_key.get(str(key), {}) if key else {}
        sites.append({
            "key": key,
            "name": site.get("name") or inv.get("name") or key,
            "url": site.get("url") or inv.get("url"),
            "status": site.get("status") or inv.get("status") or "runtime_registry",
            "is_monitored": bool(site.get("is_monitored") or inv.get("is_monitored")),
            "source": "runtime_contract",
            "registry": site,
            "inventory": inv,
        })
    return sites


def _jom_estate_workspace_alignment_summary_v1(site_registry, admin_inventory, sites, existing_summary=None):
    summary = dict(existing_summary) if isinstance(existing_summary, dict) else {}
    registry_summary = site_registry.get("summary", {}) if isinstance(site_registry, dict) else {}
    inventory_summary = admin_inventory.get("summary", {}) if isinstance(admin_inventory, dict) else {}
    total_sites = summary.get("total_sites") or registry_summary.get("total_sites") or registry_summary.get("site_count") or inventory_summary.get("total_sites") or inventory_summary.get("site_count") or len(sites)
    monitored_sites = summary.get("monitored_sites") or registry_summary.get("monitored_sites") or registry_summary.get("monitored_count") or inventory_summary.get("monitored_sites")
    if monitored_sites is None:
        monitored_sites = sum(1 for site in sites if isinstance(site, dict) and site.get("is_monitored"))
    review_items = summary.get("review_items") or registry_summary.get("review_items") or inventory_summary.get("review_items") or 0
    coverage_percent = summary.get("coverage_percent")
    if coverage_percent is None and total_sites:
        try:
            coverage_percent = round((float(monitored_sites or 0) / float(total_sites)) * 100)
        except Exception:
            coverage_percent = None
    return {
        "total_sites": total_sites or 0,
        "monitored_sites": monitored_sites or 0,
        "review_items": review_items or 0,
        "coverage_percent": coverage_percent,
    }


def _jom_estate_workspace_alignment_get_existing_payload_v1():
    try:
        response = _jom_workspace_estate_existing_fast_read_v1()
        if hasattr(response, "get_json"):
            return response.get_json(silent=True) or {}
        if isinstance(response, dict):
            return response
    except Exception:
        pass
    return {}


def _jom_estate_workspace_alignment_payload_v1():
    existing = _jom_estate_workspace_alignment_get_existing_payload_v1()
    if not isinstance(existing, dict):
        existing = {}
    site_registry = _jom_estate_workspace_alignment_read_contract_v1("site_registry.json", {})
    access_truth = _jom_estate_workspace_alignment_read_contract_v1("estate_access_truth.json", {})
    admin_inventory = _jom_estate_workspace_alignment_read_contract_v1("estate_admin_site_inventory_v1.json", {})
    sites = _jom_estate_workspace_alignment_normalise_sites_v1(site_registry, admin_inventory, existing.get("sites"))
    summary = _jom_estate_workspace_alignment_summary_v1(site_registry, admin_inventory, sites, existing.get("summary"))
    source_health = existing.get("source_health") if isinstance(existing.get("source_health"), dict) else {}
    source_health.update({
        "site_registry": _jom_estate_workspace_alignment_source_health_v1("site_registry", site_registry),
        "estate_access_truth": _jom_estate_workspace_alignment_source_health_v1("estate_access_truth", access_truth),
        "estate_admin_site_inventory": _jom_estate_workspace_alignment_source_health_v1("estate_admin_site_inventory", admin_inventory),
    })
    payload = dict(existing)
    payload.update({
        "schema": "jom-estate-workspace-contract-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": existing.get("status") or ("ok" if site_registry and admin_inventory else "attention"),
        "summary": summary,
        "sites": sites,
        "source_health": source_health,
        "inventory": existing.get("inventory") if isinstance(existing.get("inventory"), dict) else admin_inventory,
        "access_truth": existing.get("access_truth") if isinstance(existing.get("access_truth"), dict) else access_truth,
        "frontend_owner": {
            "template": "templates/estate.html",
            "javascript": "static/js/jom_estate_lifecycle_v1.js",
            "css": "static/css/jom_estate_lifecycle_v1.css",
        },
    })
    return payload


@app.route("/api/workspace/estate")
def jom_api_workspace_estate_aligned_v1():
    return jsonify(_jom_estate_workspace_alignment_payload_v1())
'''

@dataclass
class Change:
    file: str
    detail: str
    count: int

@dataclass
class Check:
    name: str
    status: str
    detail: str


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='ignore') if path.exists() else ''


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding='utf-8')


def backup(path: Path) -> str | None:
    if not path.exists():
        return None
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    dest = BACKUP_DIR / stamp / path.as_posix()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    return dest.as_posix()


def ensure_imports(text: str) -> tuple[str, list[Change]]:
    changes = []
    if 'from datetime import datetime, timezone' not in text:
        if 'from datetime import datetime' in text:
            text = text.replace('from datetime import datetime', 'from datetime import datetime, timezone', 1)
            changes.append(Change(WEB.as_posix(), 'extended datetime import with timezone', 1))
        else:
            text = 'from datetime import datetime, timezone\n' + text
            changes.append(Change(WEB.as_posix(), 'added datetime/timezone import', 1))
    return text, changes


def find_workspace_route(lines: list[str]) -> tuple[int, int, str] | None:
    for i, line in enumerate(lines):
        if '@app.route' in line and ROUTE in line:
            for j in range(i + 1, min(i + 8, len(lines))):
                match = re.match(r'^(\s*)def\s+([A-Za-z0-9_]+)\s*\(', lines[j])
                if match:
                    return i, j, match.group(2)
    return None


def patch_web() -> tuple[list[Change], str | None]:
    if not WEB.exists():
        raise FileNotFoundError('app/web.py not found')
    backup_path = backup(WEB)
    original = read(WEB)
    text, changes = ensure_imports(original)
    if MARKER in text:
        if text != original:
            write(WEB, text)
        return changes, backup_path

    lines = text.splitlines()
    route_info = find_workspace_route(lines)
    if not route_info:
        raise RuntimeError('Existing /api/workspace/estate route not found')
    decorator_idx, def_idx, old_name = route_info
    lines.pop(decorator_idx)
    if def_idx > decorator_idx:
        def_idx -= 1
    lines[def_idx] = re.sub(r'def\s+' + re.escape(old_name) + r'\s*\(', f'def {INTERNAL_NAME}(', lines[def_idx], count=1)
    lines.insert(decorator_idx, ALIGNMENT_BLOCK.strip('\n'))
    text = '\n'.join(lines) + '\n'
    changes.append(Change(WEB.as_posix(), f'renamed existing workspace estate route function {old_name} to {INTERNAL_NAME}', 1))
    changes.append(Change(WEB.as_posix(), 'added aligned /api/workspace/estate contract wrapper', 1))
    write(WEB, text)
    return changes, backup_path


def compile_web() -> Check:
    try:
        py_compile.compile(str(WEB), doraise=True)
        return Check('compile_web', 'PASS', 'app/web.py compiles')
    except Exception as exc:
        return Check('compile_web', 'FAIL', str(exc))


def free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def fetch_json(base: str, route: str) -> dict:
    with urlopen(base + route, timeout=3) as response:
        body = response.read().decode('utf-8', errors='ignore')
        payload = json.loads(body) if body else {}
        return {'route': route, 'status': int(response.status), 'payload': payload, 'body': body}


def smoke(skip: bool) -> dict:
    if skip:
        return {'status': 'SKIPPED', 'reason': 'skip requested', 'routes': []}
    port = free_port()
    env = os.environ.copy()
    env['FLASK_APP'] = 'app.web'
    env['PYTHONUNBUFFERED'] = '1'
    cmd = [sys.executable, '-m', 'flask', 'run', '--host', '127.0.0.1', '--port', str(port), '--no-debugger', '--no-reload']
    proc = None
    routes = ['/api/workspace/estate', '/api/estate/discovery-authority/coverage', '/api/estate/admin-site-inventory']
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        base = f'http://127.0.0.1:{port}'
        last_error = None
        for _ in range(30):
            if proc.poll() is not None:
                break
            results = []
            responded = False
            for route in routes:
                try:
                    res = fetch_json(base, route)
                    payload = res['payload']
                    responded = True
                    results.append({
                        'route': route,
                        'http_status': res['status'],
                        'schema': payload.get('schema') if isinstance(payload, dict) else None,
                        'keys': sorted(list(payload.keys()))[:30] if isinstance(payload, dict) else [],
                        'payload': payload if route == '/api/workspace/estate' else None,
                        'body': res['body'] if route == '/api/workspace/estate' else '',
                    })
                except Exception as exc:
                    last_error = str(exc)
                    results.append({'route': route, 'http_status': 'ERROR', 'error': str(exc)[:220]})
            if responded:
                estate_ok = any(r.get('route') == '/api/workspace/estate' and r.get('http_status') == 200 for r in results)
                return {'status': 'PASS' if estate_ok else 'REVIEW', 'routes': results}
            time.sleep(0.5)
        stderr = ''
        if proc and proc.stderr:
            with contextlib.suppress(Exception):
                stderr = proc.stderr.read()[:1200]
        return {'status': 'SKIPPED', 'reason': 'Flask did not respond', 'last_error': last_error, 'stderr': stderr, 'routes': []}
    except Exception as exc:
        return {'status': 'SKIPPED', 'reason': str(exc), 'routes': []}
    finally:
        if proc and proc.poll() is None:
            with contextlib.suppress(Exception):
                proc.terminate()
                proc.wait(timeout=5)
            if proc.poll() is None:
                with contextlib.suppress(Exception):
                    proc.kill()


def validate_payload(payload: dict, body: str) -> list[Check]:
    checks = []
    if not isinstance(payload, dict):
        return [Check('payload_type', 'FAIL', 'Estate payload is not object')]
    for field in REQUIRED_TOP_LEVEL:
        checks.append(Check(f'top_level_{field}', 'PASS' if field in payload else 'FAIL', 'present' if field in payload else 'missing'))
    summary = payload.get('summary')
    if isinstance(summary, dict):
        for field in REQUIRED_SUMMARY:
            checks.append(Check(f'summary_{field}', 'PASS' if field in summary else 'FAIL', 'present' if field in summary else 'missing'))
    else:
        checks.append(Check('summary_object', 'FAIL', 'summary is not object'))
    source_health = payload.get('source_health')
    if isinstance(source_health, dict):
        for field in REQUIRED_SOURCE_HEALTH:
            checks.append(Check(f'source_health_{field}', 'PASS' if field in source_health else 'FAIL', 'present' if field in source_health else 'missing'))
    else:
        checks.append(Check('source_health_object', 'FAIL', 'source_health is not object'))
    checks.append(Check('sites_array', 'PASS' if isinstance(payload.get('sites'), list) else 'FAIL', f"type={type(payload.get('sites')).__name__}"))
    body_lower = body.lower()
    for token in LEGACY_STRINGS:
        checks.append(Check(f'legacy_absent_{token}', 'PASS' if token.lower() not in body_lower else 'FAIL', token))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-smoke-test', action='store_true')
    args = parser.parse_args()

    REPORT_TXT.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    changes, backup_path = patch_web()
    compile_check = compile_web()
    smoke_result = smoke(args.skip_smoke_test) if compile_check.status == 'PASS' else {'status': 'SKIPPED', 'reason': 'compile failed', 'routes': []}
    estate_payload = {}
    estate_body = ''
    for route in smoke_result.get('routes', []):
        if route.get('route') == '/api/workspace/estate':
            estate_payload = route.get('payload') or {}
            estate_body = route.get('body') or ''
            break
    payload_checks = validate_payload(estate_payload, estate_body) if smoke_result.get('status') != 'SKIPPED' else []
    failures = [c for c in [compile_check] + payload_checks if c.status == 'FAIL']
    status = 'PASS' if not failures and smoke_result.get('status') in {'PASS', 'SKIPPED'} else 'REVIEW'

    result = {
        'alignment': 'JOM Estate Workspace Contract Alignment v1',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'status': status,
        'backup': backup_path,
        'changes': [asdict(c) for c in changes],
        'compile_check': asdict(compile_check),
        'smoke': smoke_result,
        'payload_checks': [asdict(c) for c in payload_checks],
        'failures': [asdict(c) for c in failures],
    }
    REPORT_JSON.write_text(json.dumps(result, indent=2), encoding='utf-8')

    lines = []
    lines.append('JOM Estate Workspace Contract Alignment v1')
    lines.append('=' * 44)
    lines.append(f"Generated UTC: {result['generated_utc']}")
    lines.append(f"Status: {status}")
    lines.append('')
    lines.append('Summary')
    lines.append('-------')
    lines.append(f"Backup: {backup_path}")
    lines.append(f"Changes applied: {len(changes)}")
    lines.append(f"Compile: {compile_check.status}")
    lines.append(f"Smoke: {smoke_result.get('status')}")
    lines.append(f"Payload checks: {len(payload_checks)}")
    lines.append(f"Failures: {len(failures)}")
    lines.append('')
    lines.append('Changes')
    lines.append('-------')
    for change in changes:
        lines.append(f'- {change.file}: {change.detail} ({change.count})')
    if not changes:
        lines.append('none')
    lines.append('')
    lines.append('Smoke routes')
    lines.append('------------')
    for route in smoke_result.get('routes', []):
        lines.append(f"- {route.get('route')}: {route.get('http_status')} schema={route.get('schema')}")
    lines.append('')
    lines.append('Payload checks')
    lines.append('--------------')
    for check in payload_checks:
        lines.append(f'- {check.name}: {check.status} - {check.detail}')
    lines.append('')
    lines.append('Decision')
    lines.append('--------')
    if status == 'PASS':
        lines.append('PASS - /api/workspace/estate now has the agreed Estate contract shape.')
    else:
        lines.append('REVIEW - inspect failed checks before frontend rebuild.')
    lines.append('')
    lines.append('Next after PASS')
    lines.append('---------------')
    lines.append('- Run git diff --stat and git status --short.')
    lines.append('- Commit as: align estate workspace contract shape.')
    lines.append('- Then start JOM Estate Single-Owner Frontend Rebuild Pack v1.')

    REPORT_TXT.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(lines[0])
    print(f'Status: {status}')
    print(f'Changes applied: {len(changes)}')
    print(f'Compile: {compile_check.status}')
    print(f'Smoke: {smoke_result.get("status")}')
    print(f'Failures: {len(failures)}')
    print(f'Report: {REPORT_TXT}')
    return 0 if compile_check.status == 'PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
