from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "static" / "data" / "site_registry.json"
DECISIONS = ROOT / "config" / "site_onboarding_decisions.json"
OUT = ROOT / "static" / "data" / "site_onboarding_review.json"
REPORT = ROOT / "reports" / "site_onboarding_action_pack_status.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def site_key(site: dict) -> str | None:
    return site.get("site_key") or site.get("key") or site.get("site")


def is_monitored(site: dict) -> bool:
    return site.get("is_monitored") is True or site.get("classification") == "monitored"


def main() -> int:
    registry = read_json(REGISTRY, {})
    decisions = read_json(DECISIONS, {"approved": {}, "ignored": {}, "history": []})
    approved = decisions.get("approved", {}) if isinstance(decisions, dict) else {}
    ignored = decisions.get("ignored", {}) if isinstance(decisions, dict) else {}

    pending = []
    approved_rows = []
    ignored_rows = []

    for site in registry.get("sites", []) if isinstance(registry, dict) else []:
        if not isinstance(site, dict):
            continue
        key = site_key(site)
        if not key or is_monitored(site):
            continue
        row = {
            "site_key": key,
            "classification": site.get("classification"),
            "is_monitored": site.get("is_monitored"),
            "cloud_id": site.get("cloud_id"),
            "url": site.get("url") or site.get("site_url"),
            "approve_command": f"python scripts/run_site_onboarding_action_v1.py --site-key {key} --decision approve --reason \"approved for monitoring\" --actor operator --apply",
            "ignore_command": f"python scripts/run_site_onboarding_action_v1.py --site-key {key} --decision ignore --reason \"not in monitoring scope\" --actor operator --apply",
        }
        if key in approved:
            row["decision"] = "approved"
            row["decision_record"] = approved[key]
            approved_rows.append(row)
        elif key in ignored:
            row["decision"] = "ignored"
            row["decision_record"] = ignored[key]
            ignored_rows.append(row)
        else:
            row["decision"] = "pending"
            pending.append(row)

    payload = {
        "schema": "jom-site-onboarding-review-v2",
        "generated_at_utc": now_utc(),
        "summary": {
            "pending_count": len(pending),
            "approved_count": len(approved_rows),
            "ignored_count": len(ignored_rows),
            "total_review_count": len(pending) + len(approved_rows) + len(ignored_rows),
        },
        "pending": pending,
        "approved": approved_rows,
        "ignored": ignored_rows,
        "decision_source": str(DECISIONS),
        "safety_note": "Approve/ignore records decisions only. Monitoring scope changes require a separate controlled registry/config sync step.",
    }
    write_json(OUT, payload)

    report = {
        "schema": "jom-site-onboarding-action-pack-v1-status",
        "generated_at_utc": now_utc(),
        "status": "ok",
        "output": str(OUT),
        "summary": payload["summary"],
    }
    write_json(REPORT, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
