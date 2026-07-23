from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"_json_error": str(exc), "_file": str(path)}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("https://", "").replace("http://", "")
    text = text.replace(".atlassian.net", "")
    text = text.strip("/").split("/")[0]
    return text


def site_url(key: str) -> str:
    return f"https://{key}.atlassian.net"


def merge_site(registry: Dict[str, Dict[str, Any]], site_key: str, source: str, **fields: Any) -> None:
    key = norm(site_key)
    if not key:
        return
    row = registry.setdefault(key, {
        "site_key": key,
        "site_name": key,
        "site_url": site_url(key),
        "aliases": [key, site_url(key)],
        "sources": [],
        "classification": "discovered",
        "is_monitored": False,
        "can_approve": True,
        "metrics": {},
    })
    if source not in row["sources"]:
        row["sources"].append(source)
    for alias in [fields.get("cloud_id"), fields.get("site_url"), key, site_url(key)]:
        alias_norm = norm(alias)
        alias_value = alias if str(alias or "").startswith("http") else alias_norm
        if alias_value and alias_value not in row["aliases"]:
            row["aliases"].append(alias_value)
    for field in ["cloud_id", "site_name", "site_url", "status", "reason"]:
        if fields.get(field):
            row[field] = fields[field]
    metrics = fields.get("metrics") or {}
    if isinstance(metrics, dict):
        row.setdefault("metrics", {}).update(metrics)


def build_registry(project_root: Path) -> Dict[str, Any]:
    data = project_root / "static" / "data"
    current = read_json(data / "site_registry.json", {})
    product = read_json(data / "estate_product_access.json", {})
    monitored = read_json(data / "monitored_sites.json", {})
    decisions = read_json(data / "site_lifecycle_decisions.json", {})
    access_validation = read_json(data / "site_access_validation.json", {})
    admin_named = read_json(data / "live_named_access_contract", {})

    registry: Dict[str, Dict[str, Any]] = {}
    for site in current.get("sites", []) if isinstance(current, dict) else []:
        if isinstance(site, dict):
            key = site.get("site_key") or site.get("key") or site.get("site_name") or site.get("site_url")
            merge_site(registry, key, "existing_registry")
            registry[norm(key)].update(site)

    for site in product.get("sites", []) if isinstance(product, dict) else []:
        if isinstance(site, dict):
            merge_site(
                registry,
                site.get("site_key"),
                "product_access",
                cloud_id=site.get("cloud_id"),
                site_name=site.get("site_name"),
                site_url=site.get("site_url"),
                status=site.get("status"),
                metrics={
                    "jira_product_user_count": site.get("jira_product_user_count", 0),
                    "jira_product_seat_limit": site.get("jira_product_seat_limit", 0),
                    "jira_role_count": site.get("jira_role_count", 0),
                },
            )

    monitored_keys = set()
    for source in [monitored, decisions, access_validation]:
        if not isinstance(source, dict):
            continue
        for key in source.get("monitored_sites", []) if isinstance(source.get("monitored_sites"), list) else []:
            monitored_keys.add(norm(key))
        for key, value in source.get("sites", {}).items() if isinstance(source.get("sites"), dict) else []:
            if isinstance(value, dict) and (value.get("monitored") or value.get("classification") == "monitored"):
                monitored_keys.add(norm(key))
    for key in monitored_keys:
        merge_site(registry, key, "monitoring_state")
        row = registry[key]
        row["classification"] = "monitored"
        row["is_monitored"] = True
        row["can_approve"] = False

    for item in admin_named.get("site_counts", []) if isinstance(admin_named, dict) else []:
        if isinstance(item, dict):
            key = item.get("site_key")
            merge_site(registry, key, "named_access", metrics={"named_access_count": item.get("named_access_count", 0)})

    sites: List[Dict[str, Any]] = []
    for key, row in sorted(registry.items()):
        row["sources"] = sorted(set(row.get("sources", [])))
        row.setdefault("site_url", site_url(key))
        row.setdefault("site_name", key)
        row.setdefault("aliases", [key, row["site_url"]])
        if row.get("classification") == "monitored":
            row["is_monitored"] = True
            row["can_approve"] = False
        else:
            row.setdefault("classification", "discovered")
            row.setdefault("is_monitored", False)
            row.setdefault("can_approve", True)
        sites.append(row)

    summary = {
        "total_sites": len(sites),
        "monitored_count": sum(1 for s in sites if s.get("is_monitored")),
        "discovered_count": sum(1 for s in sites if not s.get("is_monitored")),
        "pending_onboarding_count": sum(1 for s in sites if s.get("collector_onboarding_status") == "not_requested"),
        "ignored_count": sum(1 for s in sites if s.get("classification") == "ignored"),
    }
    return {
        "schema": "jom-site-registry-v4-runtime-consolidated",
        "generated_at_utc": now_utc(),
        "summary": summary,
        "policy": {
            "new_sites_default_status": "discovered",
            "estate_requires_monitored_status": True,
            "approval_triggers_oauth_onboarding_gate": True,
        },
        "sites": sites,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output", default="static/data/site_registry.json")
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    output = Path(args.output)
    if not output.is_absolute():
        output = project_root / output
    payload = build_registry(project_root)
    write_json(output, payload)
    print(json.dumps({"output": str(output), "summary": payload.get("summary")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
