from pathlib import Path
import json,sys
R=Path(__file__).resolve().parents[1];md=['BOOKSYNC Guide.md','JOM Change History.md','JOM Guide v2 Additions.md','JOM Progress and Improvements.md','JOM Quick Start.md','JOM Recovery Guide.md','JOM System and File Map.md','The Jira Observation Monitor Guide.md'];req=['11 September 2026 - Discovery UX Phase 1 operator workflow closeout','JOM_ADMIN_DISCOVERY_AUTHORITY_INTEGRATION_V1','Review backlog','Validation blockers','Monitoring candidates','GENERATED_RUNTIME','FR-005 remaining surface classification'];f=[]
for n in md:
 p=R/n;ok=p.is_file() and all(x in p.read_text(encoding='utf-8-sig') for x in req);print(('PASS' if ok else 'FAIL')+': Discovery UX closeout aligned: '+n);f.append(n) if not ok else None
d=json.loads((R/'GitHub Repository Record.json').read_text(encoding='utf-8-sig'));x=d.get('booksync_discovery_ux_phase1_closeout_2026_09_11',{});checks={'repository closeout exists':bool(x),'owner marker recorded':x.get('required_owner_marker')=='JOM_ADMIN_DISCOVERY_AUTHORITY_INTEGRATION_V1','six owners recorded':len(x.get('product_owners',[]))==6,'authority unchanged':all(x.get(k) is False for k in ['new_collectors','new_runtime_contracts','new_backend_routes','authority_semantics_changed'])}
for n,ok in checks.items():print(('PASS' if ok else 'FAIL')+': '+n);f.append(n) if not ok else None
if f:sys.exit(1)
print('VALIDATION PASS: Discovery UX Phase 1 BOOKSYNC closeout owners are aligned.')
