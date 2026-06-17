"""
backend/intelligence_runtime.py

Step 3.1 Integration Runtime
----------------------------
Safe helper layer that wires `backend.intelligence_engine` into an existing
backend payload without forcing UI changes.

This file is intentionally additive:
- It does not mutate source input in place unless you choose to reuse result.
- It tolerates missing keys and missing engine import.
- It gives your routes/templates a stable structure to read from.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


DEFAULT_INTELLIGENCE_PAYLOAD = {
    "generated_at": None,
    "estate": {
        "sites_count": 0,
        "estate_risk_score": 0,
        "average_site_risk_score": 0,
        "top_risks": [],
        "risk_category": "Healthy",
    },
    "sites": [],
    "thresholds": {},
}


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any):
    return value if isinstance(value, list) else []


def _clone_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = _safe_dict(payload)
    clone = dict(source)
    clone["sites"] = list(_safe_list(source.get("sites")))
    return clone


def attach_intelligence_safe(payload: Optional[Dict[str, Any]], thresholds: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    Safe wrapper around backend.intelligence_engine.attach_intelligence.

    Returns a payload that always has an `intelligence` key.
    If engine import or processing fails, the original payload is preserved and
    a fallback empty intelligence block is attached.
    """
    cloned = _clone_payload(payload)

    try:
        from backend.intelligence_engine import attach_intelligence
        enriched = attach_intelligence(cloned, thresholds=thresholds)
        if not isinstance(enriched, dict):
            enriched = cloned
        if not isinstance(enriched.get("intelligence"), dict):
            enriched["intelligence"] = dict(DEFAULT_INTELLIGENCE_PAYLOAD)
        return enriched
    except Exception as exc:
        fallback = dict(cloned)
        fallback["intelligence"] = dict(DEFAULT_INTELLIGENCE_PAYLOAD)
        fallback["intelligence_error"] = str(exc)
        return fallback


def build_runtime_context(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Produces a stable context block that templates/routes can consume safely.
    """
    source = _safe_dict(payload)
    intelligence = _safe_dict(source.get("intelligence"))
    estate = _safe_dict(intelligence.get("estate"))
    sites = _safe_list(intelligence.get("sites"))

    return {
        "payload": source,
        "intelligence": intelligence if intelligence else dict(DEFAULT_INTELLIGENCE_PAYLOAD),
        "intelligence_estate": estate,
        "intelligence_sites": sites,
        "intelligence_top_risks": _safe_list(estate.get("top_risks")),
        "estate_risk_score": estate.get("estate_risk_score", 0),
        "estate_risk_category": estate.get("risk_category", "Healthy"),
        "sites_with_risks": [site for site in sites if isinstance(site, dict) and site.get("risk_count", 0) > 0],
    }


def enrich_context_with_intelligence(base_context: Optional[Dict[str, Any]], payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merges intelligence runtime keys into an existing template context.
    """
    context = _safe_dict(base_context).copy()
    context.update(build_runtime_context(payload))
    return context
