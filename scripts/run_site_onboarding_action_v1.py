from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "static" / "data" / "site_registry.json"
DECISIONS = ROOT / "config" / "site_onboarding_decisions.json"
AUDIT_JSONL = ROOT / "reports" / "site_onboarding_decision_audit.jsonl"
STATUS = ROOT / "reports" / "site_onboarding_action_status.json"


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


def site_key_of(site: dict) -> str | None:
    return site.get("site_key") or site.get("key") or site.get("site")


def monitored(site: dict) -> bool:
    return site.get("is_monitored") is True or site.get("classification") == "monitored"


def load_site(site_key: str) -> dict | None:
    registry = read_json(REGISTRY, {})
    for site in registry.get("sites", []) if isinstance(registry, dict) else []:
        if isinstance(site, dict) and site_key_of(site) == site_key:
            return site
    return None


def load_decisions() -> dict:
    return read_json(DECISIONS, {
        "schema": "jom-site-onboarding-decisions-v1",
        "generated_at_utc": now_utc(),
        "approved": {},
        "ignored": {},
        "history": [],
    })


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a JOM site onboarding decision.")
    parser.add_argument("--site-key", required=True)
    parser.add_argument("--decision", choices=["approve", "ignore"], required=True)
    parser.add_argument("--reason", default="")
    parser.add_argument("--actor", default="operator")
    parser.add_argument("--apply", action="store_true", help="Required to write the decision. Without this flag the command is dry-run only.")
    args = parser.parse_args()

    site = load_site(args.site_key)
    if not site:
        raise SystemExit(f"Site not found in registry: {args.site_key}")

    if monitored(site) and args.decision == "approve":
        result = {
            "status": "noop",
            "reason": "site is already monitored",
            "site_key": args.site_key,
            "decision": args.decision,
            "applied": False,
        }
        write_json(STATUS, result)
        print(json.dumps(result, indent=2))
        return 0

    entry = {
        "site_key": args.site_key,
        "decision": args.decision,
        "reason": args.reason,
        "actor": args.actor,
        "decided_at_utc": now_utc(),
        "site_snapshot": {
            "classification": site.get("classification"),
            "is_monitored": site.get("is_monitored"),
            "cloud_id": site.get("cloud_id"),
            "url": site.get("url") or site.get("site_url"),
        },
    }

    if not args.apply:
        result = {
            "status": "dry_run",
            "applied": False,
            "entry": entry,
            "next_command": f"python scripts/run_site_onboarding_action_v1.py --site-key {args.site_key} --decision {args.decision} --reason \"{args.reason}\" --actor {args.actor} --apply",
        }
        write_json(STATUS, result)
        print(json.dumps(result, indent=2))
        return 0

    decisions = load_decisions()
    decisions["generated_at_utc"] = now_utc()
    if args.decision == "approve":
        decisions.setdefault("approved", {})[args.site_key] = entry
        decisions.setdefault("ignored", {}).pop(args.site_key, None)
    else:
        decisions.setdefault("ignored", {})[args.site_key] = entry
        decisions.setdefault("approved", {}).pop(args.site_key, None)
    decisions.setdefault("history", []).append(entry)
    write_json(DECISIONS, decisions)

    AUDIT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_JSONL.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    result = {
        "status": "ok",
        "applied": True,
        "entry": entry,
        "decisions_file": str(DECISIONS),
        "audit_log": str(AUDIT_JSONL),
        "note": "Decision recorded. Monitoring scope is not changed automatically until a registry/config sync pack consumes approved decisions.",
    }
    write_json(STATUS, result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
