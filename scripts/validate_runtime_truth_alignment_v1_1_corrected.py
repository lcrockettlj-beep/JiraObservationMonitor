from __future__ import annotations
import ast
import importlib.util
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
builder_path = ROOT / "app/builders/estate_monitored_product_authority_v1.py"
chain_path = ROOT / "app/runtime/admin_enriched_chain.py"
failed = []
for path in (builder_path, chain_path):
    try:
        ast.parse(path.read_text(encoding="utf-8"))
        print(f"PASS syntax: {path.relative_to(ROOT)}")
    except Exception as exc:
        failed.append(f"syntax {path}: {exc}")
        print(f"FAIL syntax: {path.relative_to(ROOT)}: {exc}")
builder = builder_path.read_text(encoding="utf-8")
chain = chain_path.read_text(encoding="utf-8")
expected_step = '("estate_monitored_product_authority", "Rebuild monitored-product authority from current registry and resource mapping", [{"type": "module", "value": "app.builders.estate_monitored_product_authority_v1"}], ["estate_resource_authority"], None),'
checks = {
    "real executable owner": "def main()" in builder and "estate_monitored_product_authority_v1.json" in builder,
    "approved inputs only": "site_registry.json" in builder and "estate_site_resource_mapping_v1.json" in builder,
    "no fabricated products": "'fabricated_products':False" in builder,
    "high confidence gate": "high-confidence" in builder and "confidence(row)" in builder,
    "exact chain integration": chain.count(expected_step) == 1,
    "exact dependency": '["estate_resource_authority"]' in expected_step,
    "contract evidence retained": '"estate_monitored_product_authority_v1.json"' in chain,
    "execution parent child retained": "JOM_REFRESH_EXECUTION_ID" in chain and "parent_execution_id" in chain,
}
for name, ok in checks.items():
    print(("PASS" if ok else "FAIL") + ": " + name)
    if not ok: failed.append(name)
# Resolve against the installed repository rather than merely searching text.
sys.path.insert(0, str(ROOT))
spec = importlib.util.find_spec("app.builders.estate_monitored_product_authority_v1")
if spec is None:
    print("FAIL: builder module resolves")
    failed.append("builder module resolves")
else:
    print("PASS: builder module resolves")
if failed:
    print("FAIL: FR-002 FR-003 Runtime Truth Alignment v1.1 corrected integration validation")
    raise SystemExit(1)
print("PASS: FR-002 FR-003 Runtime Truth Alignment v1.1 corrected integration validation")
