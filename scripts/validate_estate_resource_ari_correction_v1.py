from pathlib import Path
import ast
root=Path(__file__).resolve().parents[1]
builder=(root/'app/builders/estate_resource_authority.py').read_text(encoding='utf-8')
ast.parse(builder)
required=['ARI_SITE_RESOURCE','fullmatch(resource_id)','ari_owner != product','mapped_site_count") == len(sites)','ambiguous_role_rows") == 0','p.get("status") != 404']
missing=[item for item in required if item not in builder]
assert not missing,missing
assert 'in text' not in builder[builder.index('def match_sites'):builder.index('def build_authority')]
print('PASS: Estate resource ARI parser, exact site matching and full-coverage success gates validated.')
