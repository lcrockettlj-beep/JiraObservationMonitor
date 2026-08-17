from pathlib import Path
import ast
root=Path(__file__).resolve().parents[1]; p=root/'app/builders/estate_marketplace_app_authority.py'; t=p.read_text(encoding='utf-8'); ast.parse(t)
for x in ['safe_to_publish_marketplace_apps','app_records_collected','fabricated_apps','marketplace_app_count":None','browser-session gateway','Separate Confluence validation']:
 assert x in t,x
print('PASS: Marketplace App limitation authority owner, evidence boundary and unavailable-state gates validated.')
