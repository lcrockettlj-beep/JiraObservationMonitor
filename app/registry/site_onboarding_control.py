from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DECISIONS_PATH = PROJECT_ROOT / "config" / "site_onboarding_decisions.json"
AUDIT_LOG = PROJECT_ROOT / "reports" / "site_onboarding_decision_audit.jsonl"
CONTROL_STATUS = PROJECT_ROOT / "static" / "data" / "site_onboarding_control_status.json"
VALID_STATES = {"pending", "approved", "rejected", "ignored", "monitored"}


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


def load_decisions() -> dict:
    payload = read_json(DECISIONS_PATH, {})
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("schema", "jom-site-onboarding-decisions-v1")
    payload.setdefault("generated_at_utc", now_utc())
    payload.setdefault("sites", {})
    payload.setdefault("approved", {})
    payload.setdefault("ignored", {})
    payload.setdefault("history", [])
    return normalise_legacy_decisions(payload)


def normalise_legacy_decisions(payload: dict) -> dict:
    sites = payload.setdefault("sites", {})
    for state, key_name in (("approved", "approved"), ("ignored", "ignored")):
        legacy = payload.get(key_name, {})
        if isinstance(legacy, dict):
            for site_key, entry in legacy.items():
                if site_key not in sites:
                    sites[site_key] = {
                        "site_key": site_key,
                        "state": state,
                        "decision": state,
                        "reason": entry.get("reason") if isinstance(entry, dict) else "legacy decision import",
                        "actor": entry.get("actor") if isinstance(entry, dict) else "system",
                        "decided_at_utc": entry.get("decided_at_utc") if isinstance(entry, dict) else now_utc(),
                        "source": "legacy_import",
                    }
    return payload


def get_site_state(site_key: str) -> str:
    record = load_decisions().get("sites", {}).get(site_key)
    if not isinstance(record, dict):
        return "pending"
    state = record.get("state") or record.get("decision") or "pending"
    return state if state in VALID_STATES else "pending"


def is_site_approved(site_key: str) -> bool:
    return get_site_state(site_key) == "approved"


def record_decision(site_key: str, state: str, reason: str = "", actor: str = "operator", apply: bool = False) -> dict:
    if state not in {"approved", "rejected", "ignored", "pending"}:
        raise ValueError(f"Unsupported onboarding state: {state}")
    entry = {
        "site_key": site_key,
        "state": state,
        "decision": state,
        "reason": reason,
        "actor": actor,
        "decided_at_utc": now_utc(),
    }
    if not apply:
        return {"status": "dry_run", "applied": False, "entry": entry}
    decisions = load_decisions()
    decisions["generated_at_utc"] = now_utc()
    decisions.setdefault("sites", {})[site_key] = entry
    decisions.setdefault("history", []).append(entry)
    decisions.setdefault("approved", {})
    decisions.setdefault("ignored", {})
    if state == "approved":
        decisions["approved"][site_key] = entry
        decisions["ignored"].pop(site_key, None)
    elif state in {"ignored", "rejected"}:
        decisions["ignored"][site_key] = entry
        decisions["approved"].pop(site_key, None)
    else:
        decisions["approved"].pop(site_key, None)
        decisions["ignored"].pop(site_key, None)
    write_json(DECISIONS_PATH, decisions)
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    status = {"schema": "jom-site-onboarding-control-status-v1", "generated_at_utc": now_utc(), "last_decision": entry}
    write_json(CONTROL_STATUS, status)
    return {"status": "ok", "applied": True, "entry": entry, "decisions_file": str(DECISIONS_PATH), "audit_log": str(AUDIT_LOG)}
