from __future__ import annotations
import csv, json, sys
from collections import Counter, defaultdict
from pathlib import Path

def main(folder: str) -> int:
    root=Path(folder)
    contracts=list(csv.DictReader((root/'runtime_contract_inventory.csv').open(encoding='utf-8-sig')))
    evidence=list(csv.DictReader((root/'site_product_evidence.csv').open(encoding='utf-8-sig')))
    refs=list(csv.DictReader((root/'repository_authority_references.csv').open(encoding='utf-8-sig')))
    sites=defaultdict(set)
    for row in evidence:
        key=(row.get('SiteKey') or '').strip().lower(); product=(row.get('Product') or '').strip().lower()
        if key and product: sites[key].add(product)
    app_candidates=[r for r in contracts if int(r.get('AppTerms') or 0)>0]
    product_candidates=[r for r in contracts if int(r.get('ProductTerms') or 0)>0]
    finding={
      'schema':'jom-product-marketplace-app-authority-analysis-v1',
      'product_candidate_contracts':[r['File'] for r in product_candidates],
      'marketplace_app_candidate_contracts':[r['File'] for r in app_candidates],
      'site_product_evidence':{k:sorted(v) for k,v in sorted(sites.items())},
      'repository_reference_patterns':dict(Counter(r['Pattern'] for r in refs)),
      'decision_gates':{
        'complete_site_product_authority_proven':False,
        'marketplace_app_installation_authority_proven':False,
        'safe_to_integrate_products':False,
        'safe_to_integrate_marketplace_apps':False,
      },
      'note':'Candidate references are not authority. Inspect evidence and prove semantics/completeness before changing a publish gate.'
    }
    (root/'analysis.json').write_text(json.dumps(finding,indent=2),encoding='utf-8')
    print(json.dumps({'analysis':str(root/'analysis.json'),'product_candidate_contracts':len(product_candidates),'app_candidate_contracts':len(app_candidates),'sites_with_explicit_product_rows':len(sites)},indent=2))
    return 0
if __name__=='__main__':
    raise SystemExit(main(sys.argv[1]))
