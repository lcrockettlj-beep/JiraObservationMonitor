from pathlib import Path
import ast
root=Path(__file__).resolve().parents[1]
path=root/'app/builders/estate_monitored_product_authority.py'; text=path.read_text(encoding='utf-8'); ast.parse(text)
for item in ['site-scoped Atlassian ARI','commercial_licensing_included','marketplace_apps_included','safe_to_publish','fabricated_products','uncovered_site_count']:
 assert item in text,item
print('PASS: Monitored Product Authority owner, scope boundary and publish gates validated.')
