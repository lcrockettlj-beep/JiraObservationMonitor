from pathlib import Path
import sys
R=Path(__file__).resolve().parents[1];h=(R/'templates/admin_discovery.html').read_text(encoding='utf-8-sig')
expected={'Review backlog':'discovery-rail-review','Validation blockers':'discovery-rail-access','Monitoring candidates':'discovery-rail-ready','Monitoring enabled':'discovery-rail-monitored'}
f=[]
for label,binding in expected.items():
 ok=label in h and f'id="{binding}"' in h;print(('PASS' if ok else 'FAIL')+f': rail owner {label} -> {binding}');f.append(label) if not ok else None
old=['<dt>Identities</dt>','<dt>Review</dt>','<dt>Monitored</dt>','<dt>Sources</dt>'];ok=all(x not in h for x in old);print(('PASS' if ok else 'FAIL')+': old passive rail labels absent');f.append('old labels') if not ok else None
if f:print('VALIDATION FAILED: '+str(len(f)));sys.exit(1)
print('VALIDATION PASS: Discovery UX Phase 1 right rail uses complete workflow labels and bindings.')
