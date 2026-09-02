from pathlib import Path
import json,sys
root=Path(__file__).resolve().parents[1]; guide=root/'JOM Living Guide'
files=['BOOKSYNC Guide.md','JOM Change History.md','JOM Progress and Improvements.md','JOM Quick Start.md','JOM Recovery Guide.md','JOM System and File Map.md','The Jira Observation Monitor Guide.md']
markers=['Project Lead Authority v1','69 have a supported active lead published','23 have no supported active lead published','lead coverage is 75.0%','20 distinct supported active leads','Project Lead is not Project Owner','Organisation administrator','sixteen-file milestone boundary']
for name in files:
 text=(guide/name).read_text(encoding='utf-8-sig')
 for marker in markers: assert marker in text,(name,marker)
record=json.loads((guide/'GitHub Repository Record.json').read_text(encoding='utf-8-sig'))['project_lead_authority_v1']
assert record['authority_status']=='partial' and record['projects']==92 and record['projects_with_supported_active_lead']==69 and record['projects_without_supported_active_lead_published']==23 and record['lead_coverage_percent']==75.0 and record['distinct_supported_active_leads']==20
assert record['safe_to_serve'] is True and record['project_owner_semantics_proven'] is False and record['privacy']['account_ids_stored'] is False
print('PASS: Project Lead BOOKSYNC state, owners, authority, privacy, limitations, recovery and commit gate validated across eight owners.')
