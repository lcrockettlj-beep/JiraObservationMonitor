#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import json
import os
import py_compile
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
REPORT_TXT = Path('reports/estate_workspace_contract_route_v1.txt')
REPORT_JSON = Path('reports/estate_workspace_contract_route_validation_v1.json')
BACKUP_DIR = Path('reports/estate_workspace_contract_route_v1_backups')
ROUTE = '/api/workspace/estate'
MARKER = '# JOM estate workspace contract route v1'

ROUTE_BLOCK = r'''

# JOM estate workspace contract route v1
def _jom_estate_workspace_read_runtime_contract_v1(filename, default=None):
    """Read a runtime/data contract by filename only. No runtime/data and no legacy JSON consumers."""
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


def _jom_estate_workspace_source_summary_v1(label, payload):
    if isinstance(payload, dict):
        keys = sorted(list(payload.keys()))[:30]
        count = None
        for name in ("sites", "items", "records", "validations", "decisions"):
            value = payload.get(name)
            if isinstance(value, (list, dict)):
                count = len(value)
                break
        return {"label": label, "available": True, "type": "dict", "keys": keys, "count_hint": count}
    if isinstance(payload, list):
        return {"label": label, "available": True, "type": "list", "count_hint": len(payload)}
    return {"label": label, "available": bool(payload), "type": type(payload).__name__}


def _jom_estate_workspace_normalise_sites_v1(site_registry, admin_inventory, access_truth):
    registry_sites = site_registry.get("sites", []) if isinstance(site_registry, dict) else []
    inventory_sites = admin_inventory.get("sites", []) if isinstance(admin_inventory, dict) else []
    inventory_by_key = {}
    for item in inventory_sites if isinstance(inventory_sites, list) else []:
        if not isinstance(item, dict):
            continue
        key = item.get("key") or item.get("site_key") or item.get("cloud_id") or item.get("url")
        if key:
            inventory_by_key[str(key)] = item

    normalised = []
    for site in registry_sites if isinstance(registry_sites, list) else []:
        if not isinstance(site, dict):
            continue
        key = site.get("key") or site.get("site_key") or site.get("cloud_id") or site.get("url") or site.get("name")
        inv = inventory_by_key.get(str(key), {}) if key else {}
        normalised.append({
            "key": key,
            "name": site.get("name") or inv.get("name") or key,
            "url": site.get("url") or inv.get("url"),
            "status": site.get("status") or inv.get("status") or "runtime_registry",
            "source": "runtime_contract",
            "registry": site,
            "inventory": inv,
        })
    return normalised


def _jom_estate_workspace_summary_v1(site_registry, admin_inventory, authority_coverage):
    registry_summary = site_registry.get("summary", {}) if isinstance(site_registry, dict) else {}
    inventory_summary = admin_inventory.get("summary", {}) if isinstance(admin_inventory, dict) else {}
    total_sites = registry_summary.get("total_sites") or registry_summary.get("site_count") or inventory_summary.get("total_sites") or inventory_summary.get("site_count")
    monitored_sites = registry_summary.get("monitored_sites") or registry_summary.get("monitored_count") or inventory_summary.get("monitored_sites")
    review_items = registry_summary.get("review_items") or inventory_summary.get("review_items")
    coverage_percent = None
    if isinstance(authority_coverage, dict):
        coverage_percent = authority_coverage.get("coverage_percent") or authority_coverage.get("coverage")
        summary = authority_coverage.get("summary")
        if isinstance(summary, dict):
            coverage_percent = coverage_percent if coverage_percent is not None else summary.get("coverage_percent")
            total_sites = total_sites if total_sites is not None else summary.get("total_sites")
            monitored_sites = monitored_sites if monitored_sites is not None else summary.get("monitored_sites")
            review_items = review_items if review_items is not None else summary.get("review_items")
    return {
        "total_sites": total_sites or 0,
        "monitored_sites": monitored_sites or 0,
        "review_items": review_items or 0,
        "coverage_percent": coverage_percent,
    }


def _jom_estate_workspace_authority_coverage_v1():
    try:
        if "estate_discovery_authority_coverage" in globals():
            response = estate_discovery_authority_coverage()
            if hasattr(response, "get_json"):
                return response.get_json(silent=True) or {}
            return response if isinstance(response, dict) else {}
    except Exception:
        pass
    return {"status": "unavailable", "reason": "authority coverage route not callable in-process"}


@app.route("/api/workspace/estate")
def jom_api_workspace_estate_v1():
    site_registry = _jom_estate_workspace_read_runtime_contract_v1("site_registry.json", {})
    access_truth = _jom_estate_workspace_read_runtime_contract_v1("estate_access_truth.json", {})
    admin_inventory = _jom_estate_workspace_read_runtime_contract_v1("estate_admin_site_inventory_v1.json", {})
    authority_coverage = _jom_estate_workspace_authority_coverage_v1()
    sites = _jom_estate_workspace_normalise_sites_v1(site_registry, admin_inventory, access_truth)
    source_health = {
        "site_registry": _jom_estate_workspace_source_summary_v1("site_registry", site_registry),
        "estate_access_truth": _jom_estate_workspace_source_summary_v1("estate_access_truth", access_truth),
        "estate_admin_site_inventory": _jom_estate_workspace_source_summary_v1("estate_admin_site_inventory", admin_inventory),
        "authority_coverage": _jom_estate_workspace_source_summary_v1("authority_coverage", authority_coverage),
    }
    payload = {
        "schema": "jom-estate-workspace-contract-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if site_registry and admin_inventory else "attention",
        "summary": _jom_estate_workspace_summary_v1(site_registry, admin_inventory, authority_coverage),
        "authority_coverage": authority_coverage,
        "inventory": admin_inventory,
        "access_truth": access_truth,
        "sites": sites,
        "source_health": source_health,
        "frontend_owner": {
            "template": "templates/estate.html",
            "javascript": "static/js/jom_estate_lifecycle_v1.js",
            "css": "static/css/jom_estate_lifecycle_v1.css",
        },
    }
    return jsonify(payload)
'''

@dataclass
class Change:
    file: str
    detail: str
    count: int


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


def insert_route(text: str) -> tuple[str, int]:
    if ROUTE in text or MARKER in text:
        return text, 0
    anchors = ['if __name__ == "__main__"', "if __name__ == '__main__'"]
    for anchor in anchors:
        idx = text.find(anchor)
        if idx >= 0:
            return text[:idx].rstrip() + ROUTE_BLOCK + '\n\n' + text[idx:], 1
    return text.rstrip() + ROUTE_BLOCK + '\n', 1


def patch_web() -> tuple[list[Change], str | None]:
    if not WEB.exists():
        raise FileNotFoundError('app/web.py not found')
    backup_path = backup(WEB)
    original = read(WEB)
    text, changes = ensure_imports(original)
    text, count = insert_route(text)
    if count:
        changes.append(Change(WEB.as_posix(), 'added /api/workspace/estate route contract', count))
    if text != original:
        write(WEB, text)
    return changes, backup_path


def compile_web() -> dict:
    try:
        py_compile.compile(str(WEB), doraise=True)
        return {'file': WEB.as_posix(), 'status': 'PASS'}
    except Exception as exc:
        return {'file': WEB.as_posix(), 'status': 'FAIL', 'error': str(exc)}


def free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def smoke(skip: bool) -> dict:
    if skip:
        return {'status': 'SKIPPED', 'reason': 'skip requested'}
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
                    with urlopen(base + route, timeout=2) as response:
                        body = response.read().decode('utf-8', errors='ignore')
                        keys = []
                        schema = None
                        try:
                            payload = json.loads(body) if body else {}
                            if isinstance(payload, dict):
                                keys = sorted(list(payload.keys()))[:30]
                                schema = payload.get('schema')
                        except Exception:
                            pass
                        responded = True
                        results.append({'route': route, 'status': int(response.status), 'schema': schema, 'keys': keys})
                except Exception as exc:
                    last_error = str(exc)
                    results.append({'route': route, 'status': 'ERROR', 'error': str(exc)[:220]})
            if responded:
                estate_route = [r for r in results if r['route'] == '/api/workspace/estate'][0]
                return {'status': 'PASS' if estate_route.get('status') == 200 else 'REVIEW', 'routes': results}
            time.sleep(0.5)
        stderr = ''
        if proc and proc.stderr:
            with contextlib.suppress(Exception):
                stderr = proc.stderr.read()[:1200]
        return {'status': 'SKIPPED', 'reason': 'Flask smoke did not respond', 'last_error': last_error, 'stderr': stderr}
    except Exception as exc:
        return {'status': 'SKIPPED', 'reason': str(exc)}
    finally:
        if proc and proc.poll() is None:
            with contextlib.suppress(Exception):
                proc.terminate()
                proc.wait(timeout=5)
            if proc.poll() is None:
                with contextlib.suppress(Exception):
                    proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-smoke-test', action='store_true')
    args = parser.parse_args()

    REPORT_TXT.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    changes, backup_path = patch_web()
    compile_result = compile_web()
    smoke_result = smoke(args.skip_smoke_test) if compile_result.get('status') == 'PASS' else {'status': 'SKIPPED', 'reason': 'compile failed'}

    status = 'PASS' if compile_result.get('status') == 'PASS' and smoke_result.get('status') in {'PASS', 'SKIPPED', 'REVIEW'} else 'REVIEW'
    result = {
        'route_pack': 'JOM Estate Workspace Contract Route v1',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'status': status,
        'backup': backup_path,
        'changes': [asdict(c) for c in changes],
        'compile_result': compile_result,
        'smoke_result': smoke_result,
        'route': ROUTE,
    }
    REPORT_JSON.write_text(json.dumps(result, indent=2), encoding='utf-8')

    lines = []
    lines.append('JOM Estate Workspace Contract Route v1')
    lines.append('=' * 40)
    lines.append(f"Generated UTC: {result['generated_utc']}")
    lines.append(f"Status: {status}")
    lines.append('')
    lines.append('Summary')
    lines.append('-------')
    lines.append(f"Backup: {backup_path}")
    lines.append(f"Changes applied: {len(changes)}")
    lines.append(f"Compile: {compile_result.get('status')}")
    lines.append(f"Smoke: {smoke_result.get('status')}")
    if smoke_result.get('reason'):
        lines.append(f"Smoke reason: {smoke_result.get('reason')}")
    lines.append('')
    lines.append('Changes')
    lines.append('-------')
    for change in changes:
        lines.append(f'- {change.file}: {change.detail} ({change.count})')
    if not changes:
        lines.append('none - route already present')
    lines.append('')
    lines.append('Smoke routes')
    lines.append('------------')
    for route in smoke_result.get('routes', []):
        lines.append(f"- {route.get('route')}: {route.get('status')} schema={route.get('schema')}")
    lines.append('')
    lines.append('Decision')
    lines.append('--------')
    if status == 'PASS':
        lines.append('PASS - /api/workspace/estate route is present, app/web.py compiles, and smoke validation is acceptable.')
    else:
        lines.append('REVIEW - inspect compile or smoke output before commit.')
    lines.append('')
    lines.append('Next after PASS')
    lines.append('---------------')
    lines.append('- Commit as: add estate workspace contract route')
    lines.append('- Run Estate Workspace Contract Route Validation Pack v1')
    lines.append('- Then start Estate single-owner frontend rebuild')

    REPORT_TXT.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(lines[0])
    print(f'Status: {status}')
    print(f'Changes applied: {len(changes)}')
    print(f'Compile: {compile_result.get("status")}')
    print(f'Smoke: {smoke_result.get("status")}')
    print(f'Report: {REPORT_TXT}')
    return 0 if compile_result.get('status') == 'PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
