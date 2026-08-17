from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "runtime" / "data" / "estate_monitored_product_authority_v1.json"
ACCEPTED_PRODUCTS = {"jira-software": "Jira Software", "confluence": "Confluence"}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception: return default


def is_monitored(row: dict[str, Any]) -> bool:
    state=str(row.get("lifecycle") or row.get("classification") or row.get("collector_onboarding_status") or row.get("status") or "").lower()
    return bool(row.get("is_monitored") is True or row.get("monitored") is True or row.get("approved_monitored") is True or state in {"monitored","monitoring_enabled"})


def site_key(row: dict[str, Any]) -> str:
    return str(row.get("site_key") or row.get("key") or row.get("name") or "").strip().lower()


def build_monitored_product_authority(root: Path | None = None, write_output: bool = True) -> dict[str, Any]:
    root=root or ROOT
    registry=read_json(root/"runtime"/"data"/"site_registry.json",{}) or {}
    mapping=read_json(root/"runtime"/"data"/"estate_site_resource_mapping_v1.json",{}) or {}
    sites={site_key(row): row for row in registry.get("sites",[]) if isinstance(row,dict) and site_key(row) and is_monitored(row)}
    product_by_site={key:set() for key in sites}
    rejected=[]
    for row in mapping.get("mappings",[]) if isinstance(mapping,dict) else []:
        if not isinstance(row,dict): continue
        key=site_key(row); product=str(row.get("product") or "").strip().lower(); confidence=str(row.get("confidence") or "").lower()
        if key not in sites: continue
        if product not in ACCEPTED_PRODUCTS or confidence != "high":
            rejected.append({"site_key":key,"product":product or "unavailable","reason":"unsupported product or mapping confidence is not high"})
            continue
        product_by_site[key].add(product)
    rows=[]
    for key in sorted(sites):
        products=sorted(product_by_site[key])
        rows.append({"site_key":key,"status":"available" if products else "unavailable","products":[{"product_key":x,"display_name":ACCEPTED_PRODUCTS[x],"monitoring_state":"monitored","authority":"current high-confidence site-scoped Atlassian ARI mapping"} for x in products],"product_count":len(products),"reason":"Current monitored products proven by site-scoped Atlassian ARI mappings." if products else "No current high-confidence monitored-product mapping was available."})
    uncovered=sorted(key for key in sites if not product_by_site[key])
    complete=bool(sites) and not uncovered and not rejected and mapping.get("status")=="mapped" and mapping.get("safe_to_populate_contacts") is True
    payload={"schema":"jom-estate-monitored-product-authority-v1","generated_at_utc":now_utc(),"status":"ok" if complete else "review","scope":{"definition":"Products actively monitored by JOM and proven for each monitored site. This is not a commercial subscription or billing inventory.","commercial_licensing_included":False,"marketplace_apps_included":False},"authority":{"site_scope":"runtime/data/site_registry.json monitored lifecycle","product_scope":"runtime/data/estate_site_resource_mapping_v1.json high-confidence site-scoped ARI mapping","safe_to_publish":complete,"fabricated_products":False},"summary":{"monitored_site_count":len(sites),"covered_site_count":len(sites)-len(uncovered),"monitored_product_assignment_count":sum(len(x) for x in product_by_site.values()),"unique_monitored_products":sorted({p for values in product_by_site.values() for p in values}),"uncovered_site_count":len(uncovered),"rejected_mapping_count":len(rejected)},"sites":rows,"diagnostics":{"uncovered_site_keys":uncovered,"rejected_mappings":rejected}}
    if write_output:
        OUTPUT.parent.mkdir(parents=True,exist_ok=True); OUTPUT.write_text(json.dumps(payload,indent=2),encoding="utf-8")
    return payload


def main() -> int:
    payload=build_monitored_product_authority(); print(json.dumps({"status":payload["status"],"summary":payload["summary"]},indent=2)); return 0 if payload["status"]=="ok" else 1

if __name__=="__main__": raise SystemExit(main())
