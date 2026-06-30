from pathlib import Path
import json
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static/data/site_onboarding_review.json"

now = datetime.now(timezone.utc).isoformat()

registry = json.loads((ROOT / "static/data/site_registry.json").read_text())

queue = []
for s in registry.get("sites", []):
    if not s.get("is_monitored"):
        queue.append({
            "site_key": s.get("site_key") or s.get("key"),
            "classification": s.get("classification"),
            "url": s.get("url"),
            "action": "approve_or_ignore"
        })

payload = {
    "generated_at_utc": now,
    "queue": queue,
    "count": len(queue)
}

OUT.write_text(json.dumps(payload, indent=2))
print(json.dumps(payload, indent=2))
