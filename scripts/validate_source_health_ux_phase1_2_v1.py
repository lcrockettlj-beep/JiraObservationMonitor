from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
js=(ROOT/"static/js/jom_system_truth_v1.js").read_text(encoding="utf-8-sig")
checks={
"empty containers bypass fallback": 'if(text!==null&&text!==undefined&&text!=="")x.textContent=safe(text)' in js,
"old unconditional helper removed": 'const x=document.createElement(tag);x.textContent=safe(text)' not in js,
"genuine unavailable fallback retained": '?"Unavailable":String(v)' in js,
"explicit freshness fields retained": 'operator_label' in js and 'freshness_state' in js,
"runtime rendering retained": 'function runtime(d)' in js and '/api/system/runtime-dashboard' in js,
"source rendering retained": '/api/system/source-health-dashboard' in js}
failed=[]
for label,ok in checks.items():
 print(("PASS" if ok else "FAIL")+": "+label)
 if not ok: failed.append(label)
if failed: print("VALIDATION FAILED: "+str(len(failed)));sys.exit(1)
print("VALIDATION PASS: Source Health UX Phase 1.2 removes false Unavailable prefixes while preserving genuine unavailable values.")
