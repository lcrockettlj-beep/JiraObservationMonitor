from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'scripts/validate_source_health_ux_phase1_v1.py'
t=p.read_text(encoding='utf-8-sig')
checks={
'obsolete one-endpoint count removed': "js.count('/api/')==1" not in t,
'approved endpoint set exists': "approved_api_endpoints={'/api/system/source-health-dashboard','/api/system/runtime-dashboard'}" in t,
'exact endpoint-set comparison exists': 'found_api_endpoints==approved_api_endpoints' in t,
'navigation validator retained': (ROOT/'scripts/validate_navigation_architecture_phase1_v1.py').is_file(),
'phase 1.1 validator retained': (ROOT/'scripts/validate_source_health_ux_phase1_1_v1.py').is_file(),
'phase 1.2 validator retained': (ROOT/'scripts/validate_source_health_ux_phase1_2_v1.py').is_file()}
failed=[]
for label,ok in checks.items():
 print(('PASS' if ok else 'FAIL')+': '+label)
 if not ok: failed.append(label)
if failed: print('VALIDATION FAILED: '+str(len(failed)));sys.exit(1)
print('VALIDATION PASS: Source Health Phase 1 validator is aligned to the approved shared Runtime and Source Health API owner.')
