from pathlib import Path
import sys
R=Path(__file__).resolve().parents[1]
j=(R/'static/js/jom_command_centre_completion_v1.js').read_text(encoding='utf-8-sig')
checks={'Monitoring Wall renderer retained':'function renderMonitoringWall(root,r,u,o,a)' in j,'monitor site-name helper defined':'function monitorSiteName(site)' in j,'monitor site-key helper defined':'function monitorSiteKey(site)' in j,'site renderer uses defined helper':'monitorSiteName(site)' in j,'obsolete NOC name helper absent':'nocSiteName' not in j,'obsolete NOC key helper absent':'nocSiteKey' not in j}
failed=[]
for label,ok in checks.items():
 print(('PASS' if ok else 'FAIL')+': '+label)
 if not ok: failed.append(label)
if failed: print('VALIDATION FAILED: '+str(len(failed)));sys.exit(1)
print('VALIDATION PASS: Monitoring Wall site rendering uses defined Phase 3 helpers and contains no obsolete NOC helper references.')
