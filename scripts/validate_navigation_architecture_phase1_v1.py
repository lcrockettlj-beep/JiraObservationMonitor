from pathlib import Path
import re, sys
ROOT=Path(__file__).resolve().parents[1]
nav=(ROOT/'templates/_nav.html').read_text(encoding='utf-8-sig')
css=(ROOT/'static/css/jom_navigation_remediation_phase1_v1.css').read_text(encoding='utf-8-sig')
web=(ROOT/'app/web.py').read_text(encoding='utf-8-sig')
routes=[
'/reports/governance','/reports/governance/projects','/reports/governance/users','/reports/governance/configuration','/reports/governance/permissions','/reports/governance/policy-compliance',
'/runtime-status','/system/runtime-status/application','/system/runtime-status/api','/system/runtime-status/collectors','/system/runtime-status/jobs','/system/runtime-status/errors',
'/source-health','/system/source-health/connections','/system/source-health/authentication','/system/source-health/freshness','/system/source-health/completeness','/system/source-health/failures']
failed=[]
def check(label,ok):
 print(('PASS' if ok else 'FAIL')+': '+label)
 if not ok: failed.append(label)
check('Navigation Phase 1 stylesheet is loaded by shared navigation owner',"css/jom_navigation_remediation_phase1_v1.css" in nav)
for route in routes:
 check('navigation exposes '+route,('href="'+route+'"') in nav)
 pattern=r"@app\.route\([\"']"+re.escape(route)+r"[\"']"
 check('Flask route exists '+route,re.search(pattern,web) is not None)
for label in ['Governance navigation','Runtime navigation','Source Health navigation']:
 check('semantic subnavigation exists: '+label,label in nav)
check('active subnavigation styling exists','.jom-nav-subnav--active' in css)
check('sidebar supports internal scrolling','overflow-y:auto' in css)
check('API routes are not exposed as navigation links','href="/api/' not in nav)
if failed:
 print('VALIDATION FAILED: '+str(len(failed))); sys.exit(1)
print('VALIDATION PASS: Navigation Architecture Phase 1 exposes supported operator pages without backend changes.')
