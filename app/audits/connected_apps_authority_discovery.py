from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "reports" / "connected_apps_authority_discovery_v1.json"
SENSITIVE_HEADERS = {
    "authorization", "cookie", "set-cookie", "x-api-key", "x-csrf-token",
    "x-xsrf-token", "x-atlassian-token", "proxy-authorization",
}
SENSITIVE_QUERY = {
    "token", "access_token", "refresh_token", "code", "state", "session",
    "jwt", "secret", "api_key", "apikey", "password",
}
APP_TERMS = (
    "app", "apps", "addon", "add-on", "plugin", "plugins", "marketplace",
    "connected-apps", "connectedapps", "installation", "installations",
    "entitlement", "entitlements", "offering", "license", "licence",
)
APP_SHAPE_TERMS = {
    "appkey", "app_key", "addonkey", "addon_key", "plugin_key", "pluginkey",
    "vendor", "installed", "enabled", "userinstalled", "useslicensing",
    "entitlementid", "offeringkey", "producttype", "hostingtype",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:12]


def safe_path(url: str) -> dict[str, Any]:
    parsed = urlsplit(url)
    query_names = sorted({key for key, _ in parse_qsl(parsed.query, keep_blank_values=True) if key.lower() not in SENSITIVE_QUERY})
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "path": parsed.path,
        "query_parameter_names": query_names,
        "url_hash": digest(url),
    }


def safe_headers(rows: Any) -> dict[str, Any]:
    names = []
    redacted_count = 0
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip().lower()
        if not name:
            continue
        if name in SENSITIVE_HEADERS:
            redacted_count += 1
        else:
            names.append(name)
    return {"header_names": sorted(set(names)), "sensitive_header_count": redacted_count}


def json_shape(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(key): json_shape(item, depth + 1) for key, item in list(value.items())[:60]}
    if isinstance(value, list):
        return {"type": "list", "count": len(value), "item_shape": json_shape(value[0], depth + 1) if value else None}
    return type(value).__name__


def response_shape(response: dict[str, Any]) -> dict[str, Any]:
    content = response.get("content") if isinstance(response.get("content"), dict) else {}
    text = content.get("text")
    encoding = content.get("encoding")
    mime = str(content.get("mimeType") or "")
    result = {
        "mime_type": mime,
        "body_size": response.get("bodySize"),
        "raw_body_stored": False,
        "shape": None,
        "parse_state": "body_unavailable",
    }
    if not isinstance(text, str) or not text:
        return result
    if str(encoding or "").lower() == "base64":
        result["parse_state"] = "base64_body_not_decoded"
        return result
    if "json" not in mime.lower() and not text.lstrip().startswith(("{", "[")):
        result["parse_state"] = "non_json_body_not_stored"
        return result
    try:
        result["shape"] = json_shape(json.loads(text))
        result["parse_state"] = "json_shape_extracted"
    except Exception:
        result["parse_state"] = "invalid_json_body_not_stored"
    return result


def shape_keys(value: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            out.add(str(key).lower())
            out.update(shape_keys(item))
    elif isinstance(value, list):
        for item in value:
            out.update(shape_keys(item))
    return out


def classify_candidate(record: dict[str, Any]) -> dict[str, Any]:
    path = str(record.get("request", {}).get("path") or "").lower()
    host = str(record.get("request", {}).get("host") or "").lower()
    keys = shape_keys(record.get("response", {}).get("shape"))
    path_signal = any(term in path for term in APP_TERMS)
    shape_matches = sorted(keys.intersection(APP_SHAPE_TERMS))
    first_party = host.endswith("atlassian.com") or host.endswith("atlassian.net")
    score = (2 if path_signal else 0) + min(3, len(shape_matches)) + (1 if first_party else 0)
    return {
        "candidate": score >= 3,
        "score": score,
        "path_signal": path_signal,
        "shape_key_signals": shape_matches,
        "first_party_host": first_party,
        "classification": "candidate_connected_apps_endpoint" if score >= 3 else "non_candidate",
    }


def analyse_har(har_path: Path, output_path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    payload = json.loads(har_path.read_text(encoding="utf-8-sig"))
    entries = (((payload.get("log") or {}).get("entries")) if isinstance(payload, dict) else None) or []
    records = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        request = entry.get("request") if isinstance(entry.get("request"), dict) else {}
        response = entry.get("response") if isinstance(entry.get("response"), dict) else {}
        url = safe_path(str(request.get("url") or ""))
        rec = {
            "entry_index": index,
            "started_at": entry.get("startedDateTime"),
            "request": {
                "method": request.get("method"),
                **url,
                **safe_headers(request.get("headers")),
                "post_data_present": bool(request.get("postData")),
                "post_data_stored": False,
            },
            "response": {
                "status": response.get("status"),
                "status_text": response.get("statusText"),
                **safe_headers(response.get("headers")),
                **response_shape(response),
            },
        }
        rec["candidate_assessment"] = classify_candidate(rec)
        records.append(rec)
    candidates = [row for row in records if row["candidate_assessment"]["candidate"]]
    result = {
        "schema": "jom-connected-apps-authority-discovery-v1",
        "generated_at_utc": now_utc(),
        "status": "candidate_endpoints_found" if candidates else "no_candidate_endpoint_found",
        "source": {"type": "operator_supplied_browser_har", "filename": har_path.name, "sha256": hashlib.sha256(har_path.read_bytes()).hexdigest()},
        "privacy": {
            "raw_har_stored": False,
            "raw_request_bodies_stored": False,
            "raw_response_bodies_stored": False,
            "header_values_stored": False,
            "query_values_stored": False,
            "cookies_stored": False,
            "tokens_stored": False,
        },
        "summary": {
            "entry_count": len(records),
            "candidate_endpoint_count": len(candidates),
            "status_counts": dict(Counter(str(row["response"].get("status")) for row in records)),
            "candidate_hosts": sorted({row["request"].get("host") for row in candidates if row["request"].get("host")}),
        },
        "candidates": candidates,
        "all_requests": records,
        "decision": {
            "connected_apps_authority_proven": False,
            "marketplace_app_installation_authority_proven": False,
            "safe_to_publish_marketplace_apps": False,
            "reason": "A HAR candidate is discovery evidence only. Authentication model, site association, pagination, installed/enabled semantics, first-party supportability and completeness must be validated before publishing.",
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Sanitize and analyse an Atlassian Connected Apps HAR export.")
    parser.add_argument("har", help="Path to operator-supplied HAR file")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Privacy-safe JSON evidence output")
    args = parser.parse_args()
    result = analyse_har(Path(args.har), Path(args.output))
    print(json.dumps({"status": result["status"], "summary": result["summary"], "privacy": result["privacy"], "decision": result["decision"], "output": args.output}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
