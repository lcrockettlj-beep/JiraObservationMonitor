from pathlib import Path
import ast, json, sys
ROOT=Path(__file__).resolve().parents[1]
OWNERS=["scripts/build_site_registry.py","app/builders/project_inventory_authority_v1.py","app/builders/project_lead_authority_v1.py","app/builders/project_owner_authority_v1.py","app/builders/project_governance_named_identity_authority_v1.py","app/builders/named_user_display_identity_v1.py"]
EXPECTED={"site_registry.json":"site registry contract generation time","project_inventory_authority_v1.json":"project inventory authority contract generation time","project_lead_authority_v1.json":"project lead authority contract generation time","project_owner_authority_v1.json":"governance owner authority derivation time","project_governance_named_identity_authority_v1.json":"project governance named identity authority contract generation time","named_user_display_identity_v1.json":"named user display identity authority contract generation time"}
failed=[]
def check(label,ok):
 print(("PASS" if ok else "FAIL")+": "+label)
 if not ok: failed.append(label)
texts={}
for rel in OWNERS:
 p=ROOT/rel; check("owner exists: "+rel,p.is_file())
 if not p.is_file(): continue
 text=p.read_text(encoding="utf-8-sig"); texts[rel]=text
 try: ast.parse(text); syntax=True
 except SyntaxError: syntax=False
 check("Python syntax: "+rel,syntax)
check("canonical Site Registry producer publishes semantics",texts.get(OWNERS[0],"").count('"timestamp_semantics": {')==1)
# Three textual occurrences are expected: one function definition plus two payload calls.
check("Project Inventory fail-closed and success paths publish semantics",texts.get(OWNERS[1],"").count("timestamp_semantics()") == 3)
check("Named User Display Identity fail-closed and success contracts publish semantics",texts.get(OWNERS[5],"").count('"timestamp_semantics": {') == 2)
check("Project Owner labels upstream generation time",'upstream_project_lead_generated_at_utc' in texts.get(OWNERS[3],""))
for rel in OWNERS: check("owner rejects authority-change inference: "+rel,"authority_change_time" in texts.get(rel,"") and "not represented" in texts.get(rel,""))
for filename,meaning in EXPECTED.items():
 p=ROOT/"runtime/data"/filename; check("runtime contract exists: "+filename,p.is_file())
 if not p.is_file(): continue
 try: payload=json.loads(p.read_text(encoding="utf-8-sig"))
 except Exception: payload={}
 semantics=payload.get("timestamp_semantics",{}) if isinstance(payload,dict) else {}
 check("runtime generated_at meaning: "+filename,semantics.get("generated_at_utc")==meaning)
 source=str(semantics.get("source_collection_time") or "")
 check("runtime source collection not overstated: "+filename,source=="not represented" or source.startswith("not represented;"))
 check("runtime authority change not overstated: "+filename,semantics.get("authority_change_time")=="not represented")
if failed:
 print("VALIDATION FAILED: "+str(len(failed))); sys.exit(1)
print("VALIDATION PASS: FR-004 authority timestamp semantics are explicit and runtime-proven (v2.1).")
