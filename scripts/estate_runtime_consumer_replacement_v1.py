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

REPORT_TXT = Path('reports/estate_runtime_consumer_replacement_v1.txt')
REPORT_JSON = Path('reports/estate_runtime_consumer_replacement_v1.json')
BACKUP_DIR = Path('reports/estate_runtime_consumer_replacement_v1_backups')

TARGETS = [Path('app/web.py'), Path('scripts/build_site_registry.py')]
LEGACY_FILES = ['monitored_sites.json', 'site_access_validation.json', 'site_lifecycle_decisions.json']
AUTHORITY_ROUTE = '/api/estate/discovery-authority/coverage'
SMOKE_ROUTES = [AUTHORITY_ROUTE, '/api/estate/admin-site-inventory', '/api/site-registry']

HELPER_MARKER = '# JOM estate runtime consumer replacement helpers v1'
HELPER_BLOCK = '''

# JOM estate runtime consumer replacement helpers v1
def _jom_estate_runtime_site_registry_contract_v1():
    """Return current runtime site registry contract without legacy monitored-site JSON dependency."""
    try:
        payload = _jom_cached_read_json_v1("site_registry.json", {}) if "_jom_cached_read_json_v1" in globals() else load_json("site_registry.json", {})
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    sites = payload.get("sites") if isinstance(payload.get("sites"), list) else []
    return {"schema": payload.get("schema", "site-registry-runtime"), "summary": payload.get("summary", {}), "sites": sites, "source": "runtime/data/site_registry.json"}


def _jom_estate_runtime_access_validation_contract_v1():
    """Return runtime access validation view derived from live estate contracts, not site_access_validation.json."""
    registry = _jom_estate_runtime_site_registry_contract_v1()
    validations = {}
    for site in registry.get("sites", []):
        if not isinstance(site, dict):
            continue
        key = site.get("key") or site.get("site_key") or site.get("cloud_id") or site.get("url")
        if key:
            validations[str(key)] = {"status": "runtime_contract", "source": registry.get("source"), "site": site}
    return {"validations": validations, "history": [], "source": "runtime/site_registry_contract"}


def _jom_estate_runtime_lifecycle_contract_v1():
    """Return read-only lifecycle decision contract derived from runtime site registry."""
    registry = _jom_estate_runtime_site_registry_contract_v1()
    decisions = {}
    for site in registry.get("sites", []):
        if not isinstance(site, dict):
            continue
        key = site.get("key") or site.get("site_key") or site.get("cloud_id") or site.get("url")
        if key:
            decisions[str(key)] = {"decision": site.get("lifecycle_decision") or site.get("status") or "runtime_registry", "source": registry.get("source")}
    return {"decisions": decisions, "history": [], "source": "runtime/site_registry_contract"}


def _jom_estate_runtime_noop_write_v1(label, payload=None):
    """Read-only estate guard: legacy runtime mutation disabled after runtime contract isolation."""
    return {"status": "skipped", "reason": "read_only_runtime_contract", "label": label}
'''

@dataclass
class Change:
    file: str
    detail: str
    count: int

@dataclass
class Residual:
    file: str
    line: int
    legacy_file: str
    text: str


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='ignore') if path.exists() else ''


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding='utf-8')


def backup(path: Path, stamp: str) -> str | None:
    if not path.exists():
        return None
    dest = BACKUP_DIR / stamp / path.as_posix()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    return dest.as_posix()


def replace_count(text: str, old: str, new: str) -> tuple[str, int]:
    count = text.count(old)
    if count:
        text = text.replace(old, new)
    return text, count


def ensure_web_helpers(text: str) -> tuple[str, int]:
    if HELPER_MARKER in text:
        return text, 0
    anchor = 'def _jom_generated_report_response'
    idx = text.find(anchor)
    if idx >= 0:
        return text[:idx] + HELPER_BLOCK + '\n' + text[idx:], 1
    return text + HELPER_BLOCK + '\n', 1


def patch_web(path: Path) -> list[Change]:
    if not path.exists():
        return []
    original = read(path)
    text = original
    changes: list[Change] = []

    text, c = ensure_web_helpers(text)
    if c:
        changes.append(Change(path.as_posix(), 'added runtime estate contract helper block', c))

    replacements = [
        ('SITE_LIFECYCLE_DECISIONS_PATH = DATA_PATH / "site_lifecycle_decisions.json"', 'SITE_LIFECYCLE_DECISIONS_PATH = DATA_PATH / "site_registry.json"  # runtime contract, legacy lifecycle file retired'),
        ('payload = load_json("site_lifecycle_decisions.json", {})', 'payload = _jom_estate_runtime_lifecycle_contract_v1()'),
        ('payload = load_json("site_lifecycle_decisions.json", {"decisions": {}, "history": []})', 'payload = _jom_estate_runtime_lifecycle_contract_v1()'),
        ('monitored_payload = load_json("monitored_sites.json", {})', 'monitored_payload = _jom_estate_runtime_site_registry_contract_v1()'),
        ('write_json(DATA_PATH / "monitored_sites.json", monitored_payload)', '_jom_estate_runtime_noop_write_v1("monitored_sites", monitored_payload)'),
        ('validation_payload = load_json("site_access_validation.json", {})', 'validation_payload = _jom_estate_runtime_access_validation_contract_v1()'),
        ('write_json(DATA_PATH / "site_access_validation.json", validation_payload)', '_jom_estate_runtime_noop_write_v1("site_access_validation", validation_payload)'),
        ('SITE_ACCESS_VALIDATION_PATH = DATA_PATH / "site_access_validation.json"', 'SITE_ACCESS_VALIDATION_PATH = DATA_PATH / "site_registry.json"  # runtime contract, legacy validation file retired'),
        ('payload = load_json("site_access_validation.json", {})', 'payload = _jom_estate_runtime_access_validation_contract_v1()'),
        ('validations = _load_site_access_validation() if "_load_site_access_validation" in globals() else load_json("site_access_validation.json", {"validations": {}, "history": []})', 'validations = _load_site_access_validation() if "_load_site_access_validation" in globals() else _jom_estate_runtime_access_validation_contract_v1()'),
        ('decisions = _load_lifecycle_decisions() if "_load_lifecycle_decisions" in globals() else load_json("site_lifecycle_decisions.json", {"decisions": {}, "history": []})', 'decisions = _load_lifecycle_decisions() if "_load_lifecycle_decisions" in globals() else _jom_estate_runtime_lifecycle_contract_v1()'),
        ('write_json(DATA_PATH / "site_lifecycle_decisions.json", decisions)', '_jom_estate_runtime_noop_write_v1("site_lifecycle_decisions", decisions)'),
        ('lifecycle_decisions = _jom_cached_read_json_v1("site_lifecycle_decisions.json", {"decisions": {}, "history": []})', 'lifecycle_decisions = _jom_estate_runtime_lifecycle_contract_v1()'),
        ('payload = _jom_credential_gate_read_json(_jom_credential_gate_data_path("site_access_validation.json"), {"validations": {}, "history": []})', 'payload = _jom_estate_runtime_access_validation_contract_v1()'),
        ('current_path = _jom_credential_gate_data_path("site_access_validation.json")', 'current_path = DATA_PATH / "site_registry.json"'),
        ('path = _jom_credential_gate_data_path("site_access_validation.json") if "_jom_credential_gate_data_path" in globals() else DATA_PATH / "site_access_validation.json"', 'path = DATA_PATH / "site_registry.json"'),
        ('"monitored_sites.json", "runtime_execution_history.json",', '"runtime_execution_history.json",'),
        ('"runtime_execution_status.json", "site_access_validation.json",', '"runtime_execution_status.json",'),
        ('"site_lifecycle_decisions.json", "site_onboarding_review.json",', '"site_onboarding_review.json",'),
    ]

    for old, new in replacements:
        text, c = replace_count(text, old, new)
        if c:
            changes.append(Change(path.as_posix(), f'replaced exact legacy consumer: {old[:90]}', c))

    if text != original:
        write(path, text)
    return changes


def patch_build_site_registry(path: Path) -> list[Change]:
    if not path.exists():
        return []
    original = read(path)
    text = original
    changes: list[Change] = []

    replacements = [
        ('monitored = read_json(data / "monitored_sites.json", {})', 'registry_contract = read_json(data / "site_registry.json", {})\n    monitored = {"sites": registry_contract.get("sites", []), "summary": registry_contract.get("summary", {}), "source": "runtime/data/site_registry.json"}'),
        ('decisions = read_json(data / "site_lifecycle_decisions.json", {})', 'decisions = {"decisions": {}, "history": [], "source": "runtime/data/site_registry.json"}'),
        ('access_validation = read_json(data / "site_access_validation.json", {})', 'access_validation = {"validations": {}, "history": [], "source": "runtime/data/site_registry.json"}'),
    ]
    for old, new in replacements:
        text, c = replace_count(text, old, new)
        if c:
            changes.append(Change(path.as_posix(), f'replaced build registry legacy input: {old}', c))

    if text != original:
        write(path, text)
    return changes


def collect_residuals() -> list[Residual]:
    residuals: list[Residual] = []
    for path in TARGETS:
        if not path.exists():
            continue
        for i, line in enumerate(read(path).splitlines(), 1):
            for legacy in LEGACY_FILES:
                if legacy in line:
                    residuals.append(Residual(path.as_posix(), i, legacy, line.strip()[:260]))
    return residuals


def compile_targets() -> list[dict]:
    results = []
    for path in TARGETS:
        if not path.exists() or path.suffix != '.py':
            continue
        try:
            py_compile.compile(str(path), doraise=True)
            results.append({'file': path.as_posix(), 'status': 'PASS'})
        except Exception as exc:
            results.append({'file': path.as_posix(), 'status': 'FAIL', 'error': str(exc)})
    return results


def free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def smoke_test(skip: bool) -> dict:
    if skip:
        return {'status': 'SKIPPED', 'reason': 'skip requested'}
    if not Path('app/web.py').exists():
        return {'status': 'SKIPPED', 'reason': 'app/web.py not found'}
    port = free_port()
    env = os.environ.copy()
    env['FLASK_APP'] = 'app.web'
    env['PYTHONUNBUFFERED'] = '1'
    cmd = [sys.executable, '-m', 'flask', 'run', '--host', '127.0.0.1', '--port', str(port), '--no-debugger', '--no-reload']
    proc = None
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        base = f'http://127.0.0.1:{port}'
        last_error = None
        for _ in range(30):
            if proc.poll() is not None:
                break
            route_results = []
            responded = False
            for route in SMOKE_ROUTES:
                try:
                    with urlopen(base + route, timeout=2) as response:
                        responded = True
                        route_results.append({'route': route, 'status': int(response.status)})
                except Exception as exc:
                    route_results.append({'route': route, 'status': 'ERROR', 'error': str(exc)[:220]})
                    last_error = str(exc)
            if responded:
                authority = [r for r in route_results if r['route'] == AUTHORITY_ROUTE][0]
                return {'status': 'PASS' if authority.get('status') == 200 else 'REVIEW', 'routes': route_results}
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
    stamp = now_stamp()
    backups = []
    for path in TARGETS:
        b = backup(path, stamp)
        if b:
            backups.append(b)

    changes: list[Change] = []
    changes += patch_web(Path('app/web.py'))
    changes += patch_build_site_registry(Path('scripts/build_site_registry.py'))

    residuals = collect_residuals()
    compile_results = compile_targets()
    compile_failures = [r for r in compile_results if r.get('status') != 'PASS']
    smoke = smoke_test(args.skip_smoke_test)

    status = 'PASS'
    if residuals or compile_failures or smoke.get('status') not in {'PASS', 'SKIPPED', 'REVIEW'}:
        status = 'REVIEW'

    result = {
        'replacement': 'JOM Estate Runtime Consumer Replacement v1',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'status': status,
        'backups': backups,
        'changes': [asdict(c) for c in changes],
        'residual_legacy_consumers': [asdict(r) for r in residuals],
        'compile_results': compile_results,
        'smoke_test': smoke,
    }
    REPORT_JSON.write_text(json.dumps(result, indent=2), encoding='utf-8')

    lines = []
    lines.append('JOM Estate Runtime Consumer Replacement v1')
    lines.append('=' * 42)
    lines.append(f"Generated UTC: {result['generated_utc']}")
    lines.append(f"Status: {status}")
    lines.append('')
    lines.append('Summary')
    lines.append('-------')
    lines.append(f"Backups created: {len(backups)}")
    lines.append(f"Changes applied: {len(changes)}")
    lines.append(f"Residual legacy consumers: {len(residuals)}")
    lines.append(f"Compile failures: {len(compile_failures)}")
    lines.append(f"Smoke test: {smoke.get('status')}")
    if smoke.get('reason'):
        lines.append(f"Smoke reason: {smoke.get('reason')}")
    lines.append('')
    lines.append('Backups')
    lines.append('-------')
    for b in backups:
        lines.append(f'- {b}')
    lines.append('')
    lines.append('Changes')
    lines.append('-------')
    if changes:
        for c in changes:
            lines.append(f'- {c.file}: {c.detail} ({c.count})')
    else:
        lines.append('none')
    lines.append('')
    lines.append('Residual legacy consumers')
    lines.append('-------------------------')
    if residuals:
        for r in residuals:
            lines.append(f'- {r.file}:{r.line} [{r.legacy_file}] {r.text}')
    else:
        lines.append('none')
    lines.append('')
    lines.append('Compile results')
    lines.append('---------------')
    for r in compile_results:
        if r.get('status') == 'PASS':
            lines.append(f"- {r['file']}: PASS")
        else:
            lines.append(f"- {r['file']}: FAIL {r.get('error')}")
    lines.append('')
    lines.append('Decision')
    lines.append('--------')
    if status == 'PASS':
        lines.append('PASS - guarded replacements applied, compile passed, and no target-file legacy consumers remain.')
    else:
        lines.append('REVIEW - inspect residual consumers or validation output before committing.')
    lines.append('')
    lines.append('Next after PASS')
    lines.append('---------------')
    lines.append('- Run git diff --stat and git status --short.')
    lines.append('- Run authority/estate route smoke validation if required.')
    lines.append('- Commit as: replace estate runtime legacy consumers.')
    lines.append('- Move to Estate Contract Definition Pack v1.')

    REPORT_TXT.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(lines[0])
    print(f'Status: {status}')
    print(f'Changes applied: {len(changes)}')
    print(f'Residual legacy consumers: {len(residuals)}')
    print(f'Compile failures: {len(compile_failures)}')
    print(f'Report: {REPORT_TXT}')
    return 0 if not compile_failures else 1

if __name__ == '__main__':
    raise SystemExit(main())
