import json
from pathlib import Path

path = Path("latest_run_admin_enriched_pretty.json")

if not path.exists():
    path = Path("latest_run_admin_enriched.json")

data = json.loads(path.read_text(encoding="utf-8"))
drilldowns = data.get("drilldowns", {})

print(f"Reading: {path}")
print()

for key, value in sorted(drilldowns.items()):
    rows = value.get("rows", []) if isinstance(value, dict) else []
    print(f"{key}: {len(rows)} rows")
