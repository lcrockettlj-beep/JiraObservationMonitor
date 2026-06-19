import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

"""
Snapshot Controller — JOM Sprint 9 Step 2
==========================================
Throttled snapshot creation with daily anchor guarantees.

Rules:
  - Normal snapshots: minimum 10 minutes between snapshots
  - Anchor windows: ALWAYS create a snapshot, regardless of throttle
      * Morning anchor: 07:55 - 08:05
      * Evening anchor: 19:55 - 20:05
  - Anchors are tagged with _anchor_morning or _anchor_evening suffix
  - Daily anchor uniqueness: only ONE morning anchor and ONE evening
    anchor are created per day (re-runs in the window are no-ops)
  - Retention: rolling 20 snapshots maximum
"""

import json
import shutil
from datetime import datetime, time, timedelta
from pathlib import Path

# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = PROJECT_ROOT / "snapshots"
RUNTIME_FILE = PROJECT_ROOT / "latest_run_intelligence.json"

THROTTLE_MINUTES = 10
RETENTION_LIMIT = 20

MORNING_ANCHOR_START = time(7, 55)
MORNING_ANCHOR_END   = time(8, 5)
EVENING_ANCHOR_START = time(19, 55)
EVENING_ANCHOR_END   = time(20, 5)


# ============================================================
# Helpers
# ============================================================

def now() -> datetime:
    return datetime.now()


def list_existing_snapshots() -> list[Path]:
    if not SNAPSHOT_DIR.exists():
        return []
    return sorted(SNAPSHOT_DIR.glob("snapshot_*.json"))


def latest_regular_snapshot() -> Path | None:
    """Return the most recent NON-anchor snapshot."""
    snapshots = [
        p for p in list_existing_snapshots()
        if "_anchor_" not in p.name
    ]
    return snapshots[-1] if snapshots else None


def time_since_last_regular_snapshot() -> timedelta | None:
    last = latest_regular_snapshot()
    if last is None:
        return None
    last_dt = datetime.fromtimestamp(last.stat().st_mtime)
    return now() - last_dt


def in_window(current: time, start: time, end: time) -> bool:
    return start <= current <= end


def anchor_window_status() -> tuple[bool, str | None]:
    """
    Returns (in_anchor_window, anchor_label).
    Label is one of: 'morning', 'evening', or None.
    """
    current = now().time()
    if in_window(current, MORNING_ANCHOR_START, MORNING_ANCHOR_END):
        return True, "morning"
    if in_window(current, EVENING_ANCHOR_START, EVENING_ANCHOR_END):
        return True, "evening"
    return False, None


def today_anchor_exists(label: str) -> bool:
    """Check whether an anchor of this label has already been created today."""
    today_prefix = now().strftime("%Y-%m-%d")
    pattern = f"snapshot_{today_prefix}_*_anchor_{label}.json"
    matches = list(SNAPSHOT_DIR.glob(pattern))
    return len(matches) > 0


def write_snapshot(suffix: str = "") -> Path:
    """Copy the runtime file into the snapshot directory with an optional suffix."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now().strftime("%Y-%m-%d_%H-%M-%S")
    name = f"snapshot_{stamp}{suffix}.json"
    target = SNAPSHOT_DIR / name
    shutil.copy(RUNTIME_FILE, target)
    return target


def enforce_retention():
    """
    Apply rolling retention.
    Anchor snapshots are PROTECTED — never pruned by retention.
    Only regular snapshots are subject to the limit.
    """
    regular = [
        p for p in list_existing_snapshots()
        if "_anchor_" not in p.name
    ]
    if len(regular) <= RETENTION_LIMIT:
        return
    excess = len(regular) - RETENTION_LIMIT
    to_remove = regular[:excess]
    for path in to_remove:
        try:
            path.unlink()
            print(f"♻️  Pruned old snapshot: {path.name}")
        except Exception as exc:
            print(f"⚠️  Could not prune {path.name}: {exc}")


# ============================================================
# Main logic
# ============================================================

def main():
    print("📦 Snapshot Controller")

    if not RUNTIME_FILE.exists():
        print(f"⚠️  Runtime file not found: {RUNTIME_FILE.name}")
        print("   Skipping snapshot.")
        return

    in_anchor, anchor_label = anchor_window_status()

    # === Path 1: Anchor window ===
    if in_anchor:
        if today_anchor_exists(anchor_label):
            print(f"⚓ Anchor window active ({anchor_label}), but today's anchor already exists. Skipping.")
        else:
            target = write_snapshot(suffix=f"_anchor_{anchor_label}")
            print(f"⚓ Anchor snapshot created ({anchor_label}): {target.name}")
        enforce_retention()
        return

    # === Path 2: Normal throttled path ===
    elapsed = time_since_last_regular_snapshot()

    if elapsed is None:
        # No previous regular snapshot — always create one
        target = write_snapshot()
        print(f"✅ Snapshot created: {target.name}")
    elif elapsed < timedelta(minutes=THROTTLE_MINUTES):
        mins = int(elapsed.total_seconds() // 60)
        print(f"⏳ Skipped (too soon — last regular snapshot was {mins} min ago)")
        return
    else:
        target = write_snapshot()
        print(f"✅ Snapshot created: {target.name}")

    # Always show count + apply retention
    regular_count = sum(1 for p in list_existing_snapshots() if "_anchor_" not in p.name)
    anchor_count  = sum(1 for p in list_existing_snapshots() if "_anchor_" in p.name)
    print(f"📁 Stored: {regular_count}/{RETENTION_LIMIT} regular + {anchor_count} anchor(s)")

    enforce_retention()


if __name__ == "__main__":
    main()