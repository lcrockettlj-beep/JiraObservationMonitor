from __future__ import annotations

from _project_bootstrap import ensure_project_root_on_path
ensure_project_root_on_path()

import subprocess
import sys
from datetime import datetime, timezone


def run_step(name: str, script: str) -> None:
    print(f"\n=== {name} ===")
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
    )

    if result.stdout:
        print(result.stdout)

    if result.returncode != 0:
        if result.stderr:
            print(result.stderr)
        raise SystemExit(f"FAILED: {name}")


def main() -> int:
    print("\n====================================")
    print("JOM OPERATIONAL SNAPSHOT START")
    print(f"Time: {datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}")
    print("====================================\n")

    run_step("Build Site Registry", "scripts/build_site_registry.py")
    run_step("Build Named Access Truth", "scripts/build_named_access_truth_v2.py")
    run_step("Build User Footprint", "scripts/build_user_footprint_source.py")
    run_step("Source Reliability Audit", "scripts/source_reliability_audit.py")

    print("\n====================================")
    print("SNAPSHOT COMPLETE")
    print("====================================\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# JOM_SITE_ONBOARDING_CONTROL_V1
try:
    from app.registry.site_onboarding_control import load_decisions, normalise_legacy_decisions
    _jom_onboarding_decisions = normalise_legacy_decisions(load_decisions())
except Exception:
    _jom_onboarding_decisions = None
