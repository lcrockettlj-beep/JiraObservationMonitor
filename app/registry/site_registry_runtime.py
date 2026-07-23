from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

MONITORED_CONFIG = "config/monitored_sites.json"
REGISTRY_OUTPUT = "static/data/site_registry.json"
ONBOARDING_QUEUE = "reports/site_onboarding_queue.json"

APPROVED_OPERATIONAL_SITES = [
    {
        "site_key": "gli-delivery-tm",
        "site_name": "gli-delivery-tm",
        "site_url": "https://gli-delivery-tm.atlassian.net",
        "status": "monitored",
        "approved_by": "approved_operational_scope",
    },
    {
        "site_key": "gli-global-technology",
        "site_name": "gli-global-technology",
        "site_url": "https://gli-global-technology.atlassian.net",
        "status": "monitored",
        "approved_by": "approved_operational_scope",
    },
    {
        "site_key": "gli-it-project",
        "site_name": "gli-it-project",
        "site_url": "https://gli-it-project.atlassian.net",
        "status": "monitored",
        "approved_by": "approved_operational_scope",
    },
]

KNOWN_RESOURCE_OVERRIDES = {
    "5e39f28e-6ff4-44ff-82b7-d0746cee8db5": {
        "site_key": "gli-tracker",
        "site_name": "gli-tracker",
        "site_url": "https://gli-tracker.atlassian.net",
        "classification": "discovered",
        "reason": "Discovered by Atlassian Admin role assignments/billing; not part of monitored operational estate until approved.",
    }
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: Any = None) -> Any:
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def site_key_from_url(url: str) -> str:
    host = (url or "").strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    return host.replace(".atlassian.net", "") if host else ""


def normalise_url(url: str) -> str:
    return (url or "").strip().rstrip("/").lower()


def aliases(site: Dict[str, Any]) -> List[str]:
    values = []
    for value in [
        site.get("cloud_id"),
        normalise_url(str(site.get("site_url") or "")),
        str(site.get("site_key") or "").strip().lower(),
        site_key_from_url(str(site.get("site_url") or "")),
    ]:
        if value and value not in values:
            values.append(value)
    return values


def primary_identity(site: Dict[str, Any]) -> str:
    # Prefer site_key/url over cloud ID so named-access rows and runtime rows merge cleanly by operational site identity.
    return str(site.get("site_key") or site_key_from_url(str(site.get("site_url") or "")) or site.get("site_url") or site.get("cloud_id") or "").strip().lower()


def load_runtime_sites(project_root: Path) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for filename in ["latest_run_admin_enriched_pretty.json", "latest_run_admin_enriched.json", "latest_run_pretty.json", "latest_run.json"]:
        payload = read_json(project_root / filename, {})
        sites = payload.get("sites") if isinstance(payload, dict) else []
        if not isinstance(sites, list) or not sites:
            continue
        for site in sites:
            if not isinstance(site, dict):
                continue
            url = normalise_url(str(site.get("url") or site.get("site_url") or ""))
            cloud_id = str(site.get("cloud_id") or "").strip()
            key = str(site.get("site_key") or site.get("site") or site_key_from_url(url) or cloud_id).strip()
            if key or cloud_id or url:
                output.append({
                    "site_key": key,
                    "site_name": str(site.get("site_name") or site.get("name") or key),
                    "site_url": url,
                    "cloud_id": cloud_id,
                    "source": "runtime_collector",
                })
        if output:
            return output
    return output


def load_named_sites(project_root: Path) -> List[Dict[str, Any]]:
    payload = read_json(project_root / "static" / "data" / "live_named_access_contract", {})
    rows = []
    for row in payload.get("site_counts", []) if isinstance(payload.get("site_counts"), list) else []:
        key = str(row.get("site_key") or "").strip()
        cloud_id = key if "-" in key and len(key) > 20 else ""
        override = KNOWN_RESOURCE_OVERRIDES.get(cloud_id, {})
        site_url = normalise_url(str(override.get("site_url") or ""))
        rows.append({
            "site_key": override.get("site_key") or key,
            "site_name": override.get("site_name") or key,
            "site_url": site_url,
            "cloud_id": cloud_id,
            "source": "admin_named_access",
            "named_access_count": int(row.get("named_access_count") or 0),
            "reason": override.get("reason", ""),
        })
    return rows


def load_product_sites(project_root: Path) -> List[Dict[str, Any]]:
    payload = read_json(project_root / "static" / "data" / "estate_product_access.json", {})
    rows = []
    for row in payload.get("sites", []) if isinstance(payload.get("sites"), list) else []:
        if not isinstance(row, dict):
            continue
        url = normalise_url(str(row.get("site_url") or row.get("url") or ""))
        key = str(row.get("site_key") or site_key_from_url(url) or "").strip()
        cloud_id = str(row.get("cloud_id") or "").strip()
        if key or cloud_id or url:
            rows.append({
                "site_key": key,
                "site_name": str(row.get("site_name") or key or cloud_id),
                "site_url": url,
                "cloud_id": cloud_id,
                "source": "estate_product_access",
                "jira_product_user_count": int(row.get("jira_product_user_count") or row.get("user_count") or 0),
            })
    return rows


def approved_config() -> Dict[str, Any]:
    ts = now_utc()
    monitored = []
    for site in APPROVED_OPERATIONAL_SITES:
        monitored.append({**site, "approved_at_utc": ts})
    return {
        "schema": "jom-monitored-sites-v2",
        "updated_at_utc": ts,
        "policy": {
            "home_shows_discovered_sites": True,
            "estate_requires_monitored_status": True,
            "approval_triggers_onboarding_queue": True,
            "new_sites_default_status": "discovered",
        },
        "monitored_sites": monitored,
        "ignored_sites": [],
    }


def reset_to_approved_scope(project_root: Path) -> Dict[str, Any]:
    config = approved_config()
    write_json(project_root / MONITORED_CONFIG, config)
    return config


def load_config(project_root: Path) -> Dict[str, Any]:
    path = project_root / MONITORED_CONFIG
    config = read_json(path, None)
    if not isinstance(config, dict) or "monitored_sites" not in config:
        config = approved_config()
        write_json(path, config)
    return config


def index_config_sites(sites: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for site in sites:
        if not isinstance(site, dict):
            continue
        for a in aliases(site):
            index[a] = site
    return index


def queue_onboarding(project_root: Path, entry: Dict[str, Any], requested_by: str) -> Dict[str, Any]:
    queue_path = project_root / ONBOARDING_QUEUE
    queue = read_json(queue_path, {"schema": "jom-site-onboarding-queue-v1", "requests": []})
    requests = queue.get("requests") if isinstance(queue.get("requests"), list) else []
    entry_aliases = set(aliases(entry))
    requests = [r for r in requests if not entry_aliases.intersection(set(aliases(r)))]
    requests.append({
        **entry,
        "requested_at_utc": now_utc(),
        "requested_by": requested_by,
        "status": "pending_collector_validation",
        "required_next_step": "Validate auth/API coverage and add this site to collector configuration before reporting full metrics.",
    })
    queue["requests"] = requests
    queue["updated_at_utc"] = now_utc()
    write_json(queue_path, queue)
    return queue


def build_registry(project_root: Path) -> Dict[str, Any]:
    config = load_config(project_root)
    monitored_index = index_config_sites(config.get("monitored_sites", []))
    ignored_index = index_config_sites(config.get("ignored_sites", []))
    queue = read_json(project_root / ONBOARDING_QUEUE, {"requests": []})
    queued_index = index_config_sites(queue.get("requests", []))

    merged: Dict[str, Dict[str, Any]] = {}
    alias_to_primary: Dict[str, str] = {}

    def find_primary(record: Dict[str, Any]) -> str:
        for a in aliases(record):
            if a in alias_to_primary:
                return alias_to_primary[a]
        p = primary_identity(record)
        for a in aliases(record):
            alias_to_primary[a] = p
        return p

    for source, records in [("runtime", load_runtime_sites(project_root)), ("product_access", load_product_sites(project_root)), ("named_access", load_named_sites(project_root))]:
        for record in records:
            primary = find_primary(record)
            if not primary:
                continue
            item = merged.setdefault(primary, {
                "cloud_id": record.get("cloud_id", ""),
                "site_key": record.get("site_key", ""),
                "site_name": record.get("site_name", ""),
                "site_url": record.get("site_url", ""),
                "sources": [],
                "metrics": {},
                "aliases": [],
            })
            for a in aliases(record):
                if a not in item["aliases"]:
                    item["aliases"].append(a)
                    alias_to_primary[a] = primary
            for field in ["cloud_id", "site_key", "site_name", "site_url", "reason"]:
                if not item.get(field) and record.get(field):
                    item[field] = record.get(field)
            if source not in item["sources"]:
                item["sources"].append(source)
            if record.get("named_access_count") is not None:
                item["metrics"]["named_access_count"] = record.get("named_access_count")
            if record.get("jira_product_user_count") is not None:
                item["metrics"]["jira_product_user_count"] = record.get("jira_product_user_count")

    for item in merged.values():
        item_aliases = aliases(item) + item.get("aliases", [])
        monitored_match = next((monitored_index[a] for a in item_aliases if a in monitored_index), None)
        ignored_match = next((ignored_index[a] for a in item_aliases if a in ignored_index), None)
        queued_match = next((queued_index[a] for a in item_aliases if a in queued_index), None)
        if monitored_match:
            item["classification"] = "monitored"
            item["approved_at_utc"] = monitored_match.get("approved_at_utc")
            item["collector_onboarding_status"] = queued_match.get("status") if queued_match else "validated_or_existing"
        elif ignored_match:
            item["classification"] = "ignored"
            item["collector_onboarding_status"] = "not_required"
        else:
            item["classification"] = "discovered"
            item["collector_onboarding_status"] = "not_requested"
        item["is_monitored"] = item["classification"] == "monitored"
        item["can_approve"] = item["classification"] in ["discovered", "ignored"]

    sites = sorted(merged.values(), key=lambda s: (0 if s.get("classification") == "monitored" else 1, str(s.get("site_key") or s.get("site_url") or s.get("cloud_id")).lower()))
    registry = {
        "schema": "jom-site-registry-v3-scope-merged",
        "generated_at_utc": now_utc(),
        "policy": config.get("policy", {}),
        "summary": {
            "total_sites": len(sites),
            "monitored_count": sum(1 for s in sites if s.get("classification") == "monitored"),
            "discovered_count": sum(1 for s in sites if s.get("classification") == "discovered"),
            "ignored_count": sum(1 for s in sites if s.get("classification") == "ignored"),
            "pending_onboarding_count": sum(1 for s in sites if s.get("collector_onboarding_status") == "pending_collector_validation"),
        },
        "sites": sites,
    }
    write_json(project_root / REGISTRY_OUTPUT, registry)
    return registry


def approve_site(project_root: Path, payload: Dict[str, Any], approved_by: str = "jom_admin") -> Dict[str, Any]:
    config = load_config(project_root)
    site_url = normalise_url(str(payload.get("site_url") or ""))
    cloud_id = str(payload.get("cloud_id") or "").strip()
    site_key = str(payload.get("site_key") or site_key_from_url(site_url) or cloud_id).strip()
    entry = {
        "site_key": site_key,
        "site_name": str(payload.get("site_name") or site_key),
        "site_url": site_url,
        "cloud_id": cloud_id,
        "status": "monitored",
        "approved_at_utc": now_utc(),
        "approved_by": approved_by,
    }
    entry_aliases = set(aliases(entry))
    config["monitored_sites"] = [s for s in config.get("monitored_sites", []) if not entry_aliases.intersection(set(aliases(s)))]
    config["ignored_sites"] = [s for s in config.get("ignored_sites", []) if not entry_aliases.intersection(set(aliases(s)))]
    config["monitored_sites"].append(entry)
    config["updated_at_utc"] = now_utc()
    write_json(project_root / MONITORED_CONFIG, config)
    queue_onboarding(project_root, entry, approved_by)
    return build_registry(project_root)


def ignore_site(project_root: Path, payload: Dict[str, Any], ignored_by: str = "jom_admin") -> Dict[str, Any]:
    config = load_config(project_root)
    site_url = normalise_url(str(payload.get("site_url") or ""))
    cloud_id = str(payload.get("cloud_id") or "").strip()
    site_key = str(payload.get("site_key") or site_key_from_url(site_url) or cloud_id).strip()
    entry = {
        "site_key": site_key,
        "site_name": str(payload.get("site_name") or site_key),
        "site_url": site_url,
        "cloud_id": cloud_id,
        "status": "ignored",
        "ignored_at_utc": now_utc(),
        "ignored_by": ignored_by,
        "reason": str(payload.get("reason") or "Manually ignored from JOM monitoring scope"),
    }
    entry_aliases = set(aliases(entry))
    config["monitored_sites"] = [s for s in config.get("monitored_sites", []) if not entry_aliases.intersection(set(aliases(s)))]
    config["ignored_sites"] = [s for s in config.get("ignored_sites", []) if not entry_aliases.intersection(set(aliases(s)))]
    config["ignored_sites"].append(entry)
    config["updated_at_utc"] = now_utc()
    write_json(project_root / MONITORED_CONFIG, config)
    return build_registry(project_root)

def unmonitor_site(project_root: Path, payload: Dict[str, Any], removed_by: str = "jom_admin") -> Dict[str, Any]:
    """
    Remove a site from monitored scope without ignoring it.

    If the site is still present in runtime/product/named discovery signals it will
    reappear as classification == discovered on the next registry build.
    """
    config = load_config(project_root)
    site_url = normalise_url(str(payload.get("site_url") or ""))
    cloud_id = str(payload.get("cloud_id") or "").strip()
    site_key = str(payload.get("site_key") or site_key_from_url(site_url) or cloud_id).strip()
    entry = {
        "site_key": site_key,
        "site_name": str(payload.get("site_name") or site_key),
        "site_url": site_url,
        "cloud_id": cloud_id,
    }
    entry_aliases = set(aliases(entry))

    config["monitored_sites"] = [
        s for s in config.get("monitored_sites", [])
        if not entry_aliases.intersection(set(aliases(s)))
    ]
    # Deliberately do not add to ignored_sites. The rediscovery path should put
    # the site back into discovered if runtime/product/named signals still see it.
    config["updated_at_utc"] = now_utc()
    write_json(project_root / MONITORED_CONFIG, config)

    queue_path = project_root / ONBOARDING_QUEUE
    queue = read_json(queue_path, {"schema": "jom-site-onboarding-queue-v1", "requests": []})
    requests = queue.get("requests") if isinstance(queue.get("requests"), list) else []
    queue["requests"] = [
        r for r in requests
        if not entry_aliases.intersection(set(aliases(r)))
    ]
    queue["updated_at_utc"] = now_utc()
    write_json(queue_path, queue)

    return build_registry(project_root)

