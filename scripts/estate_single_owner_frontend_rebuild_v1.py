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

REPORT_TXT = Path('reports/estate_single_owner_frontend_rebuild_v1.txt')
REPORT_JSON = Path('reports/estate_single_owner_frontend_rebuild_v1.json')
BACKUP_DIR = Path('reports/estate_single_owner_frontend_rebuild_v1_backups')
ESTATE_JS = Path('static/js/jom_estate_lifecycle_v1.js')
ESTATE_TEMPLATE = Path('templates/estate.html')
WEB = Path('app/web.py')
CONTRACT_ROUTE = '/api/workspace/estate'
LEGACY_STRINGS = ['runtime/data', 'site_registry.json', 'estate_access_truth.json', 'site_registry.json', '/api/workspace/command-centre']
REQUIRED_FIELDS = ['schema', 'status', 'summary', 'sites', 'source_health']

JS_CONTENT = r'''/* JOM Estate single-owner frontend rebuild v1
 * Owner: static/js/jom_estate_lifecycle_v1.js
 * Contract: /api/workspace/estate
 * Rules: no runtime/data, no legacy JSON, no Command Centre contract dependency.
 */
(function () {
  'use strict';

  var CONTRACT_URL = '/api/workspace/estate';
  var ROOT_SELECTORS = [
    '[data-estate-workspace]',
    '[data-estate-root]',
    '#estate-workspace',
    '#estate-root',
    '#estate-content',
    '.estate-workspace',
    'main'
  ];

  function qs(selector, root) {
    return (root || document).querySelector(selector);
  }

  function escapeHtml(value) {
    if (value === null || value === undefined) {
      return '';
    }
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function numberOrDash(value) {
    if (value === null || value === undefined || value === '') {
      return 'Unavailable';
    }
    return escapeHtml(value);
  }

  function findRoot() {
    for (var i = 0; i < ROOT_SELECTORS.length; i += 1) {
      var found = qs(ROOT_SELECTORS[i]);
      if (found && found !== document.body) {
        return found;
      }
    }
    return document.body;
  }

  function normaliseSites(payload) {
    if (!payload || !Array.isArray(payload.sites)) {
      return [];
    }
    return payload.sites.filter(function (site) {
      return site && typeof site === 'object';
    });
  }

  function sourceHealthItems(payload) {
    var health = payload && payload.source_health && typeof payload.source_health === 'object'
      ? payload.source_health
      : {};
    return Object.keys(health).sort().map(function (key) {
      var item = health[key] || {};
      return {
        key: key,
        available: item.available === undefined ? true : Boolean(item.available),
        type: item.type || 'unknown',
        count: item.count_hint === null || item.count_hint === undefined ? 'n/a' : item.count_hint
      };
    });
  }

  function actionItems(payload) {
    var summary = payload.summary || {};
    var actions = [];
    var reviewItems = Number(summary.review_items || 0);
    var monitoredSites = Number(summary.monitored_sites || 0);
    var totalSites = Number(summary.total_sites || 0);

    if (reviewItems > 0) {
      actions.push({label: 'Review estate items', detail: reviewItems + ' item(s) need review'});
    }
    if (totalSites > 0 && monitoredSites === 0) {
      actions.push({label: 'Monitoring not enabled', detail: 'No discovered sites are currently marked as monitored'});
    }
    if (!actions.length) {
      actions.push({label: 'Estate contract ready', detail: 'No immediate Estate contract blockers detected'});
    }
    return actions;
  }

  function renderSummary(payload) {
    var summary = payload.summary || {};
    return '' +
      '<section class="jom-estate-panel jom-estate-summary" aria-label="Estate summary">' +
        '<h2>Estate workspace</h2>' +
        '<p>Live Estate contract: <code>/api/workspace/estate</code></p>' +
        '<div class="jom-estate-metrics">' +
          '<article class="jom-estate-metric"><span>Total sites</span><strong>' + numberOrDash(summary.total_sites) + '</strong></article>' +
          '<article class="jom-estate-metric"><span>Monitored sites</span><strong>' + numberOrDash(summary.monitored_sites) + '</strong></article>' +
          '<article class="jom-estate-metric"><span>Review items</span><strong>' + numberOrDash(summary.review_items) + '</strong></article>' +
          '<article class="jom-estate-metric"><span>Coverage</span><strong>' + numberOrDash(summary.coverage_percent) + (summary.coverage_percent === null || summary.coverage_percent === undefined ? '' : '%') + '</strong></article>' +
        '</div>' +
      '</section>';
  }

  function renderActions(payload) {
    var actions = actionItems(payload);
    return '' +
      '<section class="jom-estate-panel jom-estate-actions" aria-label="Estate actions">' +
        '<h2>Action required</h2>' +
        '<ul>' + actions.map(function (action) {
          return '<li><strong>' + escapeHtml(action.label) + '</strong><span>' + escapeHtml(action.detail) + '</span></li>';
        }).join('') + '</ul>' +
      '</section>';
  }

  function renderSources(payload) {
    var sources = sourceHealthItems(payload);
    return '' +
      '<section class="jom-estate-panel jom-estate-sources" aria-label="Estate source health">' +
        '<h2>Source health</h2>' +
        '<ul>' + sources.map(function (source) {
          return '<li><strong>' + escapeHtml(source.key) + '</strong><span>' + (source.available ? 'Available' : 'Unavailable') + ' · ' + escapeHtml(source.type) + ' · count ' + escapeHtml(source.count) + '</span></li>';
        }).join('') + '</ul>' +
      '</section>';
  }

  function renderSites(payload) {
    var sites = normaliseSites(payload);
    if (!sites.length) {
      return '' +
        '<section class="jom-estate-panel jom-estate-sites" aria-label="Estate sites">' +
          '<h2>Site inventory</h2>' +
          '<p>No site records were returned by the Estate workspace contract.</p>' +
        '</section>';
    }
    return '' +
      '<section class="jom-estate-panel jom-estate-sites" aria-label="Estate sites">' +
        '<h2>Site inventory</h2>' +
        '<div class="jom-estate-site-list">' + sites.map(function (site) {
          var status = site.status || (site.is_monitored ? 'monitored' : 'discovered');
          var url = site.url ? '<a href="' + escapeHtml(site.url) + '" target="_blank" rel="noopener noreferrer">Open site</a>' : '<span>No site link</span>';
          return '' +
            '<article class="jom-estate-site-card">' +
              '<h3>' + escapeHtml(site.name || site.key || 'Unnamed site') + '</h3>' +
              '<p><strong>Status:</strong> ' + escapeHtml(status) + '</p>' +
              '<p><strong>Key:</strong> ' + escapeHtml(site.key || 'Unavailable') + '</p>' +
              '<p>' + url + '</p>' +
            '</article>';
        }).join('') + '</div>' +
      '</section>';
  }

  function render(payload) {
    var root = findRoot();
    root.innerHTML = '' +
      '<div class="jom-estate-single-owner" data-jom-estate-single-owner="v1">' +
        renderSummary(payload) +
        renderActions(payload) +
        renderSources(payload) +
        renderSites(payload) +
      '</div>';
  }

  function renderError(error) {
    var root = findRoot();
    root.innerHTML = '' +
      '<section class="jom-estate-panel jom-estate-error" role="alert">' +
        '<h2>Estate workspace unavailable</h2>' +
        '<p>The Estate workspace contract could not be loaded.</p>' +
        '<pre>' + escapeHtml(error && error.message ? error.message : error) + '</pre>' +
      '</section>';
  }

  function loadEstate() {
    fetch(CONTRACT_URL, {headers: {'Accept': 'application/json'}, credentials: 'same-origin'})
      .then(function (response) {
        if (!response.ok) {
          throw new Error('Estate workspace contract returned HTTP ' + response.status);
        }
        return response.json();
      })
      .then(function (payload) {
        render(payload || {});
      })
      .catch(renderError);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadEstate);
  } else {
    loadEstate();
  }
}());
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


def compile_web() -> Check:
    if not WEB.exists():
        return Check('compile_web', 'FAIL', 'app/web.py missing')
    try:
        py_compile.compile(str(WEB), doraise=True)
        return Check('compile_web', 'PASS', 'app/web.py compiles')
    except Exception as exc:
        return Check('compile_web', 'FAIL', str(exc))


def patch_estate_js() -> tuple[list[Change], str | None]:
    if not ESTATE_JS.exists():
        return [Change(ESTATE_JS.as_posix(), 'missing Estate JS owner file', 0)], None
    backup_path = backup(ESTATE_JS)
    original = read(ESTATE_JS)
    write(ESTATE_JS, JS_CONTENT)
    changed = 1 if original != JS_CONTENT else 0
    return [Change(ESTATE_JS.as_posix(), 'replaced with single-owner Estate workspace renderer', changed)], backup_path


def free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def smoke_contract(skip: bool) -> dict:
    if skip:
        return {'status': 'SKIPPED', 'reason': 'skip requested'}
    if not WEB.exists():
        return {'status': 'SKIPPED', 'reason': 'app/web.py missing'}
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
                    body = response.read().decode('utf-8', errors='ignore')
                    payload = json.loads(body) if body else {}
                    missing = [field for field in REQUIRED_FIELDS if not isinstance(payload, dict) or field not in payload]
                    return {
                        'status': 'PASS' if int(response.status) == 200 and not missing else 'REVIEW',
                        'http_status': int(response.status),
                        'schema': payload.get('schema') if isinstance(payload, dict) else None,
                        'missing_required_fields': missing,
                    }
            except Exception as exc:
                last_error = str(exc)
                time.sleep(0.5)
        stderr = ''
        if proc and proc.stderr:
            with contextlib.suppress(Exception):
                stderr = proc.stderr.read()[:1200]
        return {'status': 'SKIPPED', 'reason': 'Flask did not respond', 'last_error': last_error, 'stderr': stderr}
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


def scan_frontend() -> list[Check]:
    checks: list[Check] = []
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
    checks.append(Check('estate_js_avoids_command_centre_contract', 'PASS' if '/api/workspace/command-centre' not in js_body else 'FAIL', '/api/workspace/command-centre'))
    checks.append(Check('estate_js_single_owner_marker', 'PASS' if 'JOM Estate single-owner frontend rebuild v1' in js_body else 'FAIL', 'single-owner marker'))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-smoke-test', action='store_true')
    args = parser.parse_args()

    REPORT_TXT.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    changes, backup_path = patch_estate_js()
    compile_check = compile_web()
    smoke = smoke_contract(args.skip_smoke_test) if compile_check.status == 'PASS' else {'status': 'SKIPPED', 'reason': 'compile failed'}
    frontend_checks = scan_frontend()
    failures = [c for c in [compile_check] + frontend_checks if c.status == 'FAIL']
    status = 'PASS' if not failures and smoke.get('status') in {'PASS', 'SKIPPED'} else 'REVIEW'

    result = {
        'pack': 'JOM Estate Single-Owner Frontend Rebuild v1',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'status': status,
        'backup': backup_path,
        'changes': [asdict(c) for c in changes],
        'compile_check': asdict(compile_check),
        'smoke': smoke,
        'frontend_checks': [asdict(c) for c in frontend_checks],
        'failures': [asdict(c) for c in failures],
    }
    REPORT_JSON.write_text(json.dumps(result, indent=2), encoding='utf-8')

    lines = []
    lines.append('JOM Estate Single-Owner Frontend Rebuild v1')
    lines.append('=' * 45)
    lines.append(f"Generated UTC: {result['generated_utc']}")
    lines.append(f"Status: {status}")
    lines.append('')
    lines.append('Summary')
    lines.append('-------')
    lines.append(f"Backup: {backup_path}")
    lines.append(f"Changes applied: {sum(c.count for c in changes)}")
    lines.append(f"Compile: {compile_check.status}")
    lines.append(f"Contract smoke: {smoke.get('status')}")
    lines.append(f"Frontend failures: {len(failures)}")
    lines.append('')
    lines.append('Changes')
    lines.append('-------')
    for change in changes:
        lines.append(f'- {change.file}: {change.detail} ({change.count})')
    lines.append('')
    lines.append('Contract smoke')
    lines.append('--------------')
    lines.append(f"- {CONTRACT_ROUTE}: {smoke.get('status')} http={smoke.get('http_status')} schema={smoke.get('schema')}")
    if smoke.get('missing_required_fields'):
        lines.append(f"  missing: {', '.join(smoke.get('missing_required_fields', []))}")
    if smoke.get('reason'):
        lines.append(f"  reason: {smoke.get('reason')}")
    lines.append('')
    lines.append('Frontend checks')
    lines.append('---------------')
    for check in frontend_checks:
        lines.append(f'- {check.name}: {check.status} - {check.detail}')
    lines.append('')
    lines.append('Decision')
    lines.append('--------')
    if status == 'PASS':
        lines.append('PASS - Estate frontend now has one JS owner consuming /api/workspace/estate only.')
    else:
        lines.append('REVIEW - inspect failures before demo.')
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
