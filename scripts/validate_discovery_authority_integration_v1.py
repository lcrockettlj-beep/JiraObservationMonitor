from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
checks=[]
def need(path,terms):
 text=(root/path).read_text(encoding="utf-8-sig")
 for term in terms: checks.append((f"{path}: {term}",term in text))
need(Path("templates/admin_discovery.html"),["data-owner=\"JOM_ADMIN_DISCOVERY_AUTHORITY_INTEGRATION_V1\"","jom_admin_discovery_v1.css","jom_admin_discovery_v1.js","discovery-review-rows","discovery-source-grid","Retired sites","Static fallback"])
need(Path("static/js/jom_admin_discovery_v1.js"),["/api/estate/discovery-authority","/api/estate/discovery-authority/coverage","static_fallback_used===false","rows.filter(review)","/estate/review/"])
need(Path("static/css/jom_admin_discovery_v1.css"),["JOM_ADMIN_DISCOVERY_AUTHORITY_INTEGRATION_V1","admin-discovery-source--ok","admin-discovery-badge--review","admin-discovery-rail"])
web=(root/"app/web.py").read_text(encoding="utf-8-sig")
for route in ["/api/estate/discovery-authority","/api/estate/discovery-authority/coverage"]: checks.append((f"app/web.py existing route: {route}",route in web))
failed=[name for name,ok in checks if not ok]
for name,ok in checks: print(("PASS" if ok else "FAIL")+": "+name)
if failed: print(f"VALIDATION FAILED: {len(failed)}");sys.exit(1)
print("VALIDATION PASS: Discovery authority integration owner boundary.")
