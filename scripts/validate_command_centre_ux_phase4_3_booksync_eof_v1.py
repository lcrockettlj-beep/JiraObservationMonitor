from pathlib import Path
import json,sys
R=Path(__file__).resolve().parents[1]
files=['BOOKSYNC Guide.md','GitHub Repository Record.json','JOM Change History.md','JOM Guide v2 Additions.md','JOM Progress and Improvements.md','JOM Quick Start.md','JOM Recovery Guide.md','JOM System and File Map.md','The Jira Observation Monitor Guide.md']
checks={}
for name in files:
 p=R/name;b=p.read_bytes() if p.is_file() else b''
 checks[name+' exists']=p.is_file()
 checks[name+' single terminal newline']=b.endswith(b'\n') and not b.endswith(b'\n\n')
 if p.is_file() and name.endswith('.json'):
  try: checks[name+' milestone']='booksync_command_centre_ux_phase4_3_2026_09_14' in json.loads(p.read_text(encoding='utf-8-sig'))
  except Exception: checks[name+' milestone']=False
 elif p.is_file():
  t=p.read_text(encoding='utf-8-sig');checks[name+' milestone']='Command Centre UX Phase 4.3 closeout' in t and '3b8b6b9' in t
failed=[]
for label,ok in checks.items():
 print(('PASS' if ok else 'FAIL')+': '+label)
 if not ok: failed.append(label)
if failed: print('VALIDATION FAILED: '+str(len(failed)));sys.exit(1)
print('VALIDATION PASS: all nine Phase 4.3 BOOKSYNC owners have one terminal newline and retain the accepted milestone record.')
