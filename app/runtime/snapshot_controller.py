from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def retired_status() -> Dict[str, object]:
    return {
        "status": "retired",
        "available": False,
        "retired_at_utc": now_utc(),
        "message": "Legacy file recovery component retired. Current JOM authority uses OAuth/current-runtime outputs.",
    }


def main() -> Dict[str, object]:
    return retired_status()


if __name__ == "__main__":
    print(retired_status())
