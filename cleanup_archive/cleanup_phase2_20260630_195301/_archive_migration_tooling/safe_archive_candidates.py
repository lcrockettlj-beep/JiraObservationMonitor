from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports' / 'safe_archive_candidates_status.json'
OWNERSHIP = ROOT / 'reports' / 'project_ownership_map.json'

CANDIDATES = [
    'scripts/archive/apply_browser_refresh_pack.ps1',
    'scripts/archive/validate_browser_refresh_pack.ps1',
    'scripts/installers/apply_sprint8_combined_pack.ps1',
    'tools/admin_enrichment_output.txt',
    'tools/inputs/jom_estate_product_access_scope_inputs.zip',
    'tools/inputs/jom_home_estate_registry_truth_inputs.zip',
    'tools/inputs/jom_live_data_truth_audit_inputs.zip',
]


def now_stamp():
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def read_json(path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        return {'_read_error': str(exc)}


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def candidate_status_from_ownership():
    ownership = read_json(OWNERSHIP, {}) or {}
    rows = ownership.get('files') or []
    lookup = {row.get('file'): row for row in rows if isinstance(row, dict)}
    return {candidate: lookup.get(candidate) for candidate in CANDIDATES}


def main():
    archive_root = ROOT / 'backups' / '_project_cleanup_archive' / now_stamp()
    moved = []
    missing = []
    skipped = []
    ownership_lookup = candidate_status_from_ownership()

    for rel in CANDIDATES:
        src = ROOT / rel
        ownership_row = ownership_lookup.get(rel)
        ownership_status = (ownership_row or {}).get('status')
        if ownership_status and ownership_status != 'ARCHIVE_CANDIDATE':
            skipped.append({'file': rel, 'reason': f'Ownership map status is {ownership_status}, not ARCHIVE_CANDIDATE.'})
            continue
        if not src.exists():
            missing.append(rel)
            continue
        dest = archive_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        moved.append({'from': rel, 'to': str(dest.relative_to(ROOT)).replace('\\', '/')})

    rollback_script = archive_root / 'rollback_safe_archive_candidates.ps1'
    rollback_lines = [
        'param([string]$ProjectRoot = "C:\\Users\\Luke_C\\Desktop\\JiraObservationMonitor")',
        '$ErrorActionPreference = "Stop"',
        f'$ArchiveRoot = Join-Path $ProjectRoot "backups\\_project_cleanup_archive\\{archive_root.name}"',
    ]
    for item in moved:
        rollback_lines.append(f'New-Item -ItemType Directory -Path (Split-Path -Parent (Join-Path $ProjectRoot "{item["from"].replace("/", "\\")}")) -Force | Out-Null')
        rollback_lines.append(f'Move-Item -Path (Join-Path $ProjectRoot "{item["to"].replace("/", "\\")}") -Destination (Join-Path $ProjectRoot "{item["from"].replace("/", "\\")}") -Force')
    rollback_lines.append('Write-Host "Safe archive rollback complete." -ForegroundColor Green')
    archive_root.mkdir(parents=True, exist_ok=True)
    rollback_script.write_text('\n'.join(rollback_lines) + '\n', encoding='utf-8')

    payload = {
        'schema': 'jom-safe-archive-candidates-status-v1',
        'generated_at_utc': now_utc(),
        'mode': 'archive-only-no-delete',
        'archive_root': str(archive_root),
        'candidate_count': len(CANDIDATES),
        'moved_count': len(moved),
        'missing_count': len(missing),
        'skipped_count': len(skipped),
        'moved': moved,
        'missing': missing,
        'skipped': skipped,
        'rollback_script': str(rollback_script),
    }
    write_json(REPORT, payload)
    print(json.dumps({
        'status': 'ok',
        'archive_root': str(archive_root),
        'moved_count': len(moved),
        'missing_count': len(missing),
        'skipped_count': len(skipped),
        'output': str(REPORT),
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
