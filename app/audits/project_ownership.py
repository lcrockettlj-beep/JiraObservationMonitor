from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
REPORT_JSON = ROOT / "reports" / "project_ownership_map.json"
REPORT_MD = ROOT / "reports" / "project_ownership_map.md"
AUDIT_JSON = ROOT / "reports" / "project_alignment_audit.json"

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules", ".venv", "venv"}
CORE_KEEP_ROOT = {
    ".env", ".gitignore", "requirements.txt", "web.py", "main.py", "auth.py", "jira_client.py",
    "admin_api_client.py", "admin_api_enrichment.py", "admin_named_access_collector.py",
    "data_collector.py", "site_discovery.py", "snapshots.py", "billing_catalog.py",
    "backend_contract.py", "reporting.py", "project_counts.py", "estate_metrics.py",
    "change_detection.py", "tier_engine.py", "trends.py", "intelligence.py", "intelligence_rules_engine.py",
    "alert_rules_engine.py", "auth_verification.py", "__init__.py"
}
ACTIVE_STATIC_DATA = {
    "admin_enriched_refresh_status.json", "admin_group_expansion.json", "admin_group_expansion_status.json",
    "live_named_access_contract", "admin_truth_v2.json", "billing_seats.json", "estate_access_truth.json",
    "estate_product_access.json", "group_expansion_recovery_status.json", "named_access_recovery_status.json",
    "live_named_access_contract", "operational_source_recovery_status.json", "product_access_refresh_status.json",
    "runtime_refresh_status.json", "site_registry.json", "source_freshness_audit.json",
    "source_reliability_status.json", "user_footprint.json", "user_footprint_unlock_status.json"
}
ACTIVE_TEMPLATES = {"home.html", "estate.html", "reference.html", "_nav.html", "detail_list.html"}
REVIEW_TEMPLATES = {"admin.html", "site.html"}

AREA_HINTS = [
    ("named_access", ["named_access", "user_footprint", "group_expansion", "admin_group_expansion"]),
    ("source_reliability", ["source_reliability", "source_freshness", "truth", "reliability"]),
    ("site_registry", ["site_registry", "site_discovery", "onboarding"]),
    ("estate", ["estate", "product_access", "footprint"]),
    ("admin", ["admin", "reference", "billing"]),
    ("home", ["home", "dashboard", "tiles"]),
    ("site_pages", ["site.html", "site.css", "site.js", "detail"]),
    ("runtime", ["latest_run", "snapshot", "runtime", "sync"]),
    ("auth", ["auth", "token"]),
    ("docs", ["docs", "manual", "handover", "sprint"]),
    ("backups", ["backup"]),
]

TARGET_STRUCTURE = {
    "home": "templates/home + static/js/home + static/css/home",
    "estate": "templates/estate + static/js/estate + static/css/estate",
    "admin": "templates/admin + static/js/admin + static/css/admin",
    "shared_ui": "templates/shared + static/js/shared + static/css/shared",
    "named_access": "app/access + static/data/admin + reports/access",
    "site_registry": "app/registry + static/data/registry + reports/registry",
    "source_reliability": "app/audits + static/data/reliability + reports/reliability",
    "runtime": "app/runtime + static/data/runtime + tools/maintenance",
    "collectors": "app/collectors",
    "builders": "app/builders",
    "tools": "tools/installers + tools/inputs + tools/maintenance",
    "docs": "docs/*",
    "backups": "backups/current + backups/archive with retention policy",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_skipped(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def scan_files() -> List[Path]:
    paths = []
    for p in ROOT.rglob("*"):
        if p.is_file() and not is_skipped(p):
            paths.append(p)
    return sorted(paths, key=lambda x: rel(x))


def refs_from_text(path: Path) -> List[str]:
    text = read_text(path)
    refs = set()
    patterns = [
        r"/static/([^'\"\s)>]+)",
        r"url_for\(['\"]static['\"],\s*filename=['\"]([^'\"]+)['\"]\)",
        r"fetch\(['\"]([^'\"]+\.json)['\"]",
        r"href=['\"]([^'\"]+\.(?:css|js|json))['\"]",
        r"src=['\"]([^'\"]+\.(?:css|js|json))['\"]",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text):
            value = m.group(1)
            if value.startswith('/static/'):
                value = value.replace('/static/', '', 1)
            refs.add(value)
    return sorted(refs)


def build_reference_index(paths: List[Path]) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    static_refs = defaultdict(list)
    data_refs = defaultdict(list)
    for p in paths:
        if p.suffix.lower() not in {'.html', '.js', '.css', '.py'}:
            continue
        rp = rel(p)
        for ref in refs_from_text(p):
            if ref.endswith('.json'):
                data_refs[ref].append(rp)
            else:
                static_refs[ref].append(rp)
        text = read_text(p)
        for m in re.finditer(r"(?:static/data|reports|latest_run)[A-Za-z0-9_./\\-]*\.(?:json|md)", text):
            data_refs[m.group(0).replace('\\', '/')].append(rp)
    return dict(static_refs), dict(data_refs)


def infer_area(path: Path) -> str:
    rp = rel(path).lower()
    name = path.name.lower()
    for area, hints in AREA_HINTS:
        if any(h in rp or h in name for h in hints):
            return area
    parts = path.relative_to(ROOT).parts
    if parts:
        if parts[0] == 'templates': return 'ui_templates'
        if parts[0] == 'static': return 'ui_static'
        if parts[0] == 'scripts': return 'scripts'
        if parts[0] == 'backend': return 'backend'
        if parts[0] == 'reports': return 'reports'
        if parts[0] == 'config': return 'config'
    return 'core'


def classify(path: Path, static_refs: Dict[str, List[str]], data_refs: Dict[str, List[str]]) -> Dict[str, Any]:
    rp = rel(path)
    name = path.name
    suffix = path.suffix.lower()
    parts = path.relative_to(ROOT).parts
    first = parts[0] if parts else ''
    area = infer_area(path)
    status = 'REVIEW'
    reason = 'Needs owner confirmation.'
    target = TARGET_STRUCTURE.get(area, 'to be decided')

    lower = rp.lower()

    if first == 'backups':
        return {"file": rp, "area": 'backups', "status": 'DO_NOT_TOUCH_BACKUP', "reason": 'Backup/history area. Do not delete during runtime cleanup; handle via retention policy.', "target_structure": TARGET_STRUCTURE['backups']}
    if first == 'docs':
        return {"file": rp, "area": 'docs', "status": 'KEEP_SUPPORT', "reason": 'Documentation/support artifact.', "target_structure": TARGET_STRUCTURE['docs']}
    if first == 'reports':
        return {"file": rp, "area": area, "status": 'KEEP_SUPPORT', "reason": 'Report/audit output. Keep unless superseded by approved report retention policy.', "target_structure": TARGET_STRUCTURE.get(area, 'reports/<area>')}
    if first == '_cleanup_archive':
        return {"file": rp, "area": 'legacy', "status": 'ARCHIVE_CANDIDATE', "reason": 'Already marked cleanup archive. Keep archived, not active runtime.', "target_structure": 'backups/archive or docs/archive'}
    if 'pack' in lower and first not in {'docs', 'reports'}:
        return {"file": rp, "area": 'pack_residue', "status": 'ARCHIVE_CANDIDATE', "reason": 'Extracted/input pack residue; not active runtime unless explicitly referenced.', "target_structure": 'tools/inputs or backups/archive'}
    if '__pycache__' in lower or suffix in {'.pyc', '.pyo'}:
        return {"file": rp, "area": 'cache', "status": 'DELETE_CANDIDATE', "reason": 'Generated Python cache. Safe cleanup candidate.', "target_structure": 'none'}
    if '.bak' in lower or lower.endswith('.bak'):
        return {"file": rp, "area": area, "status": 'ARCHIVE_CANDIDATE', "reason": 'Backup suffix file. Move out of active runtime if not already archived.', "target_structure": 'backups/archive'}
    if suffix == '.zip':
        return {"file": rp, "area": 'inputs', "status": 'ARCHIVE_CANDIDATE', "reason": 'Input/pack zip should not live in runtime root.', "target_structure": 'tools/inputs'}

    if first == 'templates':
        if name in ACTIVE_TEMPLATES:
            status, reason = 'KEEP_ACTIVE', 'Active page/shared template.'
        elif name in REVIEW_TEMPLATES:
            status, reason = 'REVIEW', 'Template exists but ownership/route role needs confirmation.'
        else:
            status, reason = 'REVIEW', 'Template not in core active template set.'
        return {"file": rp, "area": area, "status": status, "reason": reason, "target_structure": TARGET_STRUCTURE.get(area, 'templates/<area>')}

    if first == 'static':
        static_key = '/'.join(parts[1:]) if len(parts) > 1 else name
        referenced = static_key in static_refs or rp.replace('static/', '') in static_refs
        if len(parts) > 1 and parts[1] == 'data':
            if name in ACTIVE_STATIC_DATA:
                status, reason = 'KEEP_ACTIVE_DATA', 'Active runtime data contract file.'
            elif '.bak' in lower:
                status, reason = 'ARCHIVE_CANDIDATE', 'Static data backup file in runtime data folder.'
            else:
                status, reason = 'REVIEW_DATA', 'Static data file not in current active contract set; confirm owner.'
        elif referenced or name in {'theme.js', 'core_truth_guard.js', 'dashboard_refresh.js', 'source_freshness_badge.js', 'source_reliability_dashboard.js', 'app.css', 'truth.css', 'source_freshness.css', 'source_reliability_dashboard.css'}:
            status, reason = 'KEEP_ACTIVE_UI', 'Referenced by template/static runtime or shared UI module.'
        else:
            status, reason = 'REVIEW_UI', 'Static asset not detected as referenced by static scan; confirm before moving/removing.'
        return {"file": rp, "area": area, "status": status, "reason": reason, "target_structure": TARGET_STRUCTURE.get(area, 'static/<area>')}

    if first == 'scripts':
        if suffix in {'.py', '.ps1', '.cmd'}:
            status, reason = 'KEEP_TOOLING', 'Script/tooling file. Classify into builders/collectors/audits in restructure phase.'
        else:
            status, reason = 'REVIEW', 'Non-standard script folder file.'
        return {"file": rp, "area": area, "status": status, "reason": reason, "target_structure": TARGET_STRUCTURE.get(area, 'app/scripts or tools')}

    if first == 'backend':
        return {"file": rp, "area": 'backend', "status": 'KEEP_ACTIVE', "reason": 'Backend runtime helper/module.', "target_structure": TARGET_STRUCTURE['runtime']}

    if first == 'config':
        return {"file": rp, "area": 'config', "status": 'KEEP_ACTIVE', "reason": 'Configuration package.', "target_structure": 'config or app/config'}

    if first == 'snapshots':
        return {"file": rp, "area": 'runtime', "status": 'KEEP_RUNTIME_HISTORY', "reason": 'Snapshot history/root snapshot index.', "target_structure": TARGET_STRUCTURE['runtime']}

    if name in CORE_KEEP_ROOT:
        return {"file": rp, "area": area, "status": 'KEEP_ACTIVE_ROOT', "reason": 'Root-level active module/application entry point.', "target_structure": TARGET_STRUCTURE.get(area, 'app/<area>')}

    if name.startswith('latest_run') or name in {'tokens.json', '.auth_state.json'}:
        return {"file": rp, "area": 'runtime', "status": 'KEEP_RUNTIME', "reason": 'Runtime/auth state file. Review secret handling separately.', "target_structure": TARGET_STRUCTURE['runtime']}

    if suffix in {'.txt', '.md'}:
        return {"file": rp, "area": 'support', "status": 'ARCHIVE_CANDIDATE', "reason": 'Root support/output text should be moved under docs or tools.', "target_structure": 'docs/support or tools'}

    return {"file": rp, "area": area, "status": status, "reason": reason, "target_structure": target}


def write_markdown(payload: Dict[str, Any]) -> None:
    lines = []
    lines.append('# JOM Project Ownership Map')
    lines.append('')
    lines.append(f"Generated: `{payload['generated_at_utc']}`")
    lines.append('')
    lines.append('## Summary')
    lines.append('')
    for key, value in payload['summary'].items():
        if key not in {'status_counts', 'area_counts'}:
            lines.append(f"- {key}: **{value}**")
    lines.append('')
    lines.append('### Status Counts')
    lines.append('')
    for status, count in payload['summary']['status_counts'].items():
        lines.append(f"- `{status}`: {count}")
    lines.append('')
    lines.append('### Area Counts')
    lines.append('')
    for area, count in payload['summary']['area_counts'].items():
        lines.append(f"- `{area}`: {count}")
    lines.append('')
    lines.append('## High Priority Review Groups')
    lines.append('')
    review = [r for r in payload['files'] if r['status'] in {'REVIEW', 'REVIEW_UI', 'REVIEW_DATA', 'ARCHIVE_CANDIDATE', 'DELETE_CANDIDATE'}]
    if not review:
        lines.append('- None flagged.')
    else:
        for row in review[:80]:
            lines.append(f"- `{row['status']}` / `{row['area']}` / `{row['file']}` — {row['reason']}")
    lines.append('')
    lines.append('## Target Structure Proposal')
    lines.append('')
    for area, target in payload['target_structure'].items():
        lines.append(f"- `{area}` → `{target}`")
    lines.append('')
    lines.append('## Safety Note')
    lines.append('')
    lines.append('This report is classification-only. It does not approve deletion or movement by itself. Build a dedicated cleanup pack after review.')
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> int:
    paths = scan_files()
    static_refs, data_refs = build_reference_index(paths)
    rows = [classify(p, static_refs, data_refs) for p in paths]
    status_counts = Counter(row['status'] for row in rows)
    area_counts = Counter(row['area'] for row in rows)
    payload = {
        'schema': 'jom-project-ownership-map-v1',
        'generated_at_utc': now_utc(),
        'mode': 'classification-only-no-file-moves',
        'summary': {
            'files_classified': len(rows),
            'keep_like': sum(count for status, count in status_counts.items() if status.startswith('KEEP')),
            'review_like': sum(count for status, count in status_counts.items() if 'REVIEW' in status),
            'archive_candidates': status_counts.get('ARCHIVE_CANDIDATE', 0),
            'delete_candidates': status_counts.get('DELETE_CANDIDATE', 0),
            'do_not_touch_backups': status_counts.get('DO_NOT_TOUCH_BACKUP', 0),
            'status_counts': dict(sorted(status_counts.items())),
            'area_counts': dict(sorted(area_counts.items())),
        },
        'target_structure': TARGET_STRUCTURE,
        'static_reference_index': static_refs,
        'data_reference_index': data_refs,
        'files': sorted(rows, key=lambda row: row['file']),
    }
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    write_markdown(payload)
    print(json.dumps({
        'status': 'ok',
        'files_classified': len(rows),
        'keep_like': payload['summary']['keep_like'],
        'review_like': payload['summary']['review_like'],
        'archive_candidates': payload['summary']['archive_candidates'],
        'delete_candidates': payload['summary']['delete_candidates'],
        'do_not_touch_backups': payload['summary']['do_not_touch_backups'],
        'json': str(REPORT_JSON),
        'report': str(REPORT_MD),
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
