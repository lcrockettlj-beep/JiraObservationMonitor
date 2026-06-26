import json
from pathlib import Path

files = []
files.extend(Path(".").glob("latest_run*.json"))
files.extend(Path("backups/latest_runtime").rglob("latest_run*.json"))

markers = [
    "users_rows",
    "users_export_rows",
    "users_export",
    "Jira - gli-it-project",
    "Jira - gli-delivery-tm",
    "Jira - gli-global-technology",
    "site::gli-it-project",
    "site::gli-delivery-tm",
    "site::gli-global-technology",
    "access::Jira - gli-it-project",
    "access::Jira - gli-delivery-tm",
    "access::Jira - gli-global-technology",
]

print("Scanning runtime files for old user access data...")
print()

for path in files:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue

    hits = [m for m in markers if m in text]
    if not hits:
        continue

    try:
        data = json.loads(text)
    except Exception:
        data = {}

    drilldowns = data.get("drilldowns", {}) if isinstance(data, dict) else {}
    users_rows = data.get("users_rows") or data.get("users_export_rows") or data.get("users_export") or []

    print("=" * 90)
    print(path)
    print("Hits:", ", ".join(hits))
    print("users_rows-like count:", len(users_rows) if isinstance(users_rows, list) else "not-list")

    for key in [
        "site::gli-it-project",
        "site::gli-delivery-tm",
        "site::gli-global-technology",
        "access::Jira - gli-it-project",
        "access::Jira - gli-delivery-tm",
        "access::Jira - gli-global-technology",
    ]:
        section = drilldowns.get(key, {})
        rows = section.get("rows", []) if isinstance(section, dict) else []
        if rows:
            print(f"{key}: {len(rows)} rows")
