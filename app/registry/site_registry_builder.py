from __future__ import annotations
import argparse, json, sys
from pathlib import Path

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--project-root", default=".")
    p.add_argument("--reset-approved-scope", action="store_true")
    args = p.parse_args()
    root = Path(args.project_root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from backend.site_registry_runtime import build_registry, reset_to_approved_scope
    if args.reset_approved_scope:
        reset_to_approved_scope(root)
    registry = build_registry(root)
    print("Site registry generated.")
    print(json.dumps(registry.get("summary", {}), indent=2))
    print(f"Output: {root / 'static' / 'data' / 'site_registry.json'}")

# JOM_SITE_ONBOARDING_CONTROL_V1
try:
    from app.registry.site_onboarding_control import get_site_state, is_site_approved
except Exception:
    def get_site_state(site_key):
        return "pending"
    def is_site_approved(site_key):
        return False
