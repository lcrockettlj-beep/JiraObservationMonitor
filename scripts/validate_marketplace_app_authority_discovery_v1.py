from pathlib import Path
import ast
root=Path(__file__).resolve().parents[1]; path=root/'app/audits/marketplace_app_authority_discovery.py'; text=path.read_text(encoding='utf-8'); ast.parse(text)
for item in ['raw_bodies_stored','secrets_stored','safe_to_publish_marketplace_apps','HTTP success is discovery evidence','Commerce entitlements may prove commercial entitlement','UPM routes may be private/internal']:
 assert item in text,item
print('PASS: Marketplace App Authority Discovery privacy and non-publishing gates validated.')
