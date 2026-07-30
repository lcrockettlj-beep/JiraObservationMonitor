from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.builders.organisation_discovery import collect_organisation_discovery
from app.runtime.runtime_data_paths import runtime_write_json


def main() -> int:
    payload = collect_organisation_discovery()
    runtime_write_json("organisation_discovery.json", payload)
    print(json.dumps({
        "status": payload.get("status"),
        "live_collection": payload.get("live_collection"),
        "token_source": payload.get("token_source"),
        "organisation_count": payload.get("organisation_count"),
        "static_fallback_used": payload.get("static_fallback_used"),
        "secrets_exposed": payload.get("secrets_exposed"),
        "http_status": payload.get("http_status"),
        "reason": payload.get("reason"),
    }, indent=2))
    return 0 if payload.get("status") in {"ok", "unavailable", "error"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
