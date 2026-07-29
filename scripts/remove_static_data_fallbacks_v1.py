from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FILES=['admin_enriched_refresh_status.json', 'admin_truth_v2.json', 'backend_final_truth_chain_status.json', 'backend_legacy_truth_eradication_status.json', 'billing_seats.json', 'estate_access_truth.json', 'estate_admin_site_inventory_v1.json', 'estate_product_access.json', 'monitored_sites.json', 'runtime_execution_history.json', 'runtime_execution_status.json', 'site_access_validation.json', 'site_lifecycle_decisions.json', 'site_onboarding_review.json', 'site_registry.json', 'source_freshness_audit.json', 'source_reliability_status.json', 'user_footprint.json']
REPORT=ROOT/'reports'/'static_data_removal_v1.json'
def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def main():
    runtime=ROOT/'runtime'/'data'; static=ROOT / "runtime" / "data"
    removed=[]; missing=[]; blocked=[]
    for name in FILES:
        rp=runtime/name; sp=static/name
        if not rp.exists():
            blocked.append({'file':'runtime/data/'+name,'reason':'runtime copy missing; static fallback not removed'})
            continue
        if sp.exists():
            sp.unlink()
            removed.append('runtime/data/'+name)
        else:
            missing.append('runtime/data/'+name)
    report={'schema':'jom-static-data-removal-v1','generated_at_utc':now(),'removed':removed,'already_missing':missing,'blocked':blocked,'summary':{'removed_count':len(removed),'already_missing_count':len(missing),'blocked_count':len(blocked)}}
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report['summary'],indent=2))
    print('Report:', str(REPORT.relative_to(ROOT)).replace('\\','/'))
    if blocked:
        raise SystemExit(1)
    return 0
if __name__=='__main__': raise SystemExit(main())
