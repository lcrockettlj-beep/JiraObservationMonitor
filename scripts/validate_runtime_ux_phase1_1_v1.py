from pathlib import Path
import re,sys
R=Path(__file__).resolve().parents[1];j=(R/'static/js/jom_system_truth_v1.js').read_text(encoding='utf-8-sig');c=(R/'static/css/jom_system_truth_v1.css').read_text(encoding='utf-8-sig')
checks={"overview priority":all(x in j for x in ['"Priority issue"','"Slowest job"','"Contracts in review"']),"API groups":all(x in j for x in ['"Unavailable contracts"','"Contracts requiring review"','"Healthy contracts"']),"collector families":'PROJECTS & GOVERNANCE' in j and 'USERS & ACCESS' in j,"job bands":all(x in j for x in ['"Long-running jobs"','"Jobs requiring duration review"','"Normal-duration jobs"']),"error groups":all(x in j for x in ['group(q,"Failed"','group(q,"Blocked"','group(q,"Review"']),"application priority":'"Current action"' in j and '"Last completed action"' in j,"runtime views":all(('function runtime'+x+'(') in j for x in ['Overview','Application','Api','Collectors','Jobs','Errors']),"approved APIs":set(re.findall(r'["\'](/api/[^"\']+)["\']',j))=={'/api/system/runtime-dashboard','/api/system/source-health-dashboard'},"source retained":'function source(d)' in j and 'mode==="runtime"?runtime(d):source(d)' in j,"styles":'.sys-truth__priority-group' in c}
f=[]
for k,v in checks.items():print(('PASS' if v else 'FAIL')+': '+k);f.append(k) if not v else None
if f:print('VALIDATION FAILED: '+str(len(f)));sys.exit(1)
print('VALIDATION PASS: Runtime UX Phase 1.1 operational prioritisation is present.')
