from __future__ import annotations
import argparse, json, socket, urllib.error, urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from app.builders import project_inventory_authority_v1 as source

OUTPUT=Path("runtime/data/project_governance_named_identity_authority_v1.json")
MAXIMUM_AGE_HOURS=26
AUTHORIZED_ROLE="Organisation administrator"
REQUEST_TIMEOUT_SECONDS=15

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def write_atomic(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
    tmp.replace(path)
def request_json(url,token):
    req=urllib.request.Request(url=url,headers={"Authorization":"Bearer "+token,"Accept":"application/json"},method="GET")
    try:
        with urllib.request.urlopen(req,timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw=response.read().decode("utf-8",errors="replace")
            return int(response.status),json.loads(raw) if raw else {},None
    except urllib.error.HTTPError as exc:
        exc.read(); return int(exc.code),{},"http_error"
    except (urllib.error.URLError,TimeoutError,socket.timeout) as exc:
        return 0,{},type(exc).__name__
    except Exception as exc:
        return 0,{},type(exc).__name__
def actor_account_id(actor):
    if not isinstance(actor,dict): return ""
    user=actor.get("actorUser") if isinstance(actor.get("actorUser"),dict) else {}
    return str(user.get("accountId") or actor.get("accountId") or "").strip()

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--project-root",default="."); args=parser.parse_args(); root=Path(args.project_root).resolve()
    inventory=json.loads((root/"runtime/data/project_inventory_authority_v1.json").read_text(encoding="utf-8-sig"))
    identity=json.loads((root/"runtime/data/named_user_display_identity_v1.json").read_text(encoding="utf-8-sig"))
    if inventory.get("status")!="ok" or inventory.get("authority",{}).get("safe_to_publish_project_inventory") is not True: raise SystemExit("STOP: Project Inventory authority is unavailable or unsafe")
    if identity.get("status")!="ok" or identity.get("authority",{}).get("safe_to_serve") is not True: raise SystemExit("STOP: Named User Display Identity authority is unavailable or unsafe")
    sites={row["site_key"]:row for row in source.monitored_sites()}; token=str(source.token_payload().get("access_token") or "")
    if not token: raise SystemExit("STOP: OAuth access token unavailable")
    projects=inventory.get("projects") if isinstance(inventory.get("projects"),list) else []
    known_names={str(row.get("display_name") or "").strip() for row in identity.get("users",[]) if isinstance(row,dict) and row.get("display_name")}
    principals={}; failures=[]; counts=Counter(); user_cache={}
    def add(account_id,user,site_key,project_key,source_type,role_name):
        if not account_id or not isinstance(user,dict) or user.get("accountType")!="atlassian" or user.get("active") is not True: return
        name=str(user.get("displayName") or "").strip()
        if not name: return
        cache_key=site_key+"\\0"+account_id
        rec=principals.setdefault(cache_key,{"display_name":name,"account_status":"active","sites":set(),"projects":set(),"roles":set(),"sources":set(),"assignments":[]})
        assignment={"site_key":site_key,"project_key":project_key,"source_type":source_type,"role_name":role_name}
        if assignment not in rec["assignments"]: rec["assignments"].append(assignment)
        rec["sites"].add(site_key); rec["projects"].add(site_key+":"+project_key); rec["roles"].add(role_name); rec["sources"].add(source_type)
    def user_for(site,site_key,account_id):
        key=site_key+"\\0"+account_id
        if key not in user_cache:
            url="https://api.atlassian.com/ex/jira/"+site["cloud_id"]+"/rest/api/3/user?accountId="+account_id
            status,payload,error=request_json(url,token); counts["unique_user_requests"]+=1
            user_cache[key]=(status,payload,error)
            if status!=200: failures.append({"site_key":site_key,"stage":"user_detail","http_status":status,"error":error})
        return user_cache[key]
    for index,project in enumerate(projects,1):
        sk=str(project.get("site_key") or ""); pk=str(project.get("project_key") or ""); site=sites.get(sk); counts["projects"]+=1
        print(f"PROJECT {index}/{len(projects)} {sk}:{pk}",flush=True)
        if not site: failures.append({"site_key":sk,"project_key":pk,"stage":"site_resolution"}); continue
        url="https://api.atlassian.com/ex/jira/"+site["cloud_id"]+"/rest/api/3/project/"+pk
        status,payload,error=request_json(url,token); counts["project_requests"]+=1
        if status!=200 or not isinstance(payload,dict): failures.append({"site_key":sk,"project_key":pk,"stage":"project_detail","http_status":status,"error":error}); continue
        counts["project_success"]+=1
        lead=payload.get("lead") if isinstance(payload.get("lead"),dict) else {}; lead_id=str(lead.get("accountId") or "")
        if lead_id:
            us,user,_=user_for(site,sk,lead_id)
            if us==200: add(lead_id,user,sk,pk,"project_lead","Project Lead")
        roles=payload.get("roles") if isinstance(payload.get("roles"),dict) else {}
        for role_name,role_url in roles.items():
            rs,rp,re=request_json(str(role_url),token); counts["role_requests"]+=1
            if rs!=200 or not isinstance(rp,dict): failures.append({"site_key":sk,"project_key":pk,"stage":"role_detail","role_name":str(role_name),"http_status":rs,"error":re}); continue
            counts["role_success"]+=1
            for actor in rp.get("actors",[]) if isinstance(rp.get("actors"),list) else []:
                account=actor_account_id(actor)
                if not account: continue
                us,user,_=user_for(site,sk,account)
                if us==200: add(account,user,sk,pk,"project_role",str(role_name))
    rows=[]
    for rec in principals.values():
        row=dict(rec); row["sites"]=sorted(row["sites"]); row["projects"]=sorted(row["projects"]); row["roles"]=sorted(row["roles"]); row["sources"]=sorted(row["sources"]); row["assignment_count"]=len(row["assignments"]); row["project_count"]=len(row["projects"]); row["existing_named_user_identity"]=row["display_name"] in known_names; rows.append(row)
    rows.sort(key=lambda x:(x["display_name"].casefold(),x["projects"]))
    project_coverage=(counts["project_success"] / len(projects)) if projects else 0.0
    role_coverage=(counts["role_success"] / counts["role_requests"]) if counts["role_requests"] else 0.0
    publishable=bool(rows) and project_coverage >= 0.95 and role_coverage >= 0.75
    capability_state="PROVEN" if not failures else "PARTIAL"
    result={"schema":"jom-project-governance-named-identity-authority-v1","generated_at_utc":now(),"status":"ok" if capability_state=="PROVEN" else "partial" if publishable else "unavailable","summary":{"named_principals":len(rows),"assignment_count":sum(x["assignment_count"] for x in rows),"existing_named_user_identities":sum(1 for x in rows if x["existing_named_user_identity"]),"additional_governance_identities":sum(1 for x in rows if not x["existing_named_user_identity"]),**dict(counts)},"quality":{"full_success":not failures,"publishable_with_recorded_exceptions":publishable,"project_coverage_percent":round(project_coverage*100,1),"role_coverage_percent":round(role_coverage*100,1),"capability_state":capability_state,"request_failures":len(failures),"account_ids_stored":False,"email_stored":False,"raw_responses_stored":False,"unique_user_lookup_cache":True,"request_timeout_seconds":REQUEST_TIMEOUT_SECONDS},"freshness":{"maximum_age_hours":MAXIMUM_AGE_HOURS},"access":{"authorized_role":AUTHORIZED_ROLE,"phase1_mode":"trusted_local_operator","deny_by_default":True,"export_allowed":False,"download_allowed":False,"bulk_copy_allowed":False},"authority":{"safe_to_serve":publishable,"reason":"Coverage thresholds passed; known HTTP coverage exceptions are recorded." if publishable else "Coverage thresholds did not pass; previous authority was not replaced."},"identities":rows if publishable else [],"failures":failures}
    if publishable: write_atomic(root/OUTPUT,result)
    else:
        report=root/"reports/project_governance_named_identity_authority_failure_v1.json"; report.parent.mkdir(parents=True,exist_ok=True); report.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"output":str(root/OUTPUT) if publishable else None,"failure_report":None if publishable else str(report),"summary":result["summary"],"request_failures":len(failures)},indent=2)); return 0 if publishable else 2
if __name__=="__main__": raise SystemExit(main())
