#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

REPORT_TXT = Path('reports/estate_single_owner_audit_v1.txt')
REPORT_JSON = Path('reports/estate_single_owner_audit_v1.json')

TEXT_EXT = {'.py', '.js', '.html', '.htm', '.css', '.json', '.md', '.txt', '.ps1'}
SKIP_PARTS = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache', 'node_modules', 'reports', 'cleanup_archive', 'archive', 'archives'}

ESTATE_TEMPLATE_CANDIDATES = [Path('templates/estate.html'), Path('templates/estate/index.html')]
JS_SEARCH_ROOTS = [Path('static/js')]
CSS_SEARCH_ROOTS = [Path('static/css')]
BACKEND_SEARCH_ROOTS = [Path('app'), Path('backend'), Path('scripts')]
COMMAND_CENTRE_HINTS = ['command-centre', 'command_centre', 'cmdc', 'workspace/command-centre']
ESTATE_HINTS = ['estate', 'site_lifecycle', 'lifecycle', 'discovery-authority', 'site-review', 'site_registry']
LEGACY_JSON_NAMES = ['monitored_sites.json', 'site_access_validation.json', 'site_lifecycle_decisions.json']

FETCH_RX = re.compile(r"fetch\s*\(\s*['\"]([^'\"]+)", re.I)
API_RX = re.compile(r"['\"]((?:/api/|/runtime/|/workspace/)[^'\"]+)['\"]")
FUNC_RX = re.compile(r"\bfunction\s+([A-Za-z0-9_$]+)\s*\(|\b(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\(?[^=]*?=>", re.I)
RENDER_RX = re.compile(r"\b(render[A-Za-z0-9_$]*|paint[A-Za-z0-9_$]*|hydrate[A-Za-z0-9_$]*|mount[A-Za-z0-9_$]*|update[A-Za-z0-9_$]*)\b")
SCRIPT_SRC_RX = re.compile(r"<script[^>]+src=['\"]([^'\"]+)['\"]", re.I)
LINK_CSS_RX = re.compile(r"<link[^>]+href=['\"]([^'\"]+\.css[^'\"]*)['\"]", re.I)
ROUTE_RX = re.compile(r"@app\.route\(['\"]([^'\"]*estate[^'\"]*)['\"]", re.I)

@dataclass
class Finding:
    file: str
    line: int
    label: str
    text: str

@dataclass
class Asset:
    file: str
    reason: str


def skip(path: Path) -> bool:
    return bool(set(path.parts).intersection(SKIP_PARTS))


def read(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return ''


def iter_files(roots: Iterable[Path]) -> Iterable[Path]:
    seen = set()
    for root in roots:
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else [p for p in root.rglob('*') if p.is_file()]
        for p in candidates:
            if p in seen or skip(p):
                continue
            if p.suffix.lower() in TEXT_EXT:
                seen.add(p)
                yield p


def rel(path: Path) -> str:
    return path.as_posix()


def line_findings(path: Path, label: str, rx: re.Pattern) -> list[Finding]:
    out = []
    for i, line in enumerate(read(path).splitlines(), 1):
        if rx.search(line):
            out.append(Finding(rel(path), i, label, line.strip()[:260]))
    return out


def estate_js_files() -> list[Path]:
    files = []
    for p in iter_files(JS_SEARCH_ROOTS):
        name = p.name.lower()
        body = read(p).lower()
        if 'estate' in name or any(h in body for h in ESTATE_HINTS):
            files.append(p)
    return sorted(files)


def estate_css_files() -> list[Path]:
    files = []
    for p in iter_files(CSS_SEARCH_ROOTS):
        name = p.name.lower()
        body = read(p).lower()
        if 'estate' in name or any(h in body for h in ['estate', 'site-card', 'lifecycle', 'coverage']):
            files.append(p)
    return sorted(files)


def backend_estate_files() -> list[Path]:
    files = []
    for p in iter_files(BACKEND_SEARCH_ROOTS):
        body = read(p).lower()
        if any(h in body for h in ESTATE_HINTS):
            files.append(p)
    return sorted(files)


def collect_template_assets() -> dict:
    templates = [p for p in ESTATE_TEMPLATE_CANDIDATES if p.exists()]
    scripts = []
    css = []
    for t in templates:
        body = read(t)
        scripts += [{'template': rel(t), 'src': m.group(1)} for m in SCRIPT_SRC_RX.finditer(body)]
        css += [{'template': rel(t), 'href': m.group(1)} for m in LINK_CSS_RX.finditer(body)]
    return {'templates': [rel(t) for t in templates], 'script_refs': scripts, 'css_refs': css}


def collect_fetches(paths: list[Path]) -> list[Finding]:
    out = []
    for p in paths:
        for i, line in enumerate(read(p).splitlines(), 1):
            for m in FETCH_RX.finditer(line):
                out.append(Finding(rel(p), i, 'fetch', m.group(1)))
            for m in API_RX.finditer(line):
                out.append(Finding(rel(p), i, 'api_literal', m.group(1)))
    return out


def collect_render_functions(paths: list[Path]) -> list[Finding]:
    out = []
    for p in paths:
        for i, line in enumerate(read(p).splitlines(), 1):
            if RENDER_RX.search(line) or FUNC_RX.search(line):
                txt = line.strip()
                if any(word in txt.lower() for word in ['render', 'paint', 'hydrate', 'mount', 'update', 'estate', 'site', 'lifecycle']):
                    out.append(Finding(rel(p), i, 'render_or_owner_function', txt[:260]))
    return out


def collect_backend_routes(paths: list[Path]) -> list[Finding]:
    out = []
    for p in paths:
        for i, line in enumerate(read(p).splitlines(), 1):
            m = ROUTE_RX.search(line)
            if m:
                out.append(Finding(rel(p), i, 'estate_route', m.group(1)))
    return out


def collect_legacy_refs(paths: list[Path]) -> list[Finding]:
    out = []
    for p in paths:
        for i, line in enumerate(read(p).splitlines(), 1):
            for name in LEGACY_JSON_NAMES:
                if name in line:
                    out.append(Finding(rel(p), i, name, line.strip()[:260]))
    return out


def collect_command_centre_duplication() -> list[Finding]:
    out = []
    paths = list(iter_files([Path('static/js'), Path('templates'), Path('app')]))
    for p in paths:
        body_lower = read(p).lower()
        if any(h in body_lower for h in COMMAND_CENTRE_HINTS) and any(h in body_lower for h in ['estate', 'site', 'coverage', 'lifecycle', 'review']):
            for i, line in enumerate(read(p).splitlines(), 1):
                low = line.lower()
                if any(h in low for h in COMMAND_CENTRE_HINTS) or any(h in low for h in ['estate', 'coverage', 'lifecycle', 'review']):
                    out.append(Finding(rel(p), i, 'command_centre_estate_overlap_signal', line.strip()[:260]))
                    if len(out) >= 200:
                        return out
    return out


def detect_duplicate_fetches(fetches: list[Finding]) -> dict:
    by_endpoint = {}
    for f in fetches:
        endpoint = f.text.split('?')[0]
        by_endpoint.setdefault(endpoint, []).append(asdict(f))
    return {k: v for k, v in sorted(by_endpoint.items()) if len({x['file'] for x in v}) > 1 or len(v) > 1}


def detect_owner_risk(js_files: list[Path], render_functions: list[Finding], fetches: list[Finding]) -> dict:
    estate_named = [rel(p) for p in js_files if 'estate' in p.name.lower()]
    active_files = sorted(set([f.file for f in render_functions] + [f.file for f in fetches]))
    return {
        'estate_named_js_files': estate_named,
        'active_estate_js_files': active_files,
        'risk': 'HIGH' if len(active_files) > 1 else ('LOW' if len(active_files) == 1 else 'UNKNOWN'),
        'expected_single_owner': active_files[0] if len(active_files) == 1 else None,
    }


def orphan_estate_assets(js_files: list[Path], css_files: list[Path], template_assets: dict) -> list[Asset]:
    script_refs = ' '.join(x['src'] for x in template_assets['script_refs']).lower()
    css_refs = ' '.join(x['href'] for x in template_assets['css_refs']).lower()
    out = []
    for p in js_files:
        if p.name.lower() not in script_refs and rel(p).lower() not in script_refs:
            out.append(Asset(rel(p), 'estate-related JS not directly referenced by estate template script tags'))
    for p in css_files:
        if p.name.lower() not in css_refs and rel(p).lower() not in css_refs:
            out.append(Asset(rel(p), 'estate-related CSS not directly referenced by estate template link tags'))
    return out


def main() -> int:
    REPORT_TXT.parent.mkdir(parents=True, exist_ok=True)

    template_assets = collect_template_assets()
    js_files = estate_js_files()
    css_files = estate_css_files()
    backend_files = backend_estate_files()
    target_files = js_files + [Path(p) for p in template_assets['templates']] + backend_files

    fetches = collect_fetches(js_files + [Path(p) for p in template_assets['templates']])
    render_functions = collect_render_functions(js_files)
    backend_routes = collect_backend_routes(backend_files)
    legacy_refs = collect_legacy_refs(target_files)
    duplicate_fetches = detect_duplicate_fetches(fetches)
    owner_risk = detect_owner_risk(js_files, render_functions, fetches)
    duplication = collect_command_centre_duplication()
    orphan_assets = orphan_estate_assets(js_files, css_files, template_assets)

    recommendations = []
    if owner_risk['risk'] == 'HIGH':
        recommendations.append('Consolidate Estate rendering and fetch ownership into one JS owner before rebuild.')
    if duplicate_fetches:
        recommendations.append('Remove duplicate fetch paths or centralise them behind one Estate workspace/contract loader.')
    if legacy_refs:
        recommendations.append('Resolve remaining legacy Estate JSON filename consumers before treating Estate as live-contract clean.')
    if orphan_assets:
        recommendations.append('Remove or reconnect orphan Estate assets during rebuild planning.')
    if not recommendations:
        recommendations.append('Estate appears ready for single-owner rebuild planning.')

    status = 'REVIEW'
    if owner_risk['risk'] == 'LOW' and not duplicate_fetches and not legacy_refs:
        status = 'PASS'

    result = {
        'audit': 'JOM Estate Single-Owner Audit v1',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'status': status,
        'template_assets': template_assets,
        'estate_js_files': [rel(p) for p in js_files],
        'estate_css_files': [rel(p) for p in css_files],
        'backend_estate_files': [rel(p) for p in backend_files],
        'owner_risk': owner_risk,
        'fetches': [asdict(f) for f in fetches],
        'duplicate_fetches': duplicate_fetches,
        'render_functions': [asdict(f) for f in render_functions],
        'backend_routes': [asdict(f) for f in backend_routes],
        'legacy_refs': [asdict(f) for f in legacy_refs],
        'command_centre_estate_overlap_signals': [asdict(f) for f in duplication],
        'orphan_estate_assets': [asdict(a) for a in orphan_assets],
        'recommendations': recommendations,
    }
    REPORT_JSON.write_text(json.dumps(result, indent=2), encoding='utf-8')

    lines = []
    lines.append('JOM Estate Single-Owner Audit v1')
    lines.append('=' * 37)
    lines.append(f"Generated UTC: {result['generated_utc']}")
    lines.append(f"Status: {status}")
    lines.append('')
    lines.append('Summary')
    lines.append('-------')
    lines.append(f"Estate templates found: {len(template_assets['templates'])}")
    lines.append(f"Estate JS files found: {len(js_files)}")
    lines.append(f"Estate CSS files found: {len(css_files)}")
    lines.append(f"Backend Estate files found: {len(backend_files)}")
    lines.append(f"Owner risk: {owner_risk['risk']}")
    lines.append(f"Fetch/API references: {len(fetches)}")
    lines.append(f"Duplicate fetch endpoints: {len(duplicate_fetches)}")
    lines.append(f"Render/owner function signals: {len(render_functions)}")
    lines.append(f"Estate backend routes: {len(backend_routes)}")
    lines.append(f"Legacy JSON refs: {len(legacy_refs)}")
    lines.append(f"Command Centre/Estate overlap signals: {len(duplication)}")
    lines.append(f"Orphan estate assets: {len(orphan_assets)}")
    lines.append('')
    lines.append('Template assets')
    lines.append('---------------')
    for t in template_assets['templates']:
        lines.append(f'- template: {t}')
    for s in template_assets['script_refs']:
        lines.append(f"- script: {s['template']} -> {s['src']}")
    for c in template_assets['css_refs']:
        lines.append(f"- css: {c['template']} -> {c['href']}")
    lines.append('')
    lines.append('Estate JS owner candidates')
    lines.append('--------------------------')
    for f in owner_risk['active_estate_js_files']:
        lines.append(f'- {f}')
    if not owner_risk['active_estate_js_files']:
        lines.append('none detected')
    lines.append('')
    lines.append('Duplicate fetch/API endpoints')
    lines.append('-----------------------------')
    if duplicate_fetches:
        for endpoint, refs in duplicate_fetches.items():
            lines.append(f'- {endpoint}: {len(refs)} references')
            for ref in refs[:8]:
                lines.append(f"  - {ref['file']}:{ref['line']} {ref['label']}")
    else:
        lines.append('none detected')
    lines.append('')
    lines.append('Legacy JSON references')
    lines.append('----------------------')
    if legacy_refs:
        for f in legacy_refs[:120]:
            lines.append(f'- {f.file}:{f.line} [{f.label}] {f.text}')
        if len(legacy_refs) > 120:
            lines.append(f'... {len(legacy_refs)-120} more in JSON')
    else:
        lines.append('none detected')
    lines.append('')
    lines.append('Orphan estate assets')
    lines.append('--------------------')
    if orphan_assets:
        for a in orphan_assets[:120]:
            lines.append(f'- {a.file}: {a.reason}')
    else:
        lines.append('none detected')
    lines.append('')
    lines.append('Recommended single-owner blueprint')
    lines.append('----------------------------------')
    lines.append('- One Estate template owner: templates/estate.html')
    if owner_risk['expected_single_owner']:
        lines.append(f"- Current likely JS owner: {owner_risk['expected_single_owner']}")
    else:
        lines.append('- Choose one JS owner and remove/decommission competing Estate renderers.')
    lines.append('- One Estate contract loader for all /api/estate, /runtime, and workspace fetches.')
    lines.append('- Keep Command Centre as summary/action entry point only; keep Estate as drilldown/inventory page.')
    lines.append('- Do not rebuild until duplicate fetches, orphan assets, and legacy refs are reviewed.')
    lines.append('')
    lines.append('Recommendations')
    lines.append('---------------')
    for r in recommendations:
        lines.append(f'- {r}')

    REPORT_TXT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(lines[0])
    print(f'Status: {status}')
    print(f"Estate JS files: {len(js_files)}")
    print(f"Duplicate fetch endpoints: {len(duplicate_fetches)}")
    print(f"Legacy JSON refs: {len(legacy_refs)}")
    print(f'Report: {REPORT_TXT}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
