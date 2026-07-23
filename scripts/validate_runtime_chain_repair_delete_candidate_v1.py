from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "static" / "data"


def run(cmd):
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {"cmd": " ".join(cmd), "returncode": proc.returncode, "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"_error": str(exc)}


def main() -> int:
    checks = []
    checks.append(run([sys.executable, "-m", "py_compile", "app/web.py", "app/runtime/runtime_sources_refresh.py", "scripts/build_site_registry.py", "scripts/audit_source_freshness.py", "scripts/backend_runtime_freshness_snapshot_elimination_v1.py"]))
    checks.append(run([sys.executable, "-m", "app.builders.estate_product_access", "--project-root", "."]))
    checks.append(run([sys.executable, "scripts/build_site_registry.py", "--project-root", "."]))
    checks.append(run([sys.executable, "scripts/backend_runtime_freshness_snapshot_elimination_v1.py"]))
    checks.append(run([sys.executable, "scripts/audit_source_freshness.py"]))
    registry = read_json(DATA / "site_registry.json")
    freshness = read_json(DATA / "source_freshness_audit.json")
    reliability = read_json(DATA / "source_reliability_status.json")
    live_truth = read_json(DATA / "runtime_live_truth_status.json")
    result = {
        "schema": "jom-runtime-chain-repair-delete-candidate-validation-v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "command_checks": checks,
        "summary": {
            "registry_sites": registry.get("summary", {}).get("total_sites"),
            "freshness_schema": freshness.get("schema"),
            "reliability_issues": reliability.get("summary", {}).get("issue_count"),
            "live_truth_available": live_truth.get("summary", {}).get("live_product_access_available"),
        },
    }
    out = ROOT / "reports" / "runtime_chain_repair_delete_candidate_validation_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    failed = [c for c in checks if c["returncode"] != 0]
    print(json.dumps(result["summary"], indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
