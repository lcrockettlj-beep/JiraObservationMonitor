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


def main():
    print("🔁 SYNC RUNTIME WORKFLOW")
    print("-" * 40)

    if not is_app_running():
        print("⚠️ Skipped — Flask app is not running")
        print("➡️ Start it: python web.py")
        return

    subprocess.run(["python", "scripts/validate_contract.py"])
    subprocess.run(["python", "scripts/change_tracker.py"])
    subprocess.run(["python", "scripts/snapshot_controller.py"])
    snapshot_now()

    print("-" * 40)
    print("✅ Sync complete — runtime + docs + snapshots aligned")


if __name__ == "__main__":
    main()