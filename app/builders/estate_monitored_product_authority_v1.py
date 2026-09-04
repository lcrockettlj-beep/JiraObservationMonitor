from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'runtime'/'data'
REGISTRY=DATA/'site_registry.json'
MAPPING=DATA/'estate_site_resource_mapping_v1.json'
OUTPUT=DATA/'estate_monitored_product_authority_v1.json'

def now_utc(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def read(path:Path)->dict[str,Any]:
 try:
  value=json.loads(path.read_text(encoding='utf-8-sig')); return value if isinstance(value,dict) else {}
 except Exception:return {}
def key(row):
 if not isinstance(row,dict): return ''
 value=row.get('site_key') or row.get('key') or row.get('site_name') or row.get('name') or row.get('site_url') or row.get('url') or ''
 text=str(value).strip().lower()
 if text.startswith('http') and '.atlassian.net' in text: text=text.split('//',1)[-1].split('.atlassian.net',1)[0]
 return text.rstrip('/')
def monitored(row):
 if not isinstance(row,dict): return False
 state=str(row.get('lifecycle') or row.get('classification') or row.get('collector_onboarding_status') or row.get('status') or '').strip().lower()
 return bool(row.get('is_monitored') is True or row.get('monitored') is True or row.get('approved_monitored') is True or state in {'monitored','monitoring_enabled'})
def rows(payload):
 for name in ('mappings','sites','resources','items','records'):
  value=payload.get(name)
  if isinstance(value,list): return [x for x in value if isinstance(x,dict)]
 return []
def confidence(row): return str(row.get('confidence') or row.get('mapping_confidence') or row.get('evidence_confidence') or '').strip().lower()
def product_key(row):
 value=row.get('product_key') or row.get('product') or row.get('product_type') or row.get('type') or row.get('ari_product') or ''
 text=str(value).strip().lower().replace('_','-')
 if 'jira' in text:return 'jira-software'
 if 'confluence' in text:return 'confluence'
 return ''
def extract_products(row):
 out=[]
 nested=row.get('products')
 if isinstance(nested,list):
  for item in nested:
   if isinstance(item,dict):
    p=product_key(item)
    if p and (confidence(item) in {'high','confirmed','authoritative'} or item.get('high_confidence') is True or item.get('status') in {'available','ok','confirmed'}): out.append(p)
   elif isinstance(item,str):
    p=product_key({'product':item})
    if p and (confidence(row) in {'high','confirmed','authoritative'} or row.get('high_confidence') is True): out.append(p)
 p=product_key(row)
 if p and (confidence(row) in {'high','confirmed','authoritative'} or row.get('high_confidence') is True or row.get('status') in {'available','ok','confirmed'}): out.append(p)
 return sorted(set(out))
def main()->dict[str,Any]:
 registry=read(REGISTRY); mapping=read(MAPPING); monitored_sites=sorted({key(x) for x in registry.get('sites',[]) if monitored(x) and key(x)})
 mapping_rows=rows(mapping); by_site={k:set() for k in monitored_sites}; rejected=[]
 for row in mapping_rows:
  k=key(row); products=extract_products(row)
  if k in by_site and products: by_site[k].update(products)
  elif k in by_site: rejected.append({'site_key':k,'reason':'No supported product with high-confidence mapping evidence.'})
 display={'jira-software':'Jira Software','confluence':'Confluence'}; sites=[]; covered=[]
 for k in monitored_sites:
  products=sorted(by_site[k])
  if products: covered.append(k)
  sites.append({'site_key':k,'status':'available' if products else 'unavailable','products':[{'product_key':p,'display_name':display[p],'monitoring_state':'monitored','authority':'current high-confidence site-scoped Atlassian ARI mapping'} for p in products],'product_count':len(products) if products else None,'reason':'Current monitored products proven by site-scoped Atlassian ARI mappings.' if products else 'No current high-confidence supported product mapping was proven.'})
 uncovered=sorted(set(monitored_sites)-set(covered)); unique=sorted({p for vals in by_site.values() for p in vals})
 payload={'schema':'jom-estate-monitored-product-authority-v1','generated_at_utc':now_utc(),'status':'ok' if monitored_sites and not uncovered else 'review','scope':{'definition':'Products actively monitored by JOM and proven for each monitored site. This is not a commercial subscription or billing inventory.','commercial_licensing_included':False,'marketplace_apps_included':False},'authority':{'site_scope':'runtime/data/site_registry.json monitored lifecycle','product_scope':'runtime/data/estate_site_resource_mapping_v1.json high-confidence site-scoped ARI mapping','safe_to_publish':bool(monitored_sites) and not uncovered,'fabricated_products':False},'summary':{'monitored_site_count':len(monitored_sites),'covered_site_count':len(covered),'monitored_product_assignment_count':sum(len(x) for x in by_site.values()),'unique_monitored_products':unique,'uncovered_site_count':len(uncovered),'rejected_mapping_count':len(rejected)},'sites':sites,'diagnostics':{'uncovered_site_keys':uncovered,'rejected_mappings':rejected},'source_files':['runtime/data/site_registry.json','runtime/data/estate_site_resource_mapping_v1.json']}
 OUTPUT.parent.mkdir(parents=True,exist_ok=True); tmp=OUTPUT.with_suffix('.json.tmp'); tmp.write_text(json.dumps(payload,indent=2),encoding='utf-8'); tmp.replace(OUTPUT); print(json.dumps({'status':payload['status'],'output':str(OUTPUT),'summary':payload['summary']},indent=2)); return payload
if __name__=='__main__':
 result=main(); raise SystemExit(0 if result.get('status') in {'ok','review'} else 2)
