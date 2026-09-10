from pathlib import Path
import re,sys
ROOT=Path(__file__).resolve().parents[1]
js=(ROOT/'static/js/jom_system_truth_v1.js').read_text(encoding='utf-8-sig')
css=(ROOT/'static/css/jom_system_truth_v1.css').read_text(encoding='utf-8-sig')
checks={
'attention ranking owner exists':'const attentionWeight=' in js and 'const attentionItems=' in js,
'blocked steps rank first':'blocked(x.item)?100' in js,
'failed steps rank before contracts':'low(x.item.status)==="failed"?95' in js,
'unavailable contracts rank before review contracts':'contractBand(x.item)==="UNAVAILABLE"?70:50' in js,
'long jobs rank before review-duration jobs':'x.duration>60?40:20' in js,
'recommendations derive from evidence':'const recommendedAction=' in js,
'overview exposes top five':'attention.slice(0,5)' in js,
'triage is included in raw evidence':'triage:{rule:' in js and 'recommended_action:recommendedAction(x)' in js,
'no fabricated health score':'healthScore' not in js and 'attentionScore' not in js,
'phase 1.1 views retained':all(('function runtime'+x+'(') in js for x in ['Overview','Application','Api','Collectors','Jobs','Errors']),
'approved APIs only':set(re.findall(r'["\'](/api/[^"\']+)["\']',js))=={'/api/system/runtime-dashboard','/api/system/source-health-dashboard'},
'source health owner retained':'function source(d)' in js and 'mode==="runtime"?runtime(d):source(d)' in js,
'triage styling exists':'.sys-truth__triage' in css and '.sys-truth__triage--blocked' in css}
failed=[]
for label,ok in checks.items():
 print(('PASS' if ok else 'FAIL')+': '+label)
 if not ok:failed.append(label)
if failed:print('VALIDATION FAILED: '+str(len(failed)));sys.exit(1)
print('VALIDATION PASS: Runtime UX Phase 1.2 ranks current evidence for operator triage without fabricating authority or health scores.')
