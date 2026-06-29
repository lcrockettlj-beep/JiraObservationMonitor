import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
paths = [
    ROOT / 'static/data/admin_enriched_refresh_status.json',
    ROOT / 'static/data/source_freshness_audit.json',
    ROOT / 'static/data/source_reliability_status.json',
    ROOT / 'latest_run_admin_enriched.json',
]
for path in paths:
    print(f'{path.relative_to(ROOT)}: exists={path.exists()}')

status_path = ROOT / 'static/data/admin_enriched_refresh_status.json'
if status_path.exists():
    status = json.loads(status_path.read_text(encoding='utf-8'))
    print(json.dumps({
        'schema': status.get('schema'),
        'overall_status': status.get('overall_status'),
        'admin_after': status.get('after', {}).get('latest_run_admin_enriched'),
        'manual_next_action': status.get('manual_next_action'),
    }, indent=2))
