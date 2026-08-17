from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.builders.estate_admin_contacts import (
    ROOT,
    collect_role_assignments,
    directory_ids_from_admin,
    load_env,
    now_utc,
    sample_account_ids,
    write_json,
)

MAPPING_OUT = ROOT / "runtime" / "data" / "estate_site_resource_mapping_v1.json"
CONTACTS_OUT = ROOT / "runtime" / "data" / "estate_admin_contacts_v1.json"
STATUS_OUT = ROOT / "runtime" / "data" / "estate_resource_authority_refresh_status_v1.json"
ACCEPTED_PRODUCTS = {"jira-software", "confluence"}
ADMIN_MARKERS = ("admin", "administrator", "site-admin", "site_admin", "org-admin")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def current_sites(root: Path = ROOT) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for filename in (
        "estate_discovery_authority_v1.json",
        "estate_admin_site_inventory_v1.json",
        "site_registry.json",
    ):
        payload = read_json(root / "runtime" / "data" / filename, {}) or {}
        for row in payload.get("sites", []) if isinstance(payload, dict) else []:
            if not isinstance(row, dict):
                continue
            key = norm(row.get("site_key") or row.get("key") or row.get("name"))
            if not key:
                continue
            merged = by_key.setdefault(key, {"site_key": key})
            for field, value in row.items():
                if value not in (None, "", [], {}):
                    merged[field] = value
    output = []
    for key, row in sorted(by_key.items()):
        state = norm(row.get("lifecycle") or row.get("classification") or row.get("collector_onboarding_status") or row.get("status"))
        monitored = bool(row.get("is_monitored") is True or row.get("monitored") is True or row.get("approved_monitored") is True or state in {"monitored", "monitoring_enabled"})
        if monitored and row.get("cloud_id"):
            output.append({"site_key": key, "cloud_id": str(row.get("cloud_id")), "monitored": True})
    return output


def role_product(role: dict[str, Any]) -> str:
    owner = norm(role.get("resourceOwner"))
    if owner == "jira-software":
        return "jira-software"
    if owner == "confluence":
        return "confluence"
    return ""


def role_is_admin(role: dict[str, Any]) -> bool:
    text = json.dumps({"roleAssignments": role.get("roleAssignments"), "roles": role.get("roles")}, ensure_ascii=False).lower()
    return any(marker in text for marker in ADMIN_MARKERS)


ARI_SITE_RESOURCE = re.compile(r"^ari:cloud:([a-z0-9-]+)::site/([0-9a-fA-F-]{36})$")


def parse_site_resource(role: dict[str, Any]) -> tuple[str, str]:
    """Return product owner and exact site cloud ID from a site-scoped Atlassian ARI."""
    resource_id = str(role.get("resourceId") or "").strip()
    match = ARI_SITE_RESOURCE.fullmatch(resource_id)
    if not match:
        return "", ""
    return norm(match.group(1)), norm(match.group(2))


def match_sites(role: dict[str, Any], sites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    _owner, ari_cloud_id = parse_site_resource(role)
    if not ari_cloud_id:
        return []
    return [site for site in sites if norm(site.get("cloud_id")) == ari_cloud_id]


def build_authority(assignments: list[dict[str, Any]], users_seen: list[dict[str, Any]], sites: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    ambiguous_rows = 0
    unmatched_product_rows = 0
    for role in assignments:
        if not isinstance(role, dict):
            continue
        product = role_product(role)
        ari_owner, _ari_cloud_id = parse_site_resource(role)
        resource_id = str(role.get("resourceId") or "").strip()
        if product not in ACCEPTED_PRODUCTS or ari_owner != product or not resource_id:
            continue
        matched = match_sites(role, sites)
        if len(matched) != 1:
            ambiguous_rows += 1 if len(matched) > 1 else 0
            unmatched_product_rows += 1 if not matched else 0
            continue
        candidates[(matched[0]["site_key"], product, resource_id)].append(role)

    mappings = []
    resources_by_site_product: dict[tuple[str, str], list[str]] = defaultdict(list)
    for (site_key, product, resource_id), rows in sorted(candidates.items()):
        resources_by_site_product[(site_key, product)].append(resource_id)
        mappings.append({
            "site_key": site_key,
            "product": product,
            "resource_id": resource_id,
            "confidence": "high",
            "reason": "site-scoped Atlassian ARI parsed successfully; ARI product owner matched resourceOwner and ARI site UUID exactly matched one current monitored tenant cloud_id",
            "evidence_rows": len(rows),
        })

    user_by_id = {str(row.get("account_id")): row for row in users_seen if isinstance(row, dict) and row.get("account_id")}
    contacts = []
    seen = set()
    for role in assignments:
        if not isinstance(role, dict) or not role_is_admin(role):
            continue
        product = role_product(role)
        ari_owner, _ari_cloud_id = parse_site_resource(role)
        resource_id = str(role.get("resourceId") or "").strip()
        matched = match_sites(role, sites)
        if product not in ACCEPTED_PRODUCTS or ari_owner != product or not resource_id or len(matched) != 1:
            continue
        site_key = matched[0]["site_key"]
        if resource_id not in resources_by_site_product.get((site_key, product), []):
            continue
        account_id = str(role.get("_account_id") or "")
        directory_id = str(role.get("_directory_id") or "")
        dedupe = (site_key, product, resource_id, account_id, directory_id)
        if dedupe in seen:
            continue
        seen.add(dedupe)
        user = user_by_id.get(account_id, {})
        contacts.append({
            "site_key": site_key,
            "product": product,
            "resource_id": resource_id,
            "account_id": account_id or None,
            "directory_id": directory_id or None,
            "display_name": user.get("display_name"),
            "email": user.get("email"),
            "role_source": "atlassian_admin_v2_user_role_assignments",
            "verification": "live_role_assignment_matched_current_tenant_cloud_identity",
            "mapping_confidence": "high",
            "mapping_reason": "site-scoped Atlassian ARI product and site UUID passed exact current-tenant matching gates",
        })

    mapped_site_keys = sorted({row["site_key"] for row in mappings})
    mapping_payload = {
        "schema": "jom-estate-site-resource-mapping-v2",
        "generated_at_utc": now_utc(),
        "status": "mapped" if mappings else "unavailable",
        "safe_to_populate_contacts": bool(mappings),
        "fabricated_mappings": False,
        "mappings": mappings,
        "source": "live_atlassian_admin_v2_role_assignments_current_tenant_cloud_identity",
        "summary": {
            "monitored_site_count": len(sites),
            "mapped_site_count": len(mapped_site_keys),
            "mapping_count": len(mappings),
            "ambiguous_role_rows": ambiguous_rows,
            "unmatched_accepted_product_rows": unmatched_product_rows,
        },
    }
    contacts_payload = {
        "schema": "jom-estate-admin-contacts-v2",
        "generated_at_utc": now_utc(),
        "status": "live_mapped" if contacts else "available_no_contacts_mapped",
        "contacts": contacts,
        "reason": "Live role assignments collected and applied to current safe site-resource mappings." if contacts else "No administrative assignments passed the current safe mapping gates.",
        "fabricated_contacts": False,
        "source": "atlassian_admin_v2_user_role_assignments_with_current_tenant_cloud_identity_mapping",
        "summary": {
            "known_site_count": len(sites),
            "safe_mapping_count": len(mappings),
            "mapped_site_count": len(mapped_site_keys),
            "contact_count": len(contacts),
            "role_rows_inspected": len(assignments),
        },
    }
    return mapping_payload, contacts_payload


def refresh_estate_resource_authority(root: Path | None = None, write_output: bool = True) -> dict[str, Any]:
    root = root or ROOT
    env = load_env(root)
    org_id = (env.get("ATLASSIAN_ADMIN_ORG_ID") or env.get("ATLASSIAN_ORG_ID") or "").strip()
    token = (env.get("ATLASSIAN_ADMIN_API_KEY") or env.get("ATLASSIAN_ADMIN_TOKEN") or "").strip()
    if not org_id or not token:
        return {"status": "unavailable", "reason": "Atlassian Admin organisation ID and API key are required.", "generated_at_utc": now_utc()}
    sites = current_sites(root)
    directory_ids, directory_diagnostics = directory_ids_from_admin(org_id, token)
    assignments, users_seen, probes = collect_role_assignments(org_id, token, directory_ids, sample_account_ids(root, 20))
    mapping, contacts = build_authority(assignments, users_seen, sites)
    status = {
        "schema": "jom-estate-resource-authority-refresh-status-v1",
        "generated_at_utc": now_utc(),
        "status": "ok" if (
            mapping.get("status") == "mapped"
            and mapping.get("summary", {}).get("mapped_site_count") == len(sites)
            and mapping.get("summary", {}).get("ambiguous_role_rows") == 0
            and sum(1 for p in probes if not p.get("ok") and p.get("status") != 404) == 0
        ) else "review",
        "summary": {
            "monitored_site_count": len(sites),
            "assignment_rows": len(assignments),
            "mapped_site_count": mapping.get("summary", {}).get("mapped_site_count"),
            "mapping_count": mapping.get("summary", {}).get("mapping_count"),
            "contact_count": contacts.get("summary", {}).get("contact_count"),
            "successful_role_probe_count": sum(1 for p in probes if p.get("endpoint") == "role_assignments" and p.get("ok")),
            "not_found_probe_count": sum(1 for p in probes if p.get("status") == 404),
            "unexpected_failed_probe_count": sum(1 for p in probes if not p.get("ok") and p.get("status") != 404),
        },
        "privacy": {"personal_records_returned": False, "resource_ids_returned": False, "probe_account_ids_redacted": True},
        "directory_discovery": [{"name": x.get("name"), "ok": x.get("ok"), "status": x.get("status"), "row_count": x.get("row_count")} for x in directory_diagnostics],
    }
    if write_output:
        write_json(root / "runtime" / "data" / "estate_site_resource_mapping_v1.json", mapping)
        write_json(root / "runtime" / "data" / "estate_admin_contacts_v1.json", contacts)
        write_json(root / "runtime" / "data" / "estate_resource_authority_refresh_status_v1.json", status)
    return {"status": status, "mapping": mapping, "contacts": contacts}


def main() -> int:
    result = refresh_estate_resource_authority()
    print(json.dumps(result.get("status", {}), indent=2))
    return 0 if result.get("status", {}).get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
