"""
Compatibility shim for legacy web.py import.

The original snapshot_controller.py has been moved to:
scripts/_legacy_review/snapshot_controller.py

This shim exists so existing imports continue to work while the runtime
entry point remains scripts/run_operational_snapshot.py.
"""

from scripts._legacy_review.snapshot_controller import *  # noqa: F401,F403
