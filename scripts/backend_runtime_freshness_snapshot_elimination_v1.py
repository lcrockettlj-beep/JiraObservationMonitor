from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "static" / "data"
OUTPUT = DATA / "runtime_live_truth_status.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"_json_error": str(exc), "_file": str(path)}


def parse_time(value: Any):
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def freshness(timestamp: Any, current_hours: int = 24, stale_hours: int = 72) -> Dict[str, Any]:
    parsed = parse_time(timestamp)
    if not parsed:
        return {"state": "unknown_timestamp", "timestamp": timestamp or None, "age_hours": None}
    age = round((datetime.now(timezone.utc) - parsed).total_seconds() / 3600, 2)
    if age <= current_hours:
        state = "current"
    elif age <= stale_hours:
        state = "aging"
    else:
        state = "stale"
    return {"state": state, "timestamp": parsed.isoformat().replace("+00:00", "Z"), "age_hours": age}


def generated_at(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("generated_at_utc") or payload.get("updated_at_utc") or payload.get("served_at_utc") or "")


def source_record(name: str, path: Path, source_of_truth: str, *, expected_live: bool = False) -> Dict[str, Any]:
    payload = read_json(path, {})
    ts = generated_at(payload)
    fresh = freshness(ts)
    live_collection = bool(payload.get("live_collection")) if isinstance(payload, dict) else False
    status = payload.get("status") if isinstance(payload, dict) else None
    if expected_live and live_collection and status in ("ok", "partial"):
        trust_state = "live_truth_available"
    elif fresh.get("state") in ("current", "aging"):
        trust_state = "generated_cache_available"
    elif path.exists():
        trust_state = "legacy_snapshot_not_website_truth"
    else:
        trust_state = "missing"
    return {
        "name": name,
        "path": str(path.relative_to(ROOT)) if path.exists() else str(path.relative_to(ROOT)),
        "exists": path.exists(),
        "schema": payload.get("schema") if isinstance(payload, dict) else None,
        "status": status,
        "live_collection": live_collection,
        "generated_at_utc": ts or None,
        "freshness": fresh,
        "source_of_truth": source_of_truth,
        "trust_state": trust_state,
    }


def main() -> int:
    product = source_record(
        "estate_product_access",
        DATA / "estate_product_access.json",
        "live /estate/product-access endpoint; generated file is cache/audit output only",
        expected_live=True,
    )
    access_truth = source_record(
        "estate_access_truth",
        DATA / "estate_access_truth.json",
        "derived from live product access; generated file is cache/audit output only",
        expected_live=True,
    )
    registry = source_record(
        "site_registry",
        DATA / "site_registry.json",
        "registry contract route /registry/sites; generated cache with explicit freshness",
    )
    admin = source_record(
        "admin_truth_v2",
        DATA / "admin_truth_v2.json",
        "admin truth contract route /admin/truth; live product overlay is primary for product counts",
    )
    footprint = source_record(
        "user_footprint",
        DATA / "user_footprint.json",
        "user footprint contract route /users/footprint; guarded unavailable if source incomplete",
    )

    legacy = [
        source_record("billing_seats", DATA / "billing_seats.json", "legacy billing snapshot; not website truth"),
        source_record("latest_run", ROOT / "latest_run.json", "legacy runtime snapshot; not website truth"),
        source_record("latest_run_admin_enriched", ROOT / "latest_run_admin_enriched.json", "legacy runtime snapshot; not website truth"),
    ]

    payload = {
        "schema": "jom-runtime-live-truth-status-v1",
        "generated_at_utc": now_utc(),
        "policy": {
            "rule": "Live endpoints and explicit backend contracts are source of truth. Legacy snapshots must not drive website truth.",
            "legacy_snapshot_files_are_reference_only": True,
            "generated_static_files_are_cache_or_state_only": True,
        },
        "live_truth_sources": {
            "estate_product_access": product,
            "estate_access_truth": access_truth,
            "site_registry": registry,
            "admin_truth_v2": admin,
            "user_footprint": footprint,
        },
        "legacy_snapshots_demoted": legacy,
        "summary": {
            "live_product_access_available": product.get("trust_state") == "live_truth_available",
            "live_product_access_status": product.get("status"),
            "legacy_snapshot_count": len(legacy),
            "legacy_snapshots_demoted_from_website_truth": True,
        },
    }
    DATA.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "summary": payload["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
