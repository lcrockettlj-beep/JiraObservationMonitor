from __future__ import annotations
import base64, json, os, re, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]
EVIDENCE=ROOT/"reports"/"connected_apps_authority_discovery_v1_1.json"
OUTPUT=ROOT/"reports"/"jira_connected_apps_endpoint_contract_audit_v1.json"
SITE_TOKEN="<site-cloud-id>"
ENDPOINTS=("/rest/plugins/1.0/","/rest/plugins/1.0/installed-marketplace")


def now_utc(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def read_json(path,default=None):
    try: return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default
    except Exception: return default

def load_env():
    env=dict(os.environ); p=ROOT/".env"
    if p.exists():
        for raw in p.read_text(encoding="utf-8",errors="ignore").splitlines():
            line=raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k,v=line.split("=",1); env[k.strip()]=v.strip().strip('"').strip("'")
    return env

def monitored_sites():
    reg=read_json(ROOT/"runtime"/"data"/"site_registry.json",{}) or {}; rows=[]
    for row in reg.get("sites",[]):
        if not isinstance(row,dict): continue
        state=str(row.get("lifecycle") or row.get("classification") or row.get("status") or "").lower()
        if row.get("is_monitored") is True or row.get("monitored") is True or row.get("approved_monitored") is True or state in {"monitored","monitoring_enabled"}:
            key=str(row.get("site_key") or row.get("key") or "").strip().lower(); cloud=str(row.get("cloud_id") or "").strip()
            if key and cloud: rows.append((key,cloud))
    return rows

def request(url,headers):
    req=urllib.request.Request(url,headers=headers,method="GET")
    try:
        with urllib.request.urlopen(req,timeout=35) as r:
            raw=r.read(); return {"ok":True,"status":int(r.status),"content_type":r.headers.get("Content-Type"),"response_bytes":len(raw),"body_stored":False}
    except urllib.error.HTTPError as e:
        return {"ok":False,"status":int(e.code),"content_type":e.headers.get("Content-Type") if e.headers else None,"response_bytes":0,"body_stored":False,"error_category":"unauthorized" if e.code in (401,403) else "not_found" if e.code==404 else "not_acceptable" if e.code==406 else "rate_limit" if e.code==429 else "http_error"}
    except Exception as e: return {"ok":False,"status":0,"response_bytes":0,"body_stored":False,"error_category":type(e).__name__}

def main():
    evidence=read_json(EVIDENCE,{}) or {}; env=load_env(); token_data=read_json(ROOT/"tokens.json",{}) or {}
    admin=(env.get("ATLASSIAN_ADMIN_API_KEY") or env.get("ATLASSIAN_ADMIN_TOKEN") or "").strip(); oauth=str(token_data.get("access_token") or "").strip(); email=(env.get("ATLASSIAN_EMAIL") or env.get("JIRA_EMAIL") or "").strip(); api=(env.get("ATLASSIAN_API_TOKEN") or env.get("JIRA_API_TOKEN") or "").strip()
    auth=[]
    if admin: auth.append(("admin_bearer",{"Authorization":"Bearer "+admin,"Accept":"application/json"}))
    if oauth: auth.append(("oauth_bearer",{"Authorization":"Bearer "+oauth,"Accept":"application/json"}))
    if email and api: auth.append(("site_basic",{"Authorization":"Basic "+base64.b64encode((email+":"+api).encode()).decode(),"Accept":"application/json"}))
    probes=[]
    sites=monitored_sites()
    for site_key,cloud_id in sites:
        for suffix in ENDPOINTS:
            safe_path=f"/gateway/api/ex/jira/{SITE_TOKEN}{suffix}"
            if not auth:
                probes.append({"site_key":site_key,"endpoint":safe_path,"auth_mode":"unavailable","result":{"ok":False,"status":0,"error_category":"credential_unavailable","body_stored":False}})
                continue
            for auth_mode,headers in auth:
                url=f"https://admin.atlassian.com/gateway/api/ex/jira/{cloud_id}{suffix}"
                probes.append({"site_key":site_key,"endpoint":safe_path,"auth_mode":auth_mode,"result":request(url,headers)})
                time.sleep(.1)
    candidates=[c for c in evidence.get("candidates",[]) if isinstance(c,dict) and "/gateway/api/ex/jira/" in str(c.get("path"))]
    shapes=[]
    for c in candidates:
        shapes.append({"endpoint":c.get("path"),"browser_status":c.get("status"),"mime_type":c.get("mime_type"),"response_shape":c.get("response_shape"),"response_shape_keys":c.get("response_shape_keys",[])})
    successes=[p for p in probes if p["result"].get("ok")]
    complete_sites=sorted({p["site_key"] for p in successes if p["endpoint"].endswith("installed-marketplace")})
    result={"schema":"jom-jira-connected-apps-endpoint-contract-audit-v1","generated_at_utc":now_utc(),"status":"non_browser_candidate_reachable" if successes else "browser_session_only_or_unsupported_with_current_credentials","privacy":{"cloud_ids_stored":False,"credentials_stored":False,"authorization_headers_stored":False,"raw_response_bodies_stored":False,"app_records_stored":False,"personal_records_stored":False},"browser_evidence":{"source_schema":evidence.get("schema"),"candidate_shapes":shapes,"full_plugins_browser_count":next((c.get("response_shape",{}).get("plugins",{}).get("count") for c in candidates if str(c.get("path")).endswith("/rest/plugins/1.0/")),None),"installed_marketplace_browser_count":next((c.get("response_shape",{}).get("plugins",{}).get("count") for c in candidates if str(c.get("path")).endswith("installed-marketplace")),None)},"field_contract":{"full_plugins":{"list_path":"plugins","candidate_identity_fields":["key","name","version","vendor.name"],"candidate_state_fields":["enabled","userInstalled","optional","unloadable","static","remotable"],"candidate_licensing_fields":["usesLicensing"]},"installed_marketplace":{"list_path":"plugins","candidate_identity_fields":["key","name","hamsProductKey"],"candidate_state_fields":["updateAvailable","updatableToPaid","updatableToForge"],"candidate_licensing_fields":["licenseReadOnly"],"host_license_fields_excluded_from_app_contract":["supportEntitlementNumber","entitlementId","entitlementNumber"]}},"summary":{"monitored_site_count":len(sites),"configured_auth_mode_count":len(auth),"probe_count":len(probes),"successful_probe_count":len(successes),"sites_with_reachable_installed_marketplace":len(complete_sites)},"probes":probes,"decision":{"browser_route_exists":len(candidates)>=2,"non_browser_authentication_proven":bool(successes),"site_binding_proven":False,"pagination_proven":False,"installation_semantics_proven":False,"system_app_exclusion_proven":False,"cross_site_completeness_proven":False,"confluence_app_authority_proven":False,"marketplace_app_installation_authority_proven":False,"safe_to_publish_marketplace_apps":False,"next_step":"If current credentials cannot reach the route, record browser-session-only limitation and create an unavailable authority contract. If reachable, perform a separate privacy-approved field/count collector and cross-site completeness audit."},"notes":["The HAR shape reported 204 rows for both full plugins and installed-marketplace; that equality is suspicious and does not by itself prove a filtered Marketplace-only list.","Host license entitlement fields describe the host product and are excluded from Marketplace app records.","No raw endpoint response is retained by this audit."]}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True); OUTPUT.write_text(json.dumps(result,indent=2),encoding="utf-8"); print(json.dumps({"status":result["status"],"summary":result["summary"],"decision":result["decision"],"output":str(OUTPUT)},indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
