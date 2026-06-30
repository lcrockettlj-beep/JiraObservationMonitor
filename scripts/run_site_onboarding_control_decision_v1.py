from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

CURRENT = Path(__file__).resolve()
PROJECT_ROOT = CURRENT.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.registry.site_onboarding_control import record_decision


def main() -> int:
    parser = argparse.ArgumentParser(description="Record JOM site onboarding control decision")
    parser.add_argument("--site-key", required=True)
    parser.add_argument("--state", choices=["pending", "approved", "ignored", "rejected"], required=True)
    parser.add_argument("--reason", default="")
    parser.add_argument("--actor", default="operator")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    result = record_decision(
        site_key=args.site_key,
        state=args.state,
        reason=args.reason,
        actor=args.actor,
        apply=args.apply,
    )

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
