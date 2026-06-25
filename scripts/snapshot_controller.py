import sys
import io
from datetime import datetime, time, timedelta
from pathlib import Path
import json
import shutil

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

"""
Snapshot Controller — JOM Sprint 9 Step 3 (replacement)

Throttled snapshot creation with daily anchor guarantees.
Rules:
- Normal snapshots: minimum 10 minutes between snapshots
- Anchor windows: create immediately during the window
    * Morning anchor: 07:55 - 08:05
    * Evening anchor: 19:55 - 20:05
- Catch-up guarantee: if a window was missed but the day has passed the
  anchor cut-off and that anchor does not yet exist, create it on the next run
- Anchors are tagged with _anchor_morning or _anchor_evening suffix
- Daily anchor uniqueness: only ONE morning anchor and ONE evening
  anchor are created per day (re-runs are no-ops)
- Retention: rolling 20 snapshots maximum for regular snapshots only

Important runtime-file behaviour in this replacement:
- Prefer latest_run_intelligence.json when present
- Fallback to latest_run.json
- Fallback to backups/latest_runtime/current/latest_run.json
- Fallback to latest_run_safe_partial.json
This keeps anchor creation aligned with the current morning startup pipeline.
"""

# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = PROJECT_ROOT / "snapshots"
LATEST_SNAPSHOT_FILE = SNAPSHOT_DIR / "latest_snapshot.json"
SNAPSHOT_INDEX_FILE = SNAPSHOT_DIR / "snapshot_index.json"

RUNTIME_CANDIDATES = [
    PROJECT_ROOT / "latest_run_intelligence.json",
    PROJECT_ROOT / "latest_run.json",
    PROJECT_ROOT / "backups" / "latest_runtime" / "current" / "latest_run.json",
    PROJECT_ROOT / "latest_run_safe_partial.json",
]

THROTTLE_MINUTES = 10
RETENTION_LIMIT = 20
MORNING_ANCHOR_START = time(7, 55)
MORNING_ANCHOR_END = time(8, 5)
EVENING_ANCHOR_START = time(19, 55)
EVENING_ANCHOR_END = time(20, 5)

# ============================================================
# Helpers
# ============================================================


def now() -> datetime:
    return datetime.now()


def resolve_runtime_file() -> Path | None:
    for candidate in RUNTIME_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def list_existing_snapshots() -> list[Path]:
    if not SNAPSHOT_DIR.exists():
        return []
    return sorted(SNAPSHOT_DIR.glob("snapshot_*.json"))


def latest_regular_snapshot() -> Path | None:
    regular = [p for p in list_existing_snapshots() if "_anchor_" not in p.name]
    return regular[-1] if regular else None


def time_since_last_regular_snapshot() -> timedelta | None:
    last = latest_regular_snapshot()
    if last is None:
        return None
    last_dt = datetime.fromtimestamp(last.stat().st_mtime)
    return now() - last_dt


def in_window(current: time, start: time, end: time) -> bool:
    return start <= current <= end


def anchor_window_status() -> tuple[bool, str | None]:
    current = now().time()
    if in_window(current, MORNING_ANCHOR_START, MORNING_ANCHOR_END):
        return True, "morning"
    if in_window(current, EVENING_ANCHOR_START, EVENING_ANCHOR_END):
        return True, "evening"
    return False, None


def today_anchor_exists(label: str) -> bool:
    today_prefix = now().strftime("%Y-%m-%d")
    pattern = f"snapshot_{today_prefix}_*_anchor_{label}.json"
    return any(SNAPSHOT_DIR.glob(pattern))


def due_anchor_labels() -> list[str]:
    """
    Determine which anchors are due right now.
    - During an anchor window: create that anchor immediately if missing.
    - After an anchor window: backfill the anchor later in the same day if missing.
    """
    current = now().time()
    due: list[str] = []

    morning_due = (
        (in_window(current, MORNING_ANCHOR_START, MORNING_ANCHOR_END) or current > MORNING_ANCHOR_END)
        and not today_anchor_exists("morning")
    )
    if morning_due:
        due.append("morning")

    evening_due = (
        (in_window(current, EVENING_ANCHOR_START, EVENING_ANCHOR_END) or current > EVENING_ANCHOR_END)
        and not today_anchor_exists("evening")
    )
    if evening_due:
        due.append("evening")

    return due


def write_snapshot(suffix: str = "") -> Path:
    runtime_file = resolve_runtime_file()
    if runtime_file is None:
        raise FileNotFoundError("No runtime file available for snapshot creation")

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now().strftime("%Y-%m-%d_%H-%M-%S")
    name = f"snapshot_{stamp}{suffix}.json"
    target = SNAPSHOT_DIR / name
    shutil.copy(runtime_file, target)
    shutil.copy(runtime_file, LATEST_SNAPSHOT_FILE)
    write_snapshot_index(latest_created=target)
    return target


def write_snapshot_index(latest_created: Path | None = None) -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    snapshots = list_existing_snapshots()
    payload = {
        "generated_at_local": now().strftime("%Y-%m-%d %H:%M:%S"),
        "latest_created": str(latest_created) if latest_created else (str(snapshots[-1]) if snapshots else ""),
        "latest_snapshot_file": str(LATEST_SNAPSHOT_FILE),
        "snapshot_count": len(snapshots),
        "regular_snapshot_count": sum(1 for p in snapshots if "_anchor_" not in p.name),
        "anchor_snapshot_count": sum(1 for p in snapshots if "_anchor_" in p.name),
        "files": [p.name for p in snapshots],
    }
    SNAPSHOT_INDEX_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def enforce_retention() -> None:
    """
    Apply rolling retention.
    Anchor snapshots are PROTECTED — never pruned by retention.
    Only regular snapshots are subject to the limit.
    """
    regular = [p for p in list_existing_snapshots() if "_anchor_" not in p.name]
    if len(regular) <= RETENTION_LIMIT:
        return

    excess = len(regular) - RETENTION_LIMIT
    for path in regular[:excess]:
        try:
            path.unlink()
            print(f"♻️  Pruned old snapshot: {path.name}")
        except Exception as exc:
            print(f"⚠️  Could not prune {path.name}: {exc}")


def startup_self_heal() -> bool:
    """
    Anchor-only startup self-heal.
    Returns True if one or more missing due anchors were created.
    """
    due_anchors = due_anchor_labels()
    if not due_anchors:
        print("🛠 Startup self-heal: no due anchors missing")
        return False

    created = False
    for anchor_label in due_anchors:
        target = write_snapshot(suffix=f"_anchor_{anchor_label}")
        print(f"⚓ Startup self-heal created ({anchor_label}): {target.name}")
        created = True

    regular_count = sum(1 for p in list_existing_snapshots() if "_anchor_" not in p.name)
    anchor_count = sum(1 for p in list_existing_snapshots() if "_anchor_" in p.name)
    print(f"📊 Stored: {regular_count}/{RETENTION_LIMIT} regular + {anchor_count} anchor(s)")
    return created


# ============================================================
# Main logic
# ============================================================


def main() -> None:
    print("📦 Snapshot Controller")

    runtime_file = resolve_runtime_file()
    if runtime_file is None:
        print("⚠️  Runtime file not found in any supported location:")
        for candidate in RUNTIME_CANDIDATES:
            print(f"   - {candidate}")
        print("   Skipping snapshot.")
        return

    print(f"🧭 Runtime source selected: {runtime_file.name}")

    # 1) Create any due anchors first (startup self-heal or in-window creation)
    created_anchor = startup_self_heal()

    # 2) If no anchor was due, apply throttled regular snapshot logic
    if not created_anchor:
        elapsed = time_since_last_regular_snapshot()
        if elapsed is None or elapsed >= timedelta(minutes=THROTTLE_MINUTES):
            target = write_snapshot()
            print(f"📸 Regular snapshot created: {target.name}")
        else:
            mins = int(elapsed.total_seconds() // 60)
            secs = int(elapsed.total_seconds() % 60)
            print(
                f"⏱ Regular snapshot throttled: last regular snapshot was {mins}m {secs}s ago "
                f"(minimum {THROTTLE_MINUTES}m)"
            )

    enforce_retention()
    write_snapshot_index()

    regular_count = sum(1 for p in list_existing_snapshots() if "_anchor_" not in p.name)
    anchor_count = sum(1 for p in list_existing_snapshots() if "_anchor_" in p.name)
    print(f"📊 Stored: {regular_count}/{RETENTION_LIMIT} regular + {anchor_count} anchor(s)")


if __name__ == "__main__":
    main()
