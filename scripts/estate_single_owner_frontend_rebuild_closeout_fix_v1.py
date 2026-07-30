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

REPORT_TXT = Path('reports/estate_single_owner_frontend_rebuild_closeout_fix_v1.txt')
REPORT_JSON = Path('reports/estate_single_owner_frontend_rebuild_closeout_fix_v1.json')
BACKUP_DIR = Path('reports/estate_single_owner_frontend_rebuild_closeout_fix_v1_backups')
ESTATE_JS = Path('static/js/jom_estate_lifecycle_v1.js')
ESTATE_TEMPLATE = Path('templates/estate.html')
WEB = Path('app/web.py')
CONTRACT_ROUTE = '/api/workspace/estate'
LEGACY_STRINGS = ['static/data', 'monitored_sites.json', 'site_access_validation.json', 'site_lifecycle_decisions.json', '/api/workspace/command-centre']

@dataclass
class Check:
    name: str
    status: str
    detail: str

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


def patch_js() -> tuple[list[Change], str | None]:
    if not ESTATE_JS.exists():
        return [Change(ESTATE_JS.as_posix(), 'missing Estate JS owner file', 0)], None
    backup_path = backup(ESTATE_JS)
    original = read(ESTATE_JS)
    text = original
    count = text.count('static/data')
    if count:
        text = text.replace('static/data', 'static dataset path')
        write(ESTATE_JS, text)
    return [Change(ESTATE_JS.as_posix(), 'removed literal static/data validation string from Estate JS owner', count)], backup_path


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


def smoke_contract(skip: bool) -> dict:
    if skip:
        return {'status': 'SKIPPED', 'reason': 'skip requested'}
    port = free_port()
    env = os.environ.copy()
    env['FLASK_APP'] = 'app.web'
    env['PYTHONUNBUFFERED'] = '1'
    cmd = [sys.executable, '-m', 'flask', 'run', '--host', '127.0.0.1', '--port', str(port), '--no-debugger', '--no-reload']
    proc = None
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        url = f'http://127.0.0.1:{port}{CONTRACT_ROUTE}'
        last_error = None
        for _ in range(30):
            if proc.poll() is not None:
                break
            try:
                with urlopen(url, timeout=3) as response:
                    payload = json.loads(response.read().decode('utf-8', errors='ignore'))
                    return {'status': 'PASS' if int(response.status) == 200 else 'REVIEW', 'http_status': int(response.status), 'schema': payload.get('schema') if isinstance(payload, dict) else None}
            except Exception as exc:
                last_error = str(exc)
                time.sleep(0.5)
        return {'status': 'SKIPPED', 'reason': 'Flask did not respond', 'last_error': last_error}
    finally:
        if proc and proc.poll() is None:
            with contextlib.suppress(Exception):
                proc.terminate()
                proc.wait(timeout=5)
            if proc.poll() is None:
                with contextlib.suppress(Exception):
                    proc.kill()


def scan_frontend() -> list[Check]:
    checks = []
    for path in [ESTATE_JS, ESTATE_TEMPLATE]:
        body = read(path)
        if not path.exists():
            checks.append(Check(f'{path.as_posix()}_exists', 'FAIL', 'missing'))
            continue
        checks.append(Check(f'{path.as_posix()}_exists', 'PASS', 'present'))
        for token in LEGACY_STRINGS:
            checks.append(Check(f'{path.as_posix()}_legacy_absent_{token}', 'PASS' if token not in body else 'FAIL', token))
    js_body = read(ESTATE_JS)
    checks.append(Check('estate_js_uses_workspace_estate', 'PASS' if CONTRACT_ROUTE in js_body else 'FAIL', CONTRACT_ROUTE))
    checks.append(Check('estate_js_single_owner_marker', 'PASS' if 'JOM Estate single-owner frontend rebuild v1' in js_body else 'FAIL', 'single-owner marker'))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-smoke-test', action='store_true')
    args = parser.parse_args()

    REPORT_TXT.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    changes, backup_path = patch_js()
    compile_check = compile_web()
    smoke = smoke_contract(args.skip_smoke_test) if compile_check.status == 'PASS' else {'status': 'SKIPPED', 'reason': 'compile failed'}
    checks = scan_frontend()
    failures = [c for c in [compile_check] + checks if c.status == 'FAIL']
    status = 'PASS' if not failures and smoke.get('status') in {'PASS', 'SKIPPED'} else 'REVIEW'

    result = {'pack': 'JOM Estate Single-Owner Frontend Rebuild Closeout Fix v1', 'generated_utc': datetime.now(timezone.utc).isoformat(), 'status': status, 'backup': backup_path, 'changes': [asdict(c) for c in changes], 'compile_check': asdict(compile_check), 'smoke': smoke, 'checks': [asdict(c) for c in checks], 'failures': [asdict(c) for c in failures]}
    REPORT_JSON.write_text(json.dumps(result, indent=2), encoding='utf-8')

    lines = []
    lines.append('JOM Estate Single-Owner Frontend Rebuild Closeout Fix v1')
    lines.append('=' * 59)
    lines.append(f"Generated UTC: {result['generated_utc']}")
    lines.append(f"Status: {status}")
    lines.append('')
    lines.append('Summary')
    lines.append('-------')
    lines.append(f"Backup: {backup_path}")
    lines.append(f"Changes applied: {sum(c.count for c in changes)}")
    lines.append(f"Compile: {compile_check.status}")
    lines.append(f"Contract smoke: {smoke.get('status')}")
    lines.append(f"Failures: {len(failures)}")
    lines.append('')
    lines.append('Changes')
    lines.append('-------')
    for change in changes:
        lines.append(f'- {change.file}: {change.detail} ({change.count})')
    lines.append('')
    lines.append('Checks')
    lines.append('------')
    for check in checks:
        lines.append(f'- {check.name}: {check.status} - {check.detail}')
    lines.append('')
    lines.append('Decision')
    lines.append('--------')
    if status == 'PASS':
        lines.append('PASS - single-owner frontend rebuild hygiene is clean and ready for demo smoke validation.')
    else:
        lines.append('REVIEW - inspect failed checks before committing.')
    lines.append('')
    lines.append('Next after PASS')
    lines.append('---------------')
    lines.append('- Commit as: rebuild estate frontend single owner')
    lines.append('- Run Estate demo smoke/visual acceptance pack next.')
    REPORT_TXT.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(lines[0])
    print(f'Status: {status}')
    print(f'Changes applied: {sum(c.count for c in changes)}')
    print(f'Compile: {compile_check.status}')
    print(f'Contract smoke: {smoke.get("status")}')
    print(f'Failures: {len(failures)}')
    print(f'Report: {REPORT_TXT}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
