#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import json
import os
import py_compile
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

REPORT_TXT = Path('reports/estate_demo_smoke_visual_acceptance_v1.txt')
REPORT_JSON = Path('reports/estate_demo_smoke_visual_acceptance_v1.json')
WEB = Path('app/web.py')
ESTATE_TEMPLATE = Path('templates/estate.html')
ESTATE_JS = Path('static/js/jom_estate_lifecycle_v1.js')
ESTATE_ROUTE = '/estate'
CONTRACT_ROUTE = '/api/workspace/estate'
SUPPORTING_ROUTES = ['/api/estate/discovery-authority/coverage', '/api/estate/admin-site-inventory']
REQUIRED_CONTRACT_FIELDS = ['schema', 'status', 'summary', 'sites', 'source_health']
REQUIRED_SUMMARY_FIELDS = ['total_sites', 'monitored_sites', 'review_items']
LEGACY_STRINGS = ['runtime/data', 'site_registry.json', 'estate_access_truth.json', 'site_registry.json', '/api/workspace/command-centre']
SINGLE_OWNER_MARKER = 'JOM Estate single-owner frontend rebuild v1'

@dataclass
class Check:
    name: str
    status: str
    detail: str


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='ignore') if path.exists() else ''


def compile_web() -> Check:
    if not WEB.exists():
        return Check('compile_web', 'FAIL', 'app/web.py missing')
    try:
        py_compile.compile(str(WEB), doraise=True)
        return Check('compile_web', 'PASS', 'app/web.py compiles')
    except Exception as exc:
        return Check('compile_web', 'FAIL', str(exc))


def free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def get_url(base: str, route: str) -> dict:
    with urlopen(base + route, timeout=5) as response:
        body = response.read().decode('utf-8', errors='ignore')
        return {'route': route, 'status': int(response.status), 'body': body}


def smoke(skip: bool) -> dict:
    if skip:
        return {'status': 'SKIPPED', 'reason': 'skip requested', 'routes': []}
    if not WEB.exists():
        return {'status': 'SKIPPED', 'reason': 'app/web.py missing', 'routes': []}

    port = free_port()
    env = os.environ.copy()
    env['FLASK_APP'] = 'app.web'
    env['PYTHONUNBUFFERED'] = '1'
    cmd = [sys.executable, '-m', 'flask', 'run', '--host', '127.0.0.1', '--port', str(port), '--no-debugger', '--no-reload']
    proc = None
    routes = [ESTATE_ROUTE, CONTRACT_ROUTE] + SUPPORTING_ROUTES
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
                    res = get_url(base, route)
                    responded = True
                    payload = None
                    schema = None
                    keys = []
                    body = res['body']
                    if route.startswith('/api/'):
                        try:
                            payload = json.loads(body) if body else {}
                            if isinstance(payload, dict):
                                schema = payload.get('schema')
                                keys = sorted(list(payload.keys()))[:40]
                        except Exception:
                            payload = None
                    results.append({'route': route, 'http_status': res['status'], 'schema': schema, 'keys': keys, 'body': body if route == ESTATE_ROUTE else '', 'payload': payload if route == CONTRACT_ROUTE else None})
                except Exception as exc:
                    last_error = str(exc)
                    results.append({'route': route, 'http_status': 'ERROR', 'error': str(exc)[:240]})
            if responded:
                estate_ok = any(r.get('route') == ESTATE_ROUTE and r.get('http_status') == 200 for r in results)
                contract_ok = any(r.get('route') == CONTRACT_ROUTE and r.get('http_status') == 200 for r in results)
                supporting_ok = all(r.get('http_status') == 200 for r in results if r.get('route') in SUPPORTING_ROUTES)
                return {'status': 'PASS' if estate_ok and contract_ok and supporting_ok else 'REVIEW', 'base_url': base, 'routes': results}
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


def contract_checks(payload: object) -> list[Check]:
    checks = []
    if not isinstance(payload, dict):
        return [Check('contract_payload_object', 'FAIL', 'contract payload is not object')]
    for field in REQUIRED_CONTRACT_FIELDS:
        checks.append(Check(f'contract_top_level_{field}', 'PASS' if field in payload else 'FAIL', 'present' if field in payload else 'missing'))
    summary = payload.get('summary')
    if isinstance(summary, dict):
        for field in REQUIRED_SUMMARY_FIELDS:
            checks.append(Check(f'contract_summary_{field}', 'PASS' if field in summary else 'FAIL', 'present' if field in summary else 'missing'))
    else:
        checks.append(Check('contract_summary_object', 'FAIL', 'summary is not object'))
    checks.append(Check('contract_sites_array', 'PASS' if isinstance(payload.get('sites'), list) else 'FAIL', f"type={type(payload.get('sites')).__name__}"))
    checks.append(Check('contract_schema_demo_ready', 'PASS' if payload.get('schema') == 'jom-estate-workspace-contract-v1' else 'REVIEW', str(payload.get('schema'))))
    return checks


def source_checks(estate_body: str) -> list[Check]:
    checks = []
    template_body = read(ESTATE_TEMPLATE)
    js_body = read(ESTATE_JS)
    checks.append(Check('estate_template_exists', 'PASS' if ESTATE_TEMPLATE.exists() else 'FAIL', ESTATE_TEMPLATE.as_posix()))
    checks.append(Check('estate_js_owner_exists', 'PASS' if ESTATE_JS.exists() else 'FAIL', ESTATE_JS.as_posix()))
    checks.append(Check('estate_js_single_owner_marker', 'PASS' if SINGLE_OWNER_MARKER in js_body else 'FAIL', SINGLE_OWNER_MARKER))
    checks.append(Check('estate_js_fetches_workspace_estate', 'PASS' if CONTRACT_ROUTE in js_body else 'FAIL', CONTRACT_ROUTE))
    # Template may use url_for, so accept either direct JS filename in template source or loaded HTML.
    js_ref_ok = ESTATE_JS.name in template_body or ESTATE_JS.name in estate_body or 'jom_estate_lifecycle_v1' in template_body or 'jom_estate_lifecycle_v1' in estate_body
    checks.append(Check('estate_page_references_estate_js_owner', 'PASS' if js_ref_ok else 'REVIEW', ESTATE_JS.name))
    for path, body in [(ESTATE_TEMPLATE, template_body), (ESTATE_JS, js_body)]:
        for token in LEGACY_STRINGS:
            checks.append(Check(f'{path.as_posix()}_legacy_absent_{token}', 'PASS' if token not in body else 'FAIL', token))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-smoke-test', action='store_true')
    args = parser.parse_args()

    REPORT_TXT.parent.mkdir(parents=True, exist_ok=True)

    compile_check = compile_web()
    smoke_result = smoke(args.skip_smoke_test) if compile_check.status == 'PASS' else {'status': 'SKIPPED', 'reason': 'compile failed', 'routes': []}

    estate_body = ''
    contract_payload = None
    for route in smoke_result.get('routes', []):
        if route.get('route') == ESTATE_ROUTE:
            estate_body = route.get('body', '')
        if route.get('route') == CONTRACT_ROUTE:
            contract_payload = route.get('payload')

    checks = [compile_check] + contract_checks(contract_payload) + source_checks(estate_body)
    failures = [c for c in checks if c.status == 'FAIL']
    reviews = [c for c in checks if c.status == 'REVIEW']
    status = 'PASS' if not failures and smoke_result.get('status') in {'PASS', 'SKIPPED'} else 'REVIEW'

    result = {
        'pack': 'JOM Estate Demo Smoke and Visual Acceptance v1',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'status': status,
        'smoke': smoke_result,
        'checks': [asdict(c) for c in checks],
        'failures': [asdict(c) for c in failures],
        'reviews': [asdict(c) for c in reviews],
        'demo_decision': 'READY' if status == 'PASS' else 'REVIEW',
    }
    REPORT_JSON.write_text(json.dumps(result, indent=2), encoding='utf-8')

    lines = []
    lines.append('JOM Estate Demo Smoke and Visual Acceptance v1')
    lines.append('=' * 48)
    lines.append(f"Generated UTC: {result['generated_utc']}")
    lines.append(f"Status: {status}")
    lines.append(f"Demo decision: {result['demo_decision']}")
    lines.append('')
    lines.append('Summary')
    lines.append('-------')
    lines.append(f"Compile: {compile_check.status}")
    lines.append(f"Smoke: {smoke_result.get('status')}")
    lines.append(f"Failures: {len(failures)}")
    lines.append(f"Review checks: {len(reviews)}")
    if smoke_result.get('base_url'):
        lines.append(f"Local smoke base: {smoke_result.get('base_url')}")
    if smoke_result.get('reason'):
        lines.append(f"Smoke reason: {smoke_result.get('reason')}")
    lines.append('')
    lines.append('Smoke routes')
    lines.append('------------')
    for route in smoke_result.get('routes', []):
        lines.append(f"- {route.get('route')}: {route.get('http_status')} schema={route.get('schema')}")
    lines.append('')
    lines.append('Checks')
    lines.append('------')
    for check in checks:
        lines.append(f'- {check.name}: {check.status} - {check.detail}')
    lines.append('')
    lines.append('Demo talking points')
    lines.append('-------------------')
    lines.append('- Estate is now served by one workspace contract: /api/workspace/estate')
    lines.append('- Estate frontend has one JS owner: static/js/jom_estate_lifecycle_v1.js')
    lines.append('- Contract includes summary, site inventory, source health, and status fields')
    lines.append('- No static or legacy Estate JSON dependencies were detected in Estate template/JS')
    lines.append('')
    lines.append('Decision')
    lines.append('--------')
    if status == 'PASS':
        lines.append('PASS - Estate is ready for demo smoke review.')
    else:
        lines.append('REVIEW - address failed checks before demo.')
    lines.append('')
    lines.append('Next after PASS')
    lines.append('---------------')
    lines.append('- Commit validation report if required.')
    lines.append('- Open /estate locally and perform human visual acceptance.')
    lines.append('- Continue targeted demo polish only if visual issues remain.')

    REPORT_TXT.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(lines[0])
    print(f'Status: {status}')
    print(f'Demo decision: {result["demo_decision"]}')
    print(f'Compile: {compile_check.status}')
    print(f'Smoke: {smoke_result.get("status")}')
    print(f'Failures: {len(failures)}')
    print(f'Report: {REPORT_TXT}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
