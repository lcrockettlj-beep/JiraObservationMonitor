from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
checks = []
def require(condition, message):
    checks.append((bool(condition), message))
html = (ROOT / "templates" / "admin.html").read_text(encoding="utf-8")
js = (ROOT / "static" / "js" / "jom_admin_home_v1.js").read_text(encoding="utf-8")
require("jom_admin_home_v1.js" in html, "Admin Home loads its dedicated consumer")
require("jom_atlassian_command.css" in html and "jom_visual_consistency_v2.css" in html, "Shared CSS owners retained")
require("jom_admin_home_v1.css" not in html, "No duplicate Admin Home CSS owner introduced")
for endpoint in ("/api/admin/estate-configuration", "/api/admin/monitoring", "/api/admin/licensing-billing", "/api/admin/users-access", "/api/admin/system-configuration"):
    require(endpoint in js, f"Consumer uses {endpoint}")
require("/api/admin/discovery" not in js, "Discovery authority is not inferred")
require("cache: \"no-store\"" in js, "Browser requests bypass HTTP cache")
require("Promise.all" in js, "Established Admin contracts load concurrently")
failed = [message for ok, message in checks if not ok]
for ok, message in checks:
    print(("PASS" if ok else "FAIL") + ": " + message)
if failed:
    sys.exit(1)
print("PASS: Admin Home Operationalisation v1 static boundary validated")
