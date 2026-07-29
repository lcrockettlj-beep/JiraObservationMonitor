#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

REPORT_TXT = Path('reports/estate_single_owner_consolidation_blueprint_v1.txt')
REPORT_JSON = Path('reports/estate_single_owner_consolidation_blueprint_v1.json')

TEXT_EXT = {'.py', '.js', '.html', '.css'}
SKIP_PARTS = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache', 'node_modules', 'reports', 'cleanup_archive', 'archive', 'archives'}

ESTATE_TEMPLATE = Path('templates/estate.html')
JS_ROOT = Path('static/js')
CSS_ROOT = Path('static/css')
BACKEND_ROOTS = [Path('app'), Path('backend'), Path('scripts')]

ESTATE_TERMS = ['estate', 'site-review', 'site_review', 'site lifecycle', 'site_lifecycle', 'lifecycle', 'discovery-authority', 'discovery_authority', 'site_workspace', 'site registry', 'site_registry']
COMMAND_TERMS = ['command-centre', 'command_centre', 'cmdc', 'workspace/command-centre']
LEGACY_JSONS = ['monitored_sites.json', 'site_access_validation.json', 'site_lifecycle_decisions.json']

FETCH_RX = re.compile(r"fetch\s*\(\s*['\"]([^'\"]+)", re.I)
API_RX = re.compile(r"['\"]((?:/api/|/runtime/|/workspace/)[^'\"]+)['\"]")
SCRIPT_SRC_RX = re.compile(r"<script[^>]+src=['\"]([^'\"]+)['\"]", re.I)
CSS_HREF_RX = re.compile(r"<link[^>]+href=['\"]([^'\"]+\.css[^'\"]*)['\"]", re.I)
ROUTE_RX = re.compile(r"@app\.route\(['\"]([^'\"]+)['\"]", re.I)
FUNCTION_RX = re.compile(r"\b(function\s+[A-Za-z0-9_$]+|(?:const|let|var)\s+[A-Za-z0-9_$]+\s*=|class\s+[A-Za-z0-9_$]+)", re.I)

@dataclass
class FileProfile:
    file: str
    kind: str
    referenced_by_estate_template: bool
    estate_score: int
    command_score: int
    fetches: list[str]
    routes: list[str]
    legacy_refs: list[str]
    render_signals: int
    decision: str
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


def estate_template_refs() -> dict:
    body = read(ESTATE_TEMPLATE)
    scripts = [m.group(1) for m in SCRIPT_SRC_RX.finditer(body)]
    css = [m.group(1) for m in CSS_HREF_RX.finditer(body)]
    return {'scripts': scripts, 'css': css, 'body': body}


def is_referenced_by_template(path: Path, refs: dict) -> bool:
    name = path.name.lower()
    path_text = rel(path).lower()
    joined = ' '.join(refs['scripts'] + refs['css']).lower()
    return name in joined or path_text in joined


def score_terms(text: str, terms: list[str]) -> int:
    lower = text.lower()
    return sum(lower.count(t) for t in terms)


def fetches_in(text: str) -> list[str]:
    vals = []
    for m in FETCH_RX.finditer(text):
        vals.append(m.group(1))
    for m in API_RX.finditer(text):
        vals.append(m.group(1))
    return sorted(set(vals))


def routes_in(text: str) -> list[str]:
    return sorted(set(m.group(1) for m in ROUTE_RX.finditer(text) if 'estate' in m.group(1).lower() or 'site' in m.group(1).lower()))


def legacy_refs_in(text: str) -> list[str]:
    return [name for name in LEGACY_JSONS if name in text]


def render_signal_count(text: str) -> int:
    low = text.lower()
    return sum(low.count(term) for term in ['render', 'paint', 'hydrate', 'mount', 'update', 'workspace', 'card', 'panel'])


def classify(path: Path, refs: dict) -> FileProfile | None:
    text = read(path)
    estate_score = score_terms(text + ' ' + path.name, ESTATE_TERMS)
    command_score = score_terms(text + ' ' + path.name, COMMAND_TERMS)
    fetch_vals = fetches_in(text)
    route_vals = routes_in(text)
    legacy_vals = legacy_refs_in(text)
    render_signals = render_signal_count(text)
    referenced = is_referenced_by_template(path, refs)

    kind = 'backend' if path.suffix == '.py' else ('js' if path.suffix == '.js' else ('css' if path.suffix == '.css' else 'template'))

    if path == ESTATE_TEMPLATE:
        return FileProfile(rel(path), kind, True, estate_score, command_score, fetch_vals, route_vals, legacy_vals, render_signals, 'KEEP', 'Estate page template owner')

    if estate_score <= 0 and not route_vals and not legacy_vals:
        return None

    decision = 'REVIEW'
    reason = 'Estate-related file needs manual classification'

    if kind == 'js':
        if path.name == 'jom_estate_lifecycle_v1.js':
            decision = 'KEEP_CANDIDATE'
            reason = 'Best current Estate JS owner candidate by filename and Estate lifecycle role'
        elif referenced:
            decision = 'MERGE_CANDIDATE'
            reason = 'Referenced by Estate template; inspect for merge into single owner'
        elif command_score > 0:
            decision = 'REWIRE_OR_REMOVE'
            reason = 'Command Centre overlap detected; Estate should not be owned by Command Centre JS'
        elif any('/api/site-review' in f or 'site-review' in f for f in fetch_vals):
            decision = 'MERGE_CANDIDATE'
            reason = 'Site review behaviour likely belongs inside single Estate owner'
        else:
            decision = 'REMOVE_CANDIDATE'
            reason = 'Estate-related JS not directly referenced by Estate template'
    elif kind == 'css':
        if path.name == 'jom_estate_lifecycle_v1.css':
            decision = 'KEEP_CANDIDATE'
            reason = 'Best current Estate CSS owner candidate by filename'
        elif referenced:
            decision = 'KEEP_OR_MERGE_CANDIDATE'
            reason = 'Referenced by Estate template'
        elif command_score > 0:
            decision = 'REWIRE_OR_REMOVE'
            reason = 'Command Centre CSS overlap detected'
        else:
            decision = 'REMOVE_CANDIDATE'
            reason = 'Estate-related CSS not directly referenced by Estate template'
    elif kind == 'backend':
        if route_vals:
            decision = 'REWIRE_CANDIDATE'
            reason = 'Backend Estate route/contract participant'
        elif legacy_vals:
            decision = 'REWIRE_CANDIDATE'
            reason = 'Legacy Estate JSON filename consumer remains'
        else:
            decision = 'REVIEW'
            reason = 'Backend Estate-related helper/script'

    return FileProfile(rel(path), kind, referenced, estate_score, command_score, fetch_vals, route_vals, legacy_vals, render_signals, decision, reason)


def group_profiles(profiles: list[FileProfile]) -> dict:
    groups = {'KEEP': [], 'MERGE': [], 'REMOVE': [], 'REWIRE': [], 'REVIEW': []}
    for p in profiles:
        d = p.decision
        if d in {'KEEP', 'KEEP_CANDIDATE', 'KEEP_OR_MERGE_CANDIDATE'}:
            groups['KEEP'].append(p)
        elif d == 'MERGE_CANDIDATE':
            groups['MERGE'].append(p)
        elif d == 'REMOVE_CANDIDATE':
            groups['REMOVE'].append(p)
        elif d in {'REWIRE_CANDIDATE', 'REWIRE_OR_REMOVE'}:
            groups['REWIRE'].append(p)
        else:
            groups['REVIEW'].append(p)
    return groups


def duplicate_endpoint_map(profiles: list[FileProfile]) -> dict:
    by_ep = {}
    for p in profiles:
        for ep in p.fetches:
            clean = ep.split('?')[0]
            by_ep.setdefault(clean, []).append(p.file)
    return {k: sorted(set(v)) for k, v in sorted(by_ep.items()) if len(set(v)) > 1}


def main() -> int:
    REPORT_TXT.parent.mkdir(parents=True, exist_ok=True)
    refs = estate_template_refs()
    paths = []
    if ESTATE_TEMPLATE.exists():
        paths.append(ESTATE_TEMPLATE)
    paths += list(iter_files([JS_ROOT, CSS_ROOT] + BACKEND_ROOTS))

    profiles = []
    for path in sorted(set(paths)):
        prof = classify(path, refs)
        if prof:
            profiles.append(prof)

    groups = group_profiles(profiles)
    duplicate_endpoints = duplicate_endpoint_map(profiles)
    legacy_profiles = [p for p in profiles if p.legacy_refs]
    command_overlap = [p for p in profiles if p.command_score > 0 and p.estate_score > 0]

    status = 'REVIEW'
    result = {
        'blueprint': 'JOM Estate Single-Owner Consolidation Blueprint v1',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'status': status,
        'template_script_refs': refs['scripts'],
        'template_css_refs': refs['css'],
        'counts': {k: len(v) for k, v in groups.items()},
        'duplicate_endpoints': duplicate_endpoints,
        'legacy_profiles': [asdict(p) for p in legacy_profiles],
        'command_overlap_profiles': [asdict(p) for p in command_overlap],
        'profiles': [asdict(p) for p in profiles],
        'groups': {k: [asdict(p) for p in v] for k, v in groups.items()},
        'recommended_execution_order': [
            'Confirm KEEP owner files',
            'Define Estate-only backend contract to replace Command Centre contract dependency',
            'Merge site review and access validation behaviours into Estate owner',
            'Remove/decommission duplicate JS/CSS owners after validation',
            'Run route smoke tests and frontend static reference checks',
            'Proceed to Estate single-owner rebuild pack only after blueprint sign-off'
        ]
    }
    REPORT_JSON.write_text(json.dumps(result, indent=2), encoding='utf-8')

    lines = []
    lines.append('JOM Estate Single-Owner Consolidation Blueprint v1')
    lines.append('=' * 54)
    lines.append(f"Generated UTC: {result['generated_utc']}")
    lines.append(f"Status: {status}")
    lines.append('')
    lines.append('Summary')
    lines.append('-------')
    lines.append(f"Profiles classified: {len(profiles)}")
    for key in ['KEEP', 'MERGE', 'REMOVE', 'REWIRE', 'REVIEW']:
        lines.append(f"{key}: {len(groups[key])}")
    lines.append(f"Duplicate endpoints: {len(duplicate_endpoints)}")
    lines.append(f"Legacy JSON consumer profiles: {len(legacy_profiles)}")
    lines.append(f"Command Centre/Estate overlap profiles: {len(command_overlap)}")
    lines.append('')

    def section(title, items):
        lines.append(title)
        lines.append('-' * len(title))
        if not items:
            lines.append('none')
        for p in items:
            lines.append(f"- {p.file} [{p.kind}] :: {p.decision} :: {p.reason}")
            if p.fetches:
                lines.append(f"  fetches: {', '.join(p.fetches[:8])}")
            if p.routes:
                lines.append(f"  routes: {', '.join(p.routes[:8])}")
            if p.legacy_refs:
                lines.append(f"  legacy refs: {', '.join(p.legacy_refs)}")
        lines.append('')

    section('KEEP', groups['KEEP'])
    section('MERGE', groups['MERGE'])
    section('REWIRE', groups['REWIRE'])
    section('REMOVE', groups['REMOVE'])
    section('REVIEW', groups['REVIEW'])

    lines.append('Duplicate endpoint map')
    lines.append('----------------------')
    if duplicate_endpoints:
        for ep, files in duplicate_endpoints.items():
            lines.append(f'- {ep}')
            for file in files:
                lines.append(f'  - {file}')
    else:
        lines.append('none')
    lines.append('')

    lines.append('Recommended consolidation decision')
    lines.append('----------------------------------')
    lines.append('- KEEP templates/estate.html as the only Estate template owner.')
    lines.append('- KEEP_CANDIDATE static/js/jom_estate_lifecycle_v1.js as the initial Estate JS owner unless current template proves another active owner.')
    lines.append('- MERGE site-review, access-validation, lifecycle-sync, and site-workspace behaviour into one Estate owner file.')
    lines.append('- REWIRE Estate away from /api/workspace/command-centre unless the endpoint is explicitly renamed as shared context only.')
    lines.append('- REMOVE old Estate-related JS/CSS only after validating they are not referenced by templates or route-specific pages.')
    lines.append('- Do not rebuild UI until legacy app/web.py and scripts/build_site_registry.py runtime consumers are handled or formally isolated.')
    lines.append('')
    lines.append('Next pack recommendation')
    lines.append('------------------------')
    lines.append('JOM Estate Runtime Consumer Isolation Pack v1: isolate or remove monitored_sites/site_access_validation/site_lifecycle_decisions active consumers before frontend rebuild.')

    REPORT_TXT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(lines[0])
    print(f'Status: {status}')
    print(f"KEEP: {len(groups['KEEP'])}")
    print(f"MERGE: {len(groups['MERGE'])}")
    print(f"REWIRE: {len(groups['REWIRE'])}")
    print(f"REMOVE: {len(groups['REMOVE'])}")
    print(f'Report: {REPORT_TXT}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
