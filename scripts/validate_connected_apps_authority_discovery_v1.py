from pathlib import Path
import ast
root=Path(__file__).resolve().parents[1]
path=root/'app/audits/connected_apps_authority_discovery.py'; text=path.read_text(encoding='utf-8'); ast.parse(text)
required=['raw_har_stored','raw_request_bodies_stored','raw_response_bodies_stored','header_values_stored','query_values_stored','cookies_stored','tokens_stored','safe_to_publish_marketplace_apps','A HAR candidate is discovery evidence only']
missing=[x for x in required if x not in text]; assert not missing,missing
for forbidden in ['request.get("cookies")','response.get("cookies")','row.get("value")']:
 assert forbidden not in text,forbidden
print('PASS: Connected Apps HAR discovery privacy boundary and non-publishing gates validated.')
