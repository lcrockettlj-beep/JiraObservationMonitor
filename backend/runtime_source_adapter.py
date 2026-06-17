"""
backend/runtime_source_adapter.py

Step 4.0 – Preferred Runtime Source Adapter
-------------------------------------------
Reads the newest available live/runtime collector payload first, and only
falls back elsewhere if no usable runtime payload is present.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import glob
import json


RUNTIME_CANDIDATE_PATTERNS = [
    "latest_run.json",
    "latest_run_safe_partial.json",
    "latest_run_pretty.json",
    "reports/latest_run.json",
    "reports/latest_run_safe_partial.json",
    "reports/latest_run_pretty.json",
    "latest_run*.json",
    "reports/latest_run*.json",
]


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return content if isinstance(content, dict) else None


def _candidate_paths(base_dir: Path) -> List[Path]:
    seen = set()
    results: List[Path] = []
    for pattern in RUNTIME_CANDIDATE_PATTERNS:
        for match in glob.glob(str(base_dir / pattern)):
            path = Path(match)
            key = str(path.resolve())
            if key not in seen and path.is_file():
                seen.add(key)
                results.append(path)
    results.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return results


def _payload_to_sites(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(payload.get("sites"), list):
        return [item for item in payload.get("sites", []) if isinstance(item, dict)]

    if isinstance(payload.get("site_summaries"), list):
        return [item for item in payload.get("site_summaries", []) if isinstance(item, dict)]

    site_map = payload.get("site_map")
    if isinstance(site_map, dict):
        rows: List[Dict[str, Any]] = []
        for site_key, value in site_map.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("site", site_key)
                row.setdefault("name", value.get("site_name") or site_key)
                rows.append(row)
        return rows

    collector_sites = payload.get("collector_sites")
    if isinstance(collector_sites, list):
        return [item for item in collector_sites if isinstance(item, dict)]

    return []


def _normalise_payload(payload: Dict[str, Any], source_file: str) -> Dict[str, Any]:
    data = dict(payload)
    sites = _payload_to_sites(payload)
    data["sites"] = sites
    data["estate"] = _safe_dict(payload.get("estate"))
    data["drilldowns"] = _safe_dict(payload.get("drilldowns"))
    data["org_product_breakdown"] = _safe_list(payload.get("org_product_breakdown"))
    data["users_export_breakdown"] = _safe_list(payload.get("users_export_breakdown"))

    source_label = f"Runtime payload: {source_file}"
    data.setdefault("users_source_file", source_label)
    data.setdefault("managed_source_file", source_label)
    data.setdefault("users_row_count", len(_safe_list(payload.get("users"))))
    data.setdefault("managed_row_count", len(_safe_list(payload.get("managed_accounts"))))
    data["source_mode"] = "runtime"
    data["source_file"] = source_file
    return data


def load_preferred_source_payload(base_dir: Path) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    for path in _candidate_paths(base_dir):
        payload = _read_json(path)
        if not payload:
            continue
        normalised = _normalise_payload(payload, path.name)
        has_sites = bool(normalised.get("sites"))
        has_estate = bool(normalised.get("estate"))
        has_drilldowns = bool(normalised.get("drilldowns"))
        if not (has_sites or has_estate or has_drilldowns):
            continue
        return normalised, {
            "mode": "runtime",
            "file": path.name,
            "path": str(path),
        }

    return None, {
        "mode": "csv",
        "file": None,
        "path": None,
    }
