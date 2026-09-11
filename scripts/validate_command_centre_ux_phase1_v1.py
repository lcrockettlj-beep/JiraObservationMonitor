from pathlib import Path
import re,sys
R=Path(__file__).resolve().parents[1]
h=(R/'templates/home.html').read_text(encoding='utf-8-sig');j=(R/'static/js/jom_command_centre_completion_v1.js').read_text(encoding='utf-8-sig');c=(R/'static/css/jom_command_centre_completion_v1.css').read_text(encoding='utf-8-sig')
checks={'existing API retained':'/api/workspace/command-centre' in j,'single API only':set(re.findall(r"['\"](/api/[^'\"]+)['\"]",j))=={'/api/workspace/command-centre'},'priority metrics':all(x in h for x in ['jom-priority-immediate','jom-priority-review','jom-priority-healthy']),'priority model':'function priority(a)' in j and 'function priorityLabel(v)' in j,'authority domains':'function domain(a)' in j and all(x in j for x in ['Runtime','Estate & Discovery','Source Health','Users & Access']),'grouped actions':'jom-command-action-group' in j,'empty healthy state retained':'No immediate operational actions' in j,'current-state scope retained':'JOM_CURRENT_STATE_ALLOWED_KEYS_V1' in j,'NOC authority retained':'renderNocDisplay(root,r)' in j,'duplicate NOC block removed':c.count('JOM_COMMAND_CENTRE_NOC_LIGHT_THEME_OWNER_CLEANUP_V1 START')==1,'new styles':'.jom-command-priority-metrics' in c and '.jom-command-action-grid' in c,'passive rail refined':'Estate review' in h and 'Immediate actions' in h}
f=[]
for k,v in checks.items():print(('PASS' if v else 'FAIL')+': '+k);f.append(k) if not v else None
if f:print('VALIDATION FAILED: '+str(len(f)));sys.exit(1)
print('VALIDATION PASS: Command Centre UX Phase 1 adds authority-derived operational prioritisation without new routes or authority.')
