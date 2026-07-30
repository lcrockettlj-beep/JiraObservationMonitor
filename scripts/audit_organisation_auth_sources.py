from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.audits.organisation_auth_source_audit import audit_organisation_auth_sources
from app.runtime.runtime_data_paths import runtime_write_json


def main() -> int:
    payload = audit_organisation_auth_sources()
    runtime_write_json("organisation_auth_source_audit.json", payload)
    print(json.dumps({
        "status": payload.get("status"),
        "oauth_client_configured": payload.get("oauth_client_configured"),
        "oauth_client_secret_configured": payload.get("oauth_client_secret_configured"),
        "secrets_exposed": payload.get("secrets_exposed"),
        "static_fallback_used": payload.get("static_fallback_used"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
