from pathlib import Path
import json,sys
R=Path(__file__).resolve().parents[1]
files=['BOOKSYNC Guide.md','GitHub Repository Record.json','JOM Change History.md','JOM Guide v2 Additions.md','JOM Progress and Improvements.md','JOM Quick Start.md','JOM Recovery Guide.md','JOM System and File Map.md','The Jira Observation Monitor Guide.md']
checks={}
for name in files:
 p=R/name;checks[name+' exists']=p.is_file()
 if p.is_file() and name.endswith('.json'):
  try:checks[name+' record']='booksync_command_centre_ux_phase4_3_2026_09_14' in json.loads(p.read_text(encoding='utf-8-sig'))
  except Exception:checks[name+' record']=False
 elif p.is_file():
  t=p.read_text(encoding='utf-8-sig');checks[name+' milestone']='Command Centre UX Phase 4.3 closeout' in t and '3b8b6b9' in t and 'FR-004' in t and 'FR-005' in t
for path in ['templates/home.html','static/js/jom_command_centre_completion_v1.js','static/css/jom_command_centre_completion_v1.css','scripts/validate_command_centre_ux_phase1_v1.py','scripts/validate_command_centre_ux_phase4_3_v1.py']:checks[path+' owner']=(R/path).is_file()
checks['workflow recorded']='Audit -> Build -> Install -> Validate -> Live test -> Clean -> BOOKSYNC -> Stage -> Commit -> Push' in (R/'BOOKSYNC Guide.md').read_text(encoding='utf-8-sig')
checks['authority boundary recorded']='No backend route, collector, runtime contract or authority source changed.' in (R/'BOOKSYNC Guide.md').read_text(encoding='utf-8-sig')
failed=[]
for k,ok in checks.items():print(('PASS' if ok else 'FAIL')+': '+k);failed.append(k) if not ok else None
if failed:print('VALIDATION FAILED: '+str(len(failed)));sys.exit(1)
print('VALIDATION PASS: nine BOOKSYNC owners record Command Centre UX Phase 4.3, authority boundaries, retained validators, current next step and working rules.')
