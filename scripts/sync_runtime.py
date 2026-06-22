import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import subprocess
import requests
import json
from pathlib import Path

SNAPSHOT_FILE = Path("docs/control/runtime_contract_snapshot.json")
RUNTIME_URL = "http://127.0.0.1:5000/api/data"


def is_app_running():
    try:
        r = requests.get(RUNTIME_URL, timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def snapshot_now():
    response = requests.get(RUNTIME_URL, timeout=10)
    response.raise_for_status()
    SNAPSHOT_FILE.write_text(
        json.dumps(response.json(), indent=4),
        encoding="utf-8"
    )
    print("✅ Snapshot updated")


def run_step(label: str, command: list[str]) -> int:
    print(f"➡️ {label}")
    result = subprocess.run(command)
    if result.returncode != 0:
        print(f"⚠️ Step failed: {label} (exit {result.returncode})")
    return result.returncode


def backup_runtime_chain() -> int:
    print("➡️ Backup runtime chain")
    result = subprocess.run(["python", "scripts/backup_runtime_chain.py"])
    if result.returncode != 0:
        print(f"⚠️ Runtime backup step reported exit {result.returncode}")
    return result.returncode


def main():
    print("🔁 SYNC RUNTIME WORKFLOW")
    print("-" * 40)

    if not is_app_running():
        print("⚠️ Skipped — Flask app is not running")
        print("➡️ Start it: python web.py")
        return 1

    failures = []

    if run_step("Validate contract", ["python", "scripts/validate_contract.py"]) != 0:
        failures.append("validate_contract")

    if run_step("Change tracker", ["python", "scripts/change_tracker.py"]) != 0:
        failures.append("change_tracker")

    if run_step("Snapshot controller", ["python", "scripts/snapshot_controller.py"]) != 0:
        failures.append("snapshot_controller")

    try:
        print("➡️ Snapshot runtime contract")
        snapshot_now()
    except Exception as exc:
        print(f"⚠️ Snapshot update failed: {exc}")
        failures.append("snapshot_now")

    if not failures:
        backup_runtime_chain()
    else:
        print("⚠️ Runtime backup skipped because one or more sync steps failed")

    print("-" * 40)
    if failures:
        print(f"⚠️ Sync completed with failures: {', '.join(failures)}")
        return 1

    print("✅ Sync complete — runtime + docs + snapshots + backup aligned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
