import json
from pathlib import Path

path = Path("latest_run_admin_enriched_pretty.json")

if not path.exists():
    path = Path("latest_run_admin_enriched.json")

print(f"Reading: {path}")

data = json.loads(path.read_text(encoding="utf-8"))
drilldowns = data.get("drilldowns", {})

print("\nDRILLDOWN KEYS:")
for key in sorted(drilldowns.keys()):
    print("-", key)
