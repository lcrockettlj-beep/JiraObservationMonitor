from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FILES=['admin_enriched_refresh_status.json', 'admin_truth_v2.json', 'backend_final_truth_chain_status.json', 'backend_legacy_truth_eradication_status.json', 'billing_seats.json', 'estate_access_truth.json', 'estate_admin_site_inventory_v1.json', 'estate_product_access.json', 'monitored_sites.json', 'runtime_execution_history.json', 'runtime_execution_status.json', 'site_access_validation.json', 'site_lifecycle_decisions.json', 'site_onboarding_review.json', 'site_registry.json', 'source_freshness_audit.json', 'source_reliability_status.json', 'user_footprint.json']
REPORT=ROOT/'reports'/'static_data_removal_validation_v1.json'
def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def fail(msg, result):
    result['summary']['validation_state']='FAIL'
    result['failure']=msg
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('FAIL: '+msg)
    print('Report:', str(REPORT.relative_to(ROOT)).replace('\\','/'))
    raise SystemExit(1)
def readable_json(path):
    try:
        json.loads(path.read_text(encoding='utf-8-sig'))
        return True
    except Exception:
        return False
def main():
    runtime=ROOT/'runtime'/'data'; static=ROOT/'static'/'data'
    result={'schema':'jom-static-data-removal-validation-v1','generated_at_utc':now(),'summary':{},'missing_runtime':[],'unreadable_runtime':[],'remaining_static':[],'frontend_static_references':[],'backend_static_reference_files':[],'failure':None}
    for name in FILES:
        rp=runtime/name; sp=static/name
        if not rp.exists(): result['missing_runtime'].append('runtime/data/'+name)
        elif not readable_json(rp): result['unreadable_runtime'].append('runtime/data/'+name)
        if sp.exists(): result['remaining_static'].append('static/data/'+name)
    jsdir=ROOT/'static'/'js'
    if jsdir.exists():
        for js in jsdir.rglob('*.js'):
            if '/static/data/' in js.read_text(encoding='utf-8',errors='replace'):
                result['frontend_static_references'].append(str(js.relative_to(ROOT)).replace('\\','/'))
    # remaining static/data text refs for review only; app/runtime fallback resolver remains expected until next pack
    for base in ['app','scripts']:
        root=ROOT/base
        if root.exists():
            for py in root.rglob('*.py'):
                rel=str(py.relative_to(ROOT)).replace('\\','/')
                text=py.read_text(encoding='utf-8',errors='replace')
                if 'static/data' in text or ('STATIC_DATA_PATH' in text and rel!='app/runtime/runtime_data_paths.py'):
                    result['backend_static_reference_files'].append(rel)
    result['summary']={'expected_runtime_file_count':len(FILES),'runtime_file_count':len(FILES)-len(result['missing_runtime']),'missing_runtime_count':len(result['missing_runtime']),'unreadable_runtime_count':len(result['unreadable_runtime']),'remaining_static_count':len(result['remaining_static']),'frontend_static_reference_count':len(result['frontend_static_references']),'backend_static_reference_file_count':len(result['backend_static_reference_files']),'validation_state':'PASS'}
    if result['missing_runtime']: fail('runtime files are missing', result)
    if result['unreadable_runtime']: fail('runtime files are unreadable', result)
    if result['remaining_static']: fail('static fallback files still remain', result)
    if result['frontend_static_references']: fail('frontend static/data references remain', result)
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result['summary'],indent=2))
    print('Report:', str(REPORT.relative_to(ROOT)).replace('\\','/'))
    return 0
if __name__=='__main__': raise SystemExit(main())
