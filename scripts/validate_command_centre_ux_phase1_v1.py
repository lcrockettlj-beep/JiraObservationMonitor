from pathlib import Path
import re,sys
R=Path(__file__).resolve().parents[1];h=(R/'templates/home.html').read_text(encoding='utf-8-sig');j=(R/'static/js/jom_command_centre_completion_v1.js').read_text(encoding='utf-8-sig');c=(R/'static/css/jom_command_centre_completion_v1.css').read_text(encoding='utf-8-sig')
checks={'existing API retained':'/api/workspace/command-centre' in j,'single API only':set(re.findall(r"['\"](/api/[^'\"]+)['\"]",j))=={'/api/workspace/command-centre'},'priority metrics':all(x in h for x in ['jom-priority-immediate','jom-priority-review','jom-priority-healthy']),'priority model':'function priority(a)' in j,'authority domains':'function domain(a)' in j,'grouped actions':'jom-command-action-group' in j,'empty state':'No immediate operational actions' in j,'scope retained':'JOM_CURRENT_STATE_ALLOWED_KEYS_V1' in j,'monitoring visual':'renderMonitoringWall(root,r,u,o,a)' in j,'right rail bindings':all(x in h for x in ['jom-operations-rail','jom-rail-overall-health','jom-rail-monitoring-coverage','jom-rail-runtime','jom-rail-alerts','jom-rail-users'])}
f=[]
for k,v in checks.items():print(('PASS' if v else 'FAIL')+': '+k);f.append(k) if not v else None
if f:sys.exit(1)
print('VALIDATION PASS: Command Centre UX Phase 1 functions and fixed operations rail are retained.')
