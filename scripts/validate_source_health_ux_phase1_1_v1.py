from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
js=(ROOT/'static/js/jom_system_truth_v1.js').read_text(encoding='utf-8-sig')
failed=[]
def check(label,ok):
 print(('PASS' if ok else 'FAIL')+': '+label)
 if not ok: failed.append(label)
for token in ['freshness?.sources','reliability?.issues','product_access_refresh?.steps','operator_label','freshness_state','parsed_timestamp_utc','runtime(d)']:
 check('contract-driven owner contains '+token,token in js)
check('generic recursive source guessing removed','function records(' not in js)
check('runtime dashboard support preserved','/api/system/runtime-dashboard' in js and 'mode==="runtime"?runtime(d):source(d)' in js)
check('source health dashboard retained','/api/system/source-health-dashboard' in js)
check('privacy wording retained','Secrets and tokens are never rendered' in js)
if failed: print('VALIDATION FAILED: '+str(len(failed))); sys.exit(1)
print('VALIDATION PASS: Source Health UX Phase 1.1 uses explicit contract fields and preserves Runtime Status rendering.')
