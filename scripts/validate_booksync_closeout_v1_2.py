from pathlib import Path
import json, sys
root=Path(__file__).resolve().parents[1]
guide=root/'JOM Living Guide'
books=["BOOKSYNC Guide.md","JOM Change History.md","JOM Guide v2 Additions.md","JOM Progress and Improvements.md","JOM Quick Start.md","JOM Recovery Guide.md","JOM System and File Map.md","The Jira Observation Monitor Guide.md"]
terms=["Site Workspace and Discovery operational completion closeout","7a51d3ec489c4405de285fe136a65f4957f950ae","ec38a54d576ffb68d621df83575593146dc17d82","Controlled Repository Hygiene Classification","FR-004 timestamp meaning consistency remains","scripts/validate_discovery_authority_integration_v1.py"]
checks=[]
for name in books:
 path=guide/name
 checks.append((f"tracked BOOKSYNC owner exists: JOM Living Guide/{name}",path.is_file()))
 if path.is_file():
  text=path.read_text(encoding='utf-8-sig')
  for term in terms: checks.append((f"JOM Living Guide/{name}: {term}",term in text))
record_path=guide/'GitHub Repository Record.json'
checks.append(('tracked GitHub record exists',record_path.is_file()))
if record_path.is_file():
 data=json.loads(record_path.read_text(encoding='utf-8-sig'))
 record=data.get('booksync_site_workspace_discovery_closeout_2026_09_08',{})
 checks += [('GitHub record head',record.get('head_commit')=='ec38a54d576ffb68d621df83575593146dc17d82'),('GitHub record Site Workspace commit',record.get('site_workspace_project_authority_integration',{}).get('commit')=='7a51d3ec489c4405de285fe136a65f4957f950ae'),('GitHub record current workstream',record.get('current_workstream')=='Controlled Repository Hygiene Classification'),('GitHub record FR-004 honest',record.get('foundation_recovery',{}).get('FR-004')=='open_evidence_controlled_limitation')]
for name in [*books,'GitHub Repository Record.json']:
 checks.append((f"incorrect root duplicate absent: {name}",not (root/name).exists()))
failed=[name for name,ok in checks if not ok]
for name,ok in checks: print(('PASS' if ok else 'FAIL')+': '+name)
if failed:
 print(f'VALIDATION FAILED: {len(failed)}')
 sys.exit(1)
print('VALIDATION PASS: BOOKSYNC Closeout v1.2 tracked owner boundary.')
