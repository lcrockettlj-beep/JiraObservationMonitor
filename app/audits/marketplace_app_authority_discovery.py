from __future__ import annotations
import base64, json, os, re, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/"reports"/"marketplace_app_authority_discovery_v1.json"
SECRET_KEYS=("token","secret","api_key","apikey","authorization","password")


def now_utc(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def read_json(path,default=None):
    try: return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default
    except Exception: return default

def load_env():
    env=dict(os.environ); path=ROOT/".env"
    if path.exists():
        for raw in path.read_text(encoding="utf-8",errors="ignore").splitlines():
            line=raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k,v=line.split("=",1); env[k.strip()]=v.strip().strip('"').strip("'")
    return env

def clean_shape(value: Any, depth=0):
    if depth>3: return type(value).__name__
    if isinstance(value,dict): return {k:("[REDACTED]" if any(s in k.lower() for s in SECRET_KEYS) else clean_shape(v,depth+1)) for k,v in list(value.items())[:40]}
    if isinstance(value,list): return {"type":"list","count":len(value),"item_shape":clean_shape(value[0],depth+1) if value else None}
    return type(value).__name__

def request(url,headers):
    req=urllib.request.Request(url,headers=headers,method="GET")
    try:
        with urllib.request.urlopen(req,timeout=35) as r:
            raw=r.read().decode("utf-8",errors="replace"); data=json.loads(raw) if raw else {}
            return {"ok":True,"status":int(r.status),"content_type":r.headers.get("Content-Type"),"shape":clean_shape(data),"body_stored":False}
    except urllib.error.HTTPError as e:
        return {"ok":False,"status":int(e.code),"content_type":e.headers.get("Content-Type") if e.headers else None,"shape":None,"body_stored":False,"error_category":"unauthorized" if e.code in (401,403) else "not_found" if e.code==404 else "not_acceptable" if e.code==406 else "rate_limit" if e.code==429 else "http_error"}
    except Exception as e: return {"ok":False,"status":0,"shape":None,"body_stored":False,"error_category":type(e).__name__}

def main():
    env=load_env(); org=(env.get("ATLASSIAN_ADMIN_ORG_ID") or env.get("ATLASSIAN_ORG_ID") or "").strip(); admin=(env.get("ATLASSIAN_ADMIN_API_KEY") or env.get("ATLASSIAN_ADMIN_TOKEN") or "").strip(); email=(env.get("ATLASSIAN_EMAIL") or env.get("JIRA_EMAIL") or "").strip(); api=(env.get("ATLASSIAN_API_TOKEN") or env.get("JIRA_API_TOKEN") or "").strip()
    token_data=read_json(ROOT/"tokens.json",{}) or {}; oauth=str(token_data.get("access_token") or "").strip()
    registry=read_json(ROOT/"runtime"/"data"/"site_registry.json",{}) or {}
    sites=[]
    for row in registry.get("sites",[]):
        if not isinstance(row,dict): continue
        state=str(row.get("lifecycle") or row.get("classification") or row.get("status") or "").lower()
        if row.get("is_monitored") is True or row.get("monitored") is True or row.get("approved_monitored") is True or state in {"monitored","monitoring_enabled"}:
            key=str(row.get("site_key") or row.get("key") or "").lower(); url=str(row.get("site_url") or row.get("url") or "").rstrip("/")
            if key and url: sites.append((key,url))
    probes=[]
    if admin:
        probes.append({"probe":"commerce_entitlements_admin_key","scope":"organisation","result":request("https://api.atlassian.com/commerce/api/v1/entitlements?page-size=50",{"Authorization":"Bearer "+admin,"Accept":"application/json"})})
    else: probes.append({"probe":"commerce_entitlements_admin_key","scope":"organisation","result":{"ok":False,"status":0,"error_category":"credential_unavailable"}})
    if oauth:
        probes.append({"probe":"commerce_entitlements_oauth","scope":"organisation","result":request("https://api.atlassian.com/commerce/api/v1/entitlements?page-size=50",{"Authorization":"Bearer "+oauth,"Accept":"application/json"})})
    else: probes.append({"probe":"commerce_entitlements_oauth","scope":"organisation","result":{"ok":False,"status":0,"error_category":"credential_unavailable"}})
    for key,url in sites:
        headers={"Accept":"application/json"}
        if email and api: headers["Authorization"]="Basic "+base64.b64encode((email+":"+api).encode()).decode()
        elif oauth: headers["Authorization"]="Bearer "+oauth
        else:
            probes.append({"probe":"site_upm_plugins","site_key":key,"scope":"site","result":{"ok":False,"status":0,"error_category":"credential_unavailable"}}); continue
        probes.append({"probe":"site_upm_plugins","site_key":key,"scope":"site","result":request(url+"/rest/plugins/1.0/",headers)})
        time.sleep(.1)
    successful=[p for p in probes if p["result"].get("ok")]
    payload={"schema":"jom-marketplace-app-authority-discovery-v1","generated_at_utc":now_utc(),"status":"candidate_source_found" if successful else "no_proven_source","read_only":True,"raw_bodies_stored":False,"secrets_stored":False,"probes":probes,"summary":{"monitored_site_count":len(sites),"probe_count":len(probes),"successful_probe_count":len(successful),"commerce_success_count":sum(1 for p in successful if p["probe"].startswith("commerce")),"site_upm_success_count":sum(1 for p in successful if p["probe"]=="site_upm_plugins")},"decision":{"marketplace_app_installation_authority_proven":False,"safe_to_publish_marketplace_apps":False,"next_step":"Inspect successful response shapes and prove site association, pagination, installed-state semantics and completeness before creating a publishing collector."},"notes":["HTTP success is discovery evidence, not app authority.","Commerce entitlements may prove commercial entitlement but not installed or enabled state.","UPM routes may be private/internal for Atlassian Cloud and must not be treated as supported authority without validation."]}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True); OUTPUT.write_text(json.dumps(payload,indent=2),encoding="utf-8"); print(json.dumps({"status":payload["status"],"summary":payload["summary"],"output":str(OUTPUT)},indent=2)); return 0

if __name__=="__main__": raise SystemExit(main())
