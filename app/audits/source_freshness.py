from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = PROJECT_ROOT / "runtime" / "data" / "source_freshness_audit.json"

# Canonical primary authority inventory. One unique key and one unique path per row.
SOURCES = [
    {"key":"site_registry","label":"Site Registry","path":"runtime/data/site_registry.json","timestamp_fields":["generated_at_utc"],"source_type":"RUNTIME_SCOPE","pages":["Home","Estate","Admin"],"connection_member":False,"authentication_member":False},
    {"key":"admin_truth_v2","label":"Admin Truth Layer v2","path":"runtime/data/admin_truth_v2.json","timestamp_fields":["generated_at_utc"],"source_type":"DERIVED_RUNTIME_AUTHORITY","pages":["Estate","Admin"],"connection_member":False,"authentication_member":True},
    {"key":"estate_product_access","label":"Estate Product Access","path":"runtime/data/estate_product_access.json","timestamp_fields":["generated_at_utc"],"source_type":"LIVE_COLLECTION","pages":["Estate"],"connection_member":True,"authentication_member":True},
    {"key":"estate_access_truth","label":"Estate Access Truth","path":"runtime/data/estate_access_truth.json","timestamp_fields":["generated_at_utc"],"source_type":"LIVE_COLLECTION","pages":["Estate"],"connection_member":True,"authentication_member":True},
    {"key":"estate_admin_contacts","label":"Estate Admin Contacts","path":"runtime/data/estate_admin_contacts_v1.json","timestamp_fields":["generated_at_utc"],"source_type":"DERIVED_RUNTIME_AUTHORITY","pages":["Estate","Admin"],"connection_member":False,"authentication_member":True},
    {"key":"estate_monitored_products","label":"Estate Monitored Products","path":"runtime/data/estate_monitored_product_authority_v1.json","timestamp_fields":["generated_at_utc"],"source_type":"DERIVED_RUNTIME_AUTHORITY","pages":["Estate","Admin"],"connection_member":False,"authentication_member":False},
    {"key":"named_site_access","label":"Named Site Access","path":"runtime/data/named_site_access_authority_v1.json","timestamp_fields":["generated_at_utc"],"source_type":"DERIVED_RUNTIME_AUTHORITY","pages":["Admin"],"connection_member":False,"authentication_member":True},
    {"key":"named_user_display_identity","label":"Named User Display Identity","path":"runtime/data/named_user_display_identity_v1.json","timestamp_fields":["generated_at_utc"],"source_type":"DERIVED_RUNTIME_AUTHORITY","pages":["Admin","Governance"],"connection_member":False,"authentication_member":True},
    {"key":"user_footprint","label":"User Footprint","path":"runtime/data/user_footprint.json","timestamp_fields":["generated_at_utc","created_at_utc","updated_at_utc"],"source_type":"DERIVED_RUNTIME_AUTHORITY","pages":["Estate","Admin"],"connection_member":False,"authentication_member":False},
    {"key":"users_access_actionable","label":"Users Access Actionable Drill-down","path":"runtime/data/users_access_actionable_drilldown_v1.json","timestamp_fields":["generated_at_utc"],"source_type":"DERIVED_RUNTIME_AUTHORITY","pages":["Admin"],"connection_member":False,"authentication_member":True},
    {"key":"verified_active_jira_users","label":"Verified Active Jira Users","path":"runtime/data/verified_active_jira_users_v1.json","timestamp_fields":["generated_at_utc"],"source_type":"LIVE_DERIVED_ACTIVITY_AUTHORITY","pages":["Admin"],"connection_member":False,"authentication_member":True},
    {"key":"project_inventory","label":"Project Inventory","path":"runtime/data/project_inventory_authority_v1.json","timestamp_fields":["generated_at_utc"],"source_type":"LIVE_COLLECTION","pages":["Governance"],"connection_member":True,"authentication_member":True},
    {"key":"project_governance_identity","label":"Project Governance Named Identity","path":"runtime/data/project_governance_named_identity_authority_v1.json","timestamp_fields":["generated_at_utc"],"source_type":"LIVE_DERIVED_AUTHORITY","pages":["Governance"],"connection_member":True,"authentication_member":True},
    {"key":"project_lead","label":"Project Lead Authority","path":"runtime/data/project_lead_authority_v1.json","timestamp_fields":["generated_at_utc"],"source_type":"DERIVED_RUNTIME_AUTHORITY","pages":["Governance"],"connection_member":False,"authentication_member":False},
    {"key":"project_owner","label":"Project Owner Authority","path":"runtime/data/project_owner_authority_v1.json","timestamp_fields":["generated_at_utc"],"source_type":"GOVERNANCE_DERIVED_AUTHORITY","pages":["Governance"],"connection_member":False,"authentication_member":False},
    {"key":"runtime_execution","label":"Runtime Execution","path":"runtime/data/runtime_execution_status.json","timestamp_fields":["generated_at_utc","last_finished_at_utc","last_started_at_utc"],"source_type":"RUNTIME_CONTRACT","pages":["Home","Estate","Admin","Runtime"],"connection_member":False,"authentication_member":False},
]

POLICY = {
    "current_hours": 24,
    "aging_hours": 72,
    "stale_after_hours": 72,
    "whole_platform_ok_requires_complete_coverage": True,
    "partial_review_is_not_healthy": True,
    "file_mtime_is_not_collection_time": True,
    "rule": "No timestamp means not trusted as current; missing files are explicit MISSING, never treated as zero.",
}

def now_utc(): return datetime.now(timezone.utc)
def iso(dt): return dt.isoformat().replace("+00:00","Z")
def parse(value):
    if not value: return None
    try: return datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone(timezone.utc)
    except Exception: return None

def read(path):
    try: return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception: return None

def classify(age, exists, timestamp_present):
    if not exists: return "MISSING"
    if not timestamp_present or age is None: return "UNKNOWN_TIMESTAMP"
    if age > POLICY["stale_after_hours"]: return "STALE"
    if age > POLICY["current_hours"]: return "AGING"
    return "CURRENT"

def contract_state(payload):
    if not isinstance(payload,dict): return "UNAVAILABLE"
    return str(payload.get("status") or payload.get("overall_status") or (payload.get("summary") or {}).get("overall_state") or "available").upper()

def main(project_root=None):
    root=Path(project_root).resolve() if project_root else PROJECT_ROOT
    now=now_utc(); rows=[]; counts={x:0 for x in ("CURRENT","AGING","STALE","MISSING","UNKNOWN_TIMESTAMP")}
    for src in SOURCES:
        path=root/src["path"]; exists=path.exists(); payload=read(path) if exists else None; field=None; value=None; parsed=None; error=None
        if isinstance(payload,dict):
            for candidate in src["timestamp_fields"]:
                raw=payload.get(candidate)
                if raw is not None and raw != "":
                    field=candidate; value=raw; parsed=parse(raw); break
        age=round((now-parsed).total_seconds()/3600,2) if parsed else None
        state=classify(age,exists,bool(value and parsed)); counts[state]+=1
        if value and not parsed: error="Timestamp present but not parseable as freshness evidence."
        rows.append({**src,"exists":exists,"freshness_state":state,"operator_label":state.replace("_"," "),"timestamp_field":field,"timestamp_value":value,"parsed_timestamp_utc":iso(parsed) if parsed else None,"age_hours":age,"declared_state":contract_state(payload),"error":error})
    keys=[x["key"] for x in SOURCES]; paths=[x["path"] for x in SOURCES]
    unique=len(keys)==len(set(keys)) and len(paths)==len(set(paths))
    complete=len(rows)==len(SOURCES) and all(x["exists"] for x in rows) and unique
    non_current=sum(v for k,v in counts.items() if k!="CURRENT")
    review_states=[x for x in rows if x["declared_state"] in {"PARTIAL","REVIEW","UNAVAILABLE","ERROR","FAILED","CRITICAL"}]
    overall="OK" if complete and non_current==0 and not review_states else "ATTENTION"
    payload={"schema":"jom-source-freshness-audit-v4-canonical-inventory","generated_at_utc":iso(now),"inventory":{"owner":"app/audits/source_freshness.py","expected_source_count":len(SOURCES),"checked_source_count":len(rows),"unique_keys":unique,"unique_paths":unique,"coverage_complete":complete},"membership":{"connections":[x["key"] for x in SOURCES if x["connection_member"]],"authentication":[x["key"] for x in SOURCES if x["authentication_member"]]},"policy":POLICY,"sources":rows,"summary":{"source_count":len(rows),"counts":counts,"review_state_count":len(review_states),"overall_state":overall,"coverage_complete":complete},"issues":[{"source":x["label"],"path":x["path"],"state":x["freshness_state"],"declared_state":x["declared_state"]} for x in rows if x["freshness_state"]!="CURRENT" or x["declared_state"] in {"PARTIAL","REVIEW","UNAVAILABLE","ERROR","FAILED","CRITICAL"}]}
    out=root/"runtime/data/source_freshness_audit.json"; out.parent.mkdir(parents=True,exist_ok=True); tmp=out.with_suffix(".json.tmp"); tmp.write_text(json.dumps(payload,indent=2),encoding="utf-8"); tmp.replace(out); print(json.dumps({"overall_state":overall,"expected":len(SOURCES),"coverage_complete":complete,"output":str(out)},indent=2)); return payload
if __name__=="__main__": main()
