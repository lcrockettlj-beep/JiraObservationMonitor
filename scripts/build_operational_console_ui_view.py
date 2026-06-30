from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

status_file = ROOT / "static/data/operational_console_status.json"
output_file = ROOT / "static/data/operational_console_ui_view.json"

if not status_file.exists():
    raise SystemExit("operational_console_status.json not found")

status = json.loads(status_file.read_text())

ui = {
    "timestamp": status.get("generated_at_utc"),
    "overall_status": status.get("overall_status"),
    "cards": {
        "scheduler": status.get("cards", {}).get("scheduler"),
        "reliability": status.get("cards", {}).get("source_reliability"),
        "runtime": status.get("cards", {}).get("runtime_refresh"),
        "sites": status.get("cards", {}).get("site_registry")
    },
    "badges": {
        "scheduler_ok": status.get("summary", {}).get("scheduler_ok"),
        "reliability_ok": status.get("summary", {}).get("source_reliability_ok"),
        "advisory_count": status.get("summary", {}).get("runtime_advisory_count")
    }
}

output_file.write_text(json.dumps(ui, indent=2))

print(json.dumps({
    "status": "ok",
    "output": str(output_file)
}, indent=2))
