from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "reports" / "site_onboarding_action_template_binding_status.json"
CSS_LINK = "<link rel=\"stylesheet\" href=\"{{ url_for('static', filename='css/site_onboarding_review.css') }}\">"
JS_SCRIPT = "<script defer src=\"{{ url_for('static', filename='js/site_onboarding_review.js') }}\"></script>"


def inject(path: Path) -> dict:
    if not path.exists():
        return {"path": str(path), "exists": False, "changed": False}
    text = path.read_text(encoding="utf-8", errors="replace")
    original = text
    if CSS_LINK not in text:
        text = text.replace("</head>", f"  {CSS_LINK}\n</head>") if "</head>" in text else CSS_LINK + "\n" + text
    if JS_SCRIPT not in text:
        text = text.replace("</body>", f"  {JS_SCRIPT}\n</body>") if "</body>" in text else text + "\n" + JS_SCRIPT + "\n"
    if text != original:
        backup = ROOT / "backups" / f"site_onboarding_action_template_binding_{datetime.now().strftime('%Y%m%d_%H%M%S')}" / path.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
        path.write_text(text, encoding="utf-8")
        return {"path": str(path), "exists": True, "changed": True, "backup": str(backup)}
    return {"path": str(path), "exists": True, "changed": False}


def main() -> int:
    results = [inject(ROOT / "templates" / "home.html"), inject(ROOT / "templates" / "reference.html")]
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps({"schema": "jom-site-onboarding-action-template-binding-v1", "results": results}, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "results": results}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
