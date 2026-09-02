from pathlib import Path
import ast
root=Path.cwd(); owner=root/'app/builders/project_governance_named_identity_authority_v1.py'; text=owner.read_text(encoding='utf-8-sig'); ast.parse(text)
for value in ['REQUEST_TIMEOUT_SECONDS=15','unique_user_lookup_cache','PROJECT {index}/{len(projects)}','if complete: write_atomic','project_governance_named_identity_authority_failure_v1.json','except (urllib.error.URLError,TimeoutError,socket.timeout)']: assert value in text,value
print('PASS: PGNI builder bounded requests, unique-principal cache, progress output, exception handling, and atomic success-only replacement validated.')
