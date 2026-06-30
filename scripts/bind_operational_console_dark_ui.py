from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "reports" / "operational_console_dark_ui_template_binding_status.json"
CSS_LINK = "<link rel=\"stylesheet\" href=\"{{ url_for('static', filename='css/operational_console_dark.css') }}\">"
JS_SCRIPT = "<script defer src=\"{{ url_for('static', filename='js/operational_console_dark.js') }}\"></script>"
PANEL = """<!-- JOM_OPERATIONAL_CONSOLE_START -->
<section id="operational-console-panel" class="jom-operational-console" aria-label="Operational console status">
  <div class="jom-opcon-header">
    <div>
      <p class="jom-opcon-kicker">Operational Console</p>
      <h2>Runtime Health</h2>
    </div>
    <span id="jom-opcon-overall" class="jom-opcon-pill">Loading</span>
  </div>
  <div id="jom-opcon-cards" class="jom-opcon-grid"></div>
  <div id="jom-opcon-drilldown" class="jom-opcon-drilldown" hidden></div>
</section>
<!-- JOM_OPERATIONAL_CONSOLE_END -->"""


def inject_template(path: Path) -> dict:
    if not path.exists():
        return {"path": str(path), "exists": False, "changed": False}
    text = path.read_text(encoding="utf-8", errors="replace")
    original = text
    if CSS_LINK not in text:
        text = text.replace("</head>", f"  {CSS_LINK}\n</head>") if "</head>" in text else CSS_LINK + "\n" + text
    if JS_SCRIPT not in text:
        text = text.replace("</body>", f"  {JS_SCRIPT}\n</body>") if "</body>" in text else text + "\n" + JS_SCRIPT + "\n"
    if "JOM_OPERATIONAL_CONSOLE_START" not in text:
        if "<main" in text and "</main>" in text:
            idx = text.find("</main>")
            text = text[:idx] + PANEL + "\n" + text[idx:]
        elif "</body>" in text:
            text = text.replace("</body>", PANEL + "\n</body>")
        else:
            text += "\n" + PANEL + "\n"
    if text != original:
        backup = ROOT / "backups" / f"operational_console_dark_ui_template_binding_{datetime.now().strftime('%Y%m%d_%H%M%S')}" / path.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
        path.write_text(text, encoding="utf-8")
        return {"path": str(path), "exists": True, "changed": True, "backup": str(backup)}
    return {"path": str(path), "exists": True, "changed": False}


def main() -> int:
    targets = [ROOT / "templates" / "home.html", ROOT / "templates" / "reference.html"]
    results = [inject_template(path) for path in targets]
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps({"schema": "jom-operational-console-dark-ui-template-binding-v1", "results": results}, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "results": results}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
