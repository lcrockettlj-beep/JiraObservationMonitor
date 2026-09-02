from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
OUTPUT=Path("runtime/data/project_lead_authority_v1.json")
INVENTORY=Path("runtime/data/project_inventory_authority_v1.json")
PGNI=Path("runtime/data/project_governance_named_identity_authority_v1.json")
def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def atomic(path,payload):
 path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+".tmp"); tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); tmp.replace(path)
def main():
 inventory=json.loads(INVENTORY.read_text(encoding="utf-8-sig")); pgni=json.loads(PGNI.read_text(encoding="utf-8-sig")); q=pgni.get("quality",{}); a=pgni.get("authority",{})
 if inventory.get("status")!="ok" or inventory.get("authority",{}).get("safe_to_publish_project_inventory") is not True: raise SystemExit("STOP: Project Inventory authority unavailable")
 if pgni.get("status") not in {"ok","partial"} or a.get("safe_to_serve") is not True or q.get("project_coverage_percent",0)<95 or q.get("role_coverage_percent",0)<75: raise SystemExit("STOP: PGNI authority unavailable or below threshold")
 projects={(str(x.get("site_key") or ""),str(x.get("project_key") or "").upper()):x for x in inventory.get("projects",[]) if isinstance(x,dict)}; leads=defaultdict(list)
 for identity in pgni.get("identities",[]):
  if not isinstance(identity,dict): continue
  for assignment in identity.get("assignments",[]):
   if isinstance(assignment,dict) and assignment.get("source_type")=="project_lead":
    key=(str(assignment.get("site_key") or ""),str(assignment.get("project_key") or "").upper())
    row={"display_name":str(identity.get("display_name") or ""),"account_status":identity.get("account_status")}
    if key in projects and row["display_name"] and row not in leads[key]: leads[key].append(row)
 rows=[]
 for key,p in sorted(projects.items()):
  found=sorted(leads.get(key,[]),key=lambda x:x["display_name"].casefold()); rows.append({"site_key":key[0],"project_key":key[1],"project_name":p.get("project_name"),"lead_state":"supported_active_lead" if found else "no_supported_active_atlassian_lead_published","supported_lead_count":len(found),"leads":found})
 covered=sum(bool(x["leads"]) for x in rows); total=len(rows); coverage=round(covered*100/total,1) if total else 0.0
 payload={"schema":"jom-project-lead-authority-v1","generated_at_utc":now(),"status":"ok" if covered==total else "partial","summary":{"projects":total,"projects_with_supported_active_lead":covered,"projects_without_supported_active_lead_published":total-covered,"lead_coverage_percent":coverage,"distinct_supported_active_leads":len({l["display_name"] for r in rows for l in r["leads"]})},"authority":{"safe_to_serve":total>0,"project_owner_semantics_proven":False,"reason":"Every Project Inventory row was reconciled against publishable PGNI project-lead assignments; gaps are explicit and not inferred."},"privacy":{"account_ids_stored":False,"email_stored":False,"raw_responses_stored":False,"export_allowed":False,"download_allowed":False,"bulk_copy_allowed":False},"access":{"authorized_role":"Organisation administrator","phase1_mode":"trusted_local_operator","deny_by_default":True},"projects":rows,"limitations":["No supported active lead published does not prove Jira has no configured lead.","Project Lead is not Project Owner."]}
 if not payload["authority"]["safe_to_serve"]: raise SystemExit("STOP: no projects reconciled")
 atomic(OUTPUT,payload); print(json.dumps({"status":payload["status"],"output":str(OUTPUT),"summary":payload["summary"]},indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
