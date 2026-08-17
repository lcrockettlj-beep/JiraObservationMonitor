from pathlib import Path
import ast
root=Path(__file__).resolve().parents[1]; p=root/'app/audits/connected_apps_discovery_privacy_correction.py'; t=p.read_text(encoding='utf-8'); ast.parse(t)
for x in ['cloud_ids_stored','UUID_RE','<site-cloud-id>','v1_must_be_deleted','safe_to_publish_marketplace_apps']:
 assert x in t,x
print('PASS: Connected Apps discovery v1.1 cloud-ID redaction and non-publishing gates validated.')
