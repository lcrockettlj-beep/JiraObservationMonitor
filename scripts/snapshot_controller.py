import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import datetime
import shutil
from pathlib import Path

SNAPSHOT_DIR = Path("snapshots")
MAX_SNAPSHOTS = 20
MIN_INTERVAL_MINUTES = 10
ANCHOR_TIMES = ["08:00", "20:00"]

SOURCE_FILE = Path("latest_run_intelligence.json")
LATEST_FILE = SNAPSHOT_DIR / "latest_snapshot.json"


def now():
    return datetime.datetime.now()


def list_snapshots():
    return sorted(SNAPSHOT_DIR.glob("snapshot_*.json"))


def latest_snapshot_time():
    snaps = list_snapshots()
    if not snaps:
        return None
    return datetime.datetime.fromtimestamp(snaps[-1].stat().st_mtime)


def should_skip_due_to_interval():
    last = latest_snapshot_time()
    if not last:
        return False
    diff = (now() - last).total_seconds() / 60
    return diff < MIN_INTERVAL_MINUTES


def is_anchor_window():
    current = now().strftime("%H:%M")
    return current in ANCHOR_TIMES


def prune_old():
    snaps = list_snapshots()
    if len(snaps) <= MAX_SNAPSHOTS:
        return
    excess = len(snaps) - MAX_SNAPSHOTS
    for snap in snaps[:excess]:
        snap.unlink()


def create_snapshot():
    if not SOURCE_FILE.exists():
        print(f"❌ Source missing: {SOURCE_FILE}")
        return None
    SNAPSHOT_DIR.mkdir(exist_ok=True)
    ts = now().strftime("%Y-%m-%d_%H-%M-%S")
    target = SNAPSHOT_DIR / f"snapshot_{ts}.json"
    shutil.copy(SOURCE_FILE, target)
    shutil.copy(SOURCE_FILE, LATEST_FILE)
    print(f"✅ Snapshot created: {target.name}")
    return target


def main():
    print("📦 Snapshot Controller")
    if should_skip_due_to_interval() and not is_anchor_window():
        print("⏳ Skipped (too soon)")
        return
    create_snapshot()
    prune_old()
    print(f"📁 Stored: {len(list_snapshots())}/{MAX_SNAPSHOTS}")


if __name__ == "__main__":
    main()