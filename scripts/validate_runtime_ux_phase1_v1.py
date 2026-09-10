from pathlib import Path
import re,sys
ROOT=Path(__file__).resolve().parents[1]
pages={"runtime_status.html":"overview","runtime_application.html":"application","runtime_api.html":"api","runtime_collectors.html":"collectors","runtime_jobs.html":"jobs","runtime_errors.html":"errors"}
failed=[]
def check(label,ok):
 print(('PASS' if ok else 'FAIL')+': '+label)
 if not ok: failed.append(label)
for name,mode in pages.items():
 p=ROOT/'templates'/name;check('template exists: '+name,p.is_file())
 if p.is_file():
  t=p.read_text(encoding='utf-8-sig');check('unique runtime view: '+name,('data-runtime-view="'+mode+'"') in t);check('shared detail owner: '+name,'id="sys-detail"' in t);check('raw evidence retained: '+name,'id="sys-raw"' in t)
js=(ROOT/'static/js/jom_system_truth_v1.js').read_text(encoding='utf-8-sig');css=(ROOT/'static/css/jom_system_truth_v1.css').read_text(encoding='utf-8-sig')
for mode in pages.values(): check('JavaScript specialises '+mode,re.search(r'function\s+runtime'+mode.capitalize()+r'\s*\(',js) is not None)
check('runtime dashboard API retained','/api/system/runtime-dashboard' in js)
check('source health dashboard support retained','/api/system/source-health-dashboard' in js and 'mode==="runtime"?runtime(d):source(d)' in js)
check('no third API introduced',set(re.findall(r'["\'](/api/[^"\']+)["\']',js))=={'/api/system/runtime-dashboard','/api/system/source-health-dashboard'})
check('runtime raw evidence implemented','dataset.runtimeView' in js and '$('+'"sys-raw"'+')' in js)
check('detail presentation retained','.sys-truth__detail' in css)
if failed: print('VALIDATION FAILED: '+str(len(failed)));sys.exit(1)
print('VALIDATION PASS: Runtime UX Phase 1 provides six specialised operator views over the existing runtime dashboard contract.')
