from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
files=['BOOKSYNC Guide.md','JOM Change History.md','JOM Guide v2 Additions.md','JOM Progress and Improvements.md','JOM Quick Start.md','JOM Recovery Guide.md','JOM System and File Map.md','The Jira Observation Monitor Guide.md']
required=['10 September 2026 - Post-Recovery Website Milestone Closeout','Navigation Architecture Phase 1','Source Health UX Phase 1','Discovery Response import defect corrected' if False else "The Admin Discovery walkthrough exposed HTTP 500",'Runtime UX page specialisation','GENERATED_RUNTIME','REPORT_ONLY']
failed=[]
def check(label,ok):
 print(('PASS' if ok else 'FAIL')+': '+label)
 if not ok: failed.append(label)
for f in files:
 p=ROOT/f; check('BOOKSYNC owner exists: '+f,p.is_file())
 if p.is_file():
  t=p.read_text(encoding='utf-8-sig')
  check('current closeout record: '+f,all(x in t for x in required))
j=ROOT/'GitHub Repository Record.json'
try: d=json.loads(j.read_text(encoding='utf-8-sig')); rec=d.get('booksync_post_recovery_website_closeout_2026_09_10',{})
except Exception: rec={}
check('repository record closeout exists',bool(rec))
check('repository record validators pass',rec.get('navigation_architecture_phase1')=='pass' and rec.get('discovery_response_correction')=='pass')
check('next workstream recorded',rec.get('next_workstream')=='Runtime UX page specialisation')
if failed: print('VALIDATION FAILED: '+str(len(failed)));sys.exit(1)
print('VALIDATION PASS: Post-Recovery Website Milestone BOOKSYNC owners are aligned.')
