from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/"runtime"/"data"/"estate_marketplace_app_authority_v1.json"
DISCOVERY=ROOT/"reports"/"connected_apps_authority_discovery_v1_1.json"
CONTRACT_AUDIT=ROOT/"reports"/"jira_connected_apps_endpoint_contract_audit_v1.json"
REGISTRY=ROOT/"runtime"/"data"/"site_registry.json"


def now_utc(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def read_json(path: Path, default: Any=None):
    try: return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default
    except Exception: return default

def monitored(row: dict[str,Any]) -> bool:
    state=str(row.get("lifecycle") or row.get("classification") or row.get("collector_onboarding_status") or row.get("status") or "").lower()
    return bool(row.get("is_monitored") is True or row.get("monitored") is True or row.get("approved_monitored") is True or state in {"monitored","monitoring_enabled"})
def site_key(row): return str(row.get("site_key") or row.get("key") or row.get("name") or "").strip().lower()

def build_marketplace_app_limitation_authority(root: Path|None=None, write_output: bool=True):
    root=root or ROOT
    registry=read_json(root/"runtime"/"data"/"site_registry.json",{}) or {}
    discovery=read_json(root/"reports"/"connected_apps_authority_discovery_v1_1.json",{}) or {}
    audit=read_json(root/"reports"/"jira_connected_apps_endpoint_contract_audit_v1.json",{}) or {}
    sites=[row for row in registry.get("sites",[]) if isinstance(row,dict) and site_key(row) and monitored(row)]
    browser_exists=bool(audit.get("decision",{}).get("browser_route_exists"))
    non_browser=bool(audit.get("decision",{}).get("non_browser_authentication_proven"))
    successful=int(audit.get("summary",{}).get("successful_probe_count") or 0)
    evidence_valid=(discovery.get("schema")=="jom-connected-apps-authority-discovery-v1.1" and audit.get("schema")=="jom-jira-connected-apps-endpoint-contract-audit-v1" and browser_exists and not non_browser and successful==0)
    reason="Atlassian Administration exposes Connected Apps through an authenticated browser-session gateway, but JOM's current non-browser Admin Bearer and OAuth Bearer credentials cannot access that gateway. Installed Marketplace app inventory is therefore unavailable through the current JOM integration."
    rows=[]
    for row in sorted(sites,key=site_key):
        key=site_key(row)
        base=str(row.get("site_url") or row.get("url") or "").rstrip("/")
        rows.append({"site_key":key,"status":"unavailable","marketplace_app_count":None,"apps":[],"jira_authority":"unavailable","confluence_authority":"unavailable","reason":reason,"action":{"label":"Review Connected Apps in Atlassian Administration","href":"https://admin.atlassian.com/","external":True},"site_reference":{"site_url":base if base else None}})
    payload={"schema":"jom-estate-marketplace-app-authority-v1","generated_at_utc":now_utc(),"status":"unavailable" if evidence_valid else "review","scope":{"definition":"Installed Marketplace apps by monitored site.","commercial_entitlements_included":False,"host_product_licensing_included":False},"authority":{"safe_to_publish_marketplace_apps":False,"app_records_collected":False,"fabricated_apps":False,"browser_route_exists":browser_exists,"non_browser_authentication_proven":non_browser,"reason":reason if evidence_valid else "Required limitation evidence is incomplete or inconsistent."},"summary":{"monitored_site_count":len(sites),"available_site_count":0,"unavailable_site_count":len(sites),"marketplace_app_count":None,"successful_non_browser_probe_count":successful},"sites":rows,"evidence":{"connected_apps_discovery_schema":discovery.get("schema"),"endpoint_contract_audit_schema":audit.get("schema"),"endpoint_contract_status":audit.get("status"),"cloud_ids_stored":False,"raw_payloads_stored":False},"future_authority_requirements":["Supported non-browser authentication","Proven site binding","Proven installation and enabled-state semantics","System-app exclusion","Pagination and completeness","Cross-site validation","Separate Confluence validation"]}
    if write_output:
        out=root/"runtime"/"data"/"estate_marketplace_app_authority_v1.json"; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(payload,indent=2),encoding="utf-8")
    return payload

def main():
    p=build_marketplace_app_limitation_authority(); print(json.dumps({"status":p["status"],"summary":p["summary"],"safe_to_publish":p["authority"]["safe_to_publish_marketplace_apps"]},indent=2)); return 0 if p["status"]=="unavailable" else 1
if __name__=="__main__": raise SystemExit(main())
