from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
h=(ROOT/"templates/admin_discovery.html").read_text(encoding="utf-8-sig")
required='data-owner="JOM_ADMIN_DISCOVERY_AUTHORITY_INTEGRATION_V1"'
obsolete='data-owner="JOM_ADMIN_DISCOVERY_UX_PHASE1_V1"'
checks={"required integration owner marker retained":required in h,"incorrect UX owner marker absent":obsolete not in h,"Discovery UX priority host retained":'id="discovery-priority-grid"' in h}
failed=[]
for label,ok in checks.items():
 print(("PASS" if ok else "FAIL")+": "+label)
 if not ok: failed.append(label)
if failed: print("VALIDATION FAILED: "+str(len(failed)));sys.exit(1)
print("VALIDATION PASS: Discovery UX Phase 1 retains the validated Discovery integration owner contract.")
