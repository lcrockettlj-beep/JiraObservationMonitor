from pathlib import Path
import re,sys
ROOT=Path(__file__).resolve().parents[1]
pages={"source_health.html":"overview","source_connections.html":"connections","source_authentication.html":"authentication","source_freshness.html":"freshness","source_completeness.html":"completeness","source_failures.html":"failures"}
failed=[]
def check(label,ok):
 print(("PASS" if ok else "FAIL")+": "+label)
 if not ok: failed.append(label)
for name,mode in pages.items():
 p=ROOT/"templates"/name; check("template exists: "+name,p.is_file())
 if p.is_file():
  t=p.read_text(encoding="utf-8-sig"); check("unique source view: "+name,('data-source-view="'+mode+'"') in t); check("shared detail owner: "+name,'id="sys-detail"' in t)
js=(ROOT/"static/js/jom_system_truth_v1.js").read_text(encoding="utf-8-sig")
css=(ROOT/"static/css/jom_system_truth_v1.css").read_text(encoding="utf-8-sig")
for mode in pages.values(): check("JavaScript specialises "+mode,re.search(r"function\s+"+mode+r"\s*\(",js) is not None)
check("existing source-health API retained",'/api/system/source-health-dashboard' in js)
approved_api_endpoints={'/api/system/source-health-dashboard','/api/system/runtime-dashboard'}
found_api_endpoints=set(re.findall(r"[\"\'](/api/[^\"\']+)[\"\']",js))
check("only approved shared-owner API endpoints are present",found_api_endpoints==approved_api_endpoints)
check("raw evidence remains available",'sys-raw' in js)
check("privacy-safe authentication wording",'Secrets and tokens are never rendered' in js)
check("specialist detail grid styled",'.sys-truth__detail' in css)
if failed: print("VALIDATION FAILED: "+str(len(failed))); sys.exit(1)
print("VALIDATION PASS: Source Health UX Phase 1 provides six distinct frontend views over the existing authority contract.")
