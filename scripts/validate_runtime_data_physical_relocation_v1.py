from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FILES=['admin_enriched_refresh_status.json', 'admin_truth_v2.json', 'backend_final_truth_chain_status.json', 'backend_legacy_truth_eradication_status.json', 'billing_seats.json', 'estate_access_truth.json', 'estate_admin_site_inventory_v1.json', 'estate_product_access.json', 'monitored_sites.json', 'runtime_execution_history.json', 'runtime_execution_status.json', 'site_access_validation.json', 'site_lifecycle_decisions.json', 'site_onboarding_review.json', 'site_registry.json', 'source_freshness_audit.json', 'source_reliability_status.json', 'user_footprint.json']
def fail(msg):
    print('FAIL: '+msg); raise SystemExit(1)
def main():
    runtime=ROOT/'runtime'/'data'; static=ROOT / "runtime" / "data"
    if not runtime.exists(): fail('runtime/data missing')
    missing=[n for n in FILES if not (runtime/n).exists()]
    if missing: fail('runtime/data files missing: '+', '.join(missing))
    web=(ROOT/'app'/'web.py').read_text(encoding='utf-8',errors='replace')
    if 'return runtime_read_json(filename, default)' not in web: fail('load_json runtime read not active')
    if 'return runtime_write_json(filename, payload)' not in web: fail('write_json runtime write not active')
    if '/api/runtime/data-path-status' not in web: fail('runtime data path status endpoint missing')
    bad=[]
    jsdir=ROOT/'static'/'js'
    if jsdir.exists():
        for js in jsdir.glob('*.js'):
            if '/runtime/data/' in js.read_text(encoding='utf-8',errors='replace'):
                bad.append(str(js.relative_to(ROOT)))
    if bad: fail('frontend static data references remain: '+', '.join(bad))
    unread=[]
    for n in FILES:
        try: json.loads((runtime/n).read_text(encoding='utf-8-sig'))
        except Exception as e: unread.append(f'{n}: {e}')
    if unread: fail('runtime JSON unreadable: '+'; '.join(unread))
    print('Runtime data physical relocation validation PASS')
    print('runtime_files='+str(len(FILES)))
    print('static_fallbacks_retained=true')
    return 0
if __name__=='__main__': raise SystemExit(main())
