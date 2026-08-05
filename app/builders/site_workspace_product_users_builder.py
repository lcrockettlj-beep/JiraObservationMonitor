from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "runtime" / "data"


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(filename: str, default: Any) -> Any:
    path = DATA_DIR / filename
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"_read_error": str(exc), "_file": filename}


def _norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("http") and ".atlassian.net" in text:
        text = text.split("//", 1)[-1].split(".atlassian.net", 1)[0]
    return text.rstrip("/")


def _site_key(row: Dict[str, Any]) -> str:
    for field in ("site_key", "key", "site_name", "name", "site_url", "url", "cloud_id"):
        value = row.get(field)
        if value:
            key = _norm(value)
            if key:
                return key
    return ""


def _is_monitored(row: Dict[str, Any]) -> bool:
    state = _norm(row.get("classification") or row.get("lifecycle") or row.get("collector_onboarding_status") or row.get("status"))
    return bool(
        row.get("is_monitored") is True
        or row.get("monitored") is True
        or row.get("approved_monitored") is True
        or state in {"monitored", "monitoring_enabled"}
    )


def _int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _monitored_registry_sites(registry: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = registry.get("sites") if isinstance(registry.get("sites"), list) else []
    out: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not _is_monitored(row):
            continue
        key = _site_key(row)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _product_site_map(product: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows = product.get("sites") if isinstance(product.get("sites"), list) else []
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = _site_key(row)
        if key:
            out[key] = row
    return out


def _roles_for_monitored_sites(product: Dict[str, Any], monitored_keys: set[str]) -> List[Dict[str, Any]]:
    rows = product.get("roles") if isinstance(product.get("roles"), list) else []
    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = _site_key(row)
        if key in monitored_keys:
            out.append(row)
    return out


def build_site_workspace_product_users(project_root: Path | None = None) -> Dict[str, Any]:
    """Build Site Workspace product-user totals from monitored registry sites only.

    Source policy:
    - site_registry.json decides the monitored estate scope.
    - estate_product_access.json provides Jira product-user counts.
    - no retired runtime records, no static/data, no inferred values.
    """
    root = project_root or ROOT
    global DATA_DIR
    DATA_DIR = root / "runtime" / "data"

    registry = _read_json("site_registry.json", {})
    product = _read_json("estate_product_access.json", {})

    monitored_sites = _monitored_registry_sites(registry if isinstance(registry, dict) else {})
    product_sites = _product_site_map(product if isinstance(product, dict) else {})
    monitored_keys = {_site_key(site) for site in monitored_sites if _site_key(site)}

    site_rows: List[Dict[str, Any]] = []
    missing_count = 0
    total_users = 0
    total_seat_limit = 0
    total_remaining = 0

    for site in monitored_sites:
        key = _site_key(site)
        product_row = product_sites.get(key)
        if isinstance(product_row, dict):
            users = _int(product_row.get("jira_product_user_count"), 0)
            seat_limit = _int(product_row.get("jira_product_seat_limit"), 0)
            remaining = _int(product_row.get("jira_product_remaining_seats"), 0)
            role_count = _int(product_row.get("jira_role_count"), 0)
            status = str(product_row.get("status") or "ok")
            source_available = True
        else:
            users = None
            seat_limit = None
            remaining = None
            role_count = None
            status = "unavailable"
            source_available = False
            missing_count += 1
        total_users += users if isinstance(users, int) else 0
        total_seat_limit += seat_limit if isinstance(seat_limit, int) else 0
        total_remaining += remaining if isinstance(remaining, int) else 0
        site_rows.append({
            "site_key": key,
            "site_name": site.get("site_name") or site.get("name") or key,
            "site_url": site.get("site_url") or site.get("url") or "",
            "cloud_id": site.get("cloud_id"),
            "product_users": users,
            "seat_limit": seat_limit,
            "remaining_seats": remaining,
            "role_count": role_count,
            "status": status,
            "source_available": source_available,
            "source": "runtime/data/estate_product_access.json" if source_available else "unavailable",
        })

    site_rows.sort(key=lambda row: (-1 if row.get("product_users") is None else -int(row.get("product_users") or 0), str(row.get("site_key") or "")))
    role_rows = _roles_for_monitored_sites(product if isinstance(product, dict) else {}, monitored_keys)
    product_summary = product.get("summary") if isinstance(product, dict) and isinstance(product.get("summary"), dict) else {}

    available = bool(monitored_sites) and missing_count < len(monitored_sites)
    status = "ok" if missing_count == 0 and available else "partial" if available else "unavailable"

    return {
        "schema": "jom-site-workspace-product-users-v1",
        "generated_at_utc": _now_utc(),
        "status": status,
        "available": available,
        "metric": {
            "label": "Product users",
            "total": total_users if available else None,
            "display": f"{total_users:,}" if available else "Unavailable",
        },
        "summary": {
            "monitored_site_count": len(monitored_sites),
            "matched_product_site_count": len(monitored_sites) - missing_count,
            "missing_product_site_count": missing_count,
            "total_product_users": total_users if available else None,
            "total_seat_limit": total_seat_limit if available else None,
            "total_remaining_seats": total_remaining if available else None,
            "role_row_count": len(role_rows),
            "source_total_jira_product_user_count_all_accessible_resources": product_summary.get("total_jira_product_user_count"),
        },
        "sites": site_rows,
        "roles": role_rows,
        "source_policy": {
            "scope_truth": "runtime/data/site_registry.json monitored sites only",
            "metric_truth": "runtime/data/estate_product_access.json Jira application-role user counts",
            "static_fallback_used": False,
            "retired_runtime_record_used": False,
            "unmatched_sites_are_not_guessed": True,
        },
        "source_files": {
            "site_registry": "runtime/data/site_registry.json",
            "estate_product_access": "runtime/data/estate_product_access.json",
        },
        "notes": [
            "This metric is estate-wide across monitored sites only.",
            "Product users are Jira product/application role counts, not named user-footprint truth.",
            "Unavailable site values are not converted to zero.",
        ],
    }
