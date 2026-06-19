"""
feature_flags.py — JOM Feature Flag System
============================================

Centralised feature flag system for controlling Phase 1 vs Phase 2 behaviour.

Phase 1 (single-user, current default):
    All multi-user flags are OFF. The platform behaves exactly as Phase 1.

Phase 2 (multi-user, sanctioned by senior management):
    Flags are flipped to ON by editing this file, by setting environment
    variables, or by deploying a phase2.flags.json override.

DESIGN PRINCIPLES
-----------------
1. SAFE DEFAULTS — every flag defaults to False (Phase 1 behaviour).
2. NO RUNTIME ACTIVATION — flags require deliberate file edit or env var.
3. NO NETWORK READS — flags never come from a remote source.
4. NO SIDE EFFECTS — importing this module performs zero I/O.
5. EXPLICIT — every flag has a docstring explaining what it controls.

USAGE
-----
    from config.feature_flags import is_enabled

    if is_enabled('multi_user.sso_enabled'):
        # Phase 2 code path
        ...
    else:
        # Phase 1 code path (default)
        ...

PHASE 2 ACTIVATION CHECKLIST
----------------------------
Before flipping any multi_user flag to True, the operator MUST have:
  [ ] Senior management approval for Phase 2
  [ ] Server infrastructure provisioned and approved
  [ ] Microsoft Entra ID tenant integration confirmed
  [ ] User access policy documented
  [ ] Security review completed
  [ ] All preconditions in Master Governance Pack v3 Section 12.8 met

If ANY of the above is not in place, leave the flags at False.
"""

import os
from typing import Dict, Any


# ============================================================
# FLAG DEFINITIONS
# ============================================================
# All flags default to False. Each flag controls one specific
# behaviour. Flags should be small, granular, and independent.
# ============================================================

DEFAULT_FLAGS: Dict[str, Any] = {

    # ---- Multi-user (Phase 2) ----

    "multi_user.enabled": False,
    # Master switch for Phase 2 multi-user mode.
    # When False (default), no multi-user code path is reachable.
    # When True, individual sub-flags below are evaluated.

    "multi_user.sso_enabled": False,
    # Enable Microsoft Entra ID SSO authentication.
    # When True, requires sso_handler.py to be fully implemented
    # and a valid Entra ID tenant configuration.

    "multi_user.allowlist_enforced": False,
    # Enforce the user allow-list on every authenticated request.
    # When True, requires user_allowlist.py to be fully implemented
    # and a populated users.json file.

    "multi_user.access_audit_enabled": False,
    # Log every user authentication and page view event.
    # When True, requires access_audit.py to be fully implemented
    # and an audit log destination configured.

    # ---- Network posture (Phase 2) ----

    "network.bind_external": False,
    # When False (default), Flask binds to 127.0.0.1 (Phase 1).
    # When True, Flask binds to a network interface (Phase 2 server).
    # Note: this flag does NOT itself change Flask binding — it is
    # a marker for the future deployment script.

    # ---- Phase 1 toggles (for development/testing) ----

    "phase1.debug_widget_verbose": False,
    # Show extra diagnostic info in the Live Runtime widget.
    # Useful for development. Should be False in normal operation.
}


# ============================================================
# ENVIRONMENT VARIABLE OVERRIDES
# ============================================================
# Flags can be overridden by environment variables using the
# JOM_FLAG_ prefix. Example:
#
#     JOM_FLAG_MULTI_USER_ENABLED=true
#
# becomes the flag 'multi_user.enabled'.
#
# Truthy values: 'true', '1', 'yes', 'on' (case-insensitive)
# Anything else is treated as False.
# ============================================================

TRUTHY_VALUES = {"true", "1", "yes", "on"}


def _flag_to_env_var(flag_name: str) -> str:
    """Convert a flag name to its environment variable form.

    Example:
        'multi_user.sso_enabled' -> 'JOM_FLAG_MULTI_USER_SSO_ENABLED'
    """
    return "JOM_FLAG_" + flag_name.upper().replace(".", "_")


def _env_truthy(value: str) -> bool:
    """Return True if the env value should be interpreted as True."""
    if not value:
        return False
    return value.strip().lower() in TRUTHY_VALUES


# ============================================================
# PUBLIC API
# ============================================================

def is_enabled(flag_name: str) -> bool:
    """Return True if the named flag is enabled.

    Resolution order:
        1. Environment variable override (JOM_FLAG_<NAME>)
        2. DEFAULT_FLAGS value
        3. False (if flag does not exist)

    This function performs zero I/O beyond reading environment
    variables. It is safe to call from anywhere.
    """
    env_var = _flag_to_env_var(flag_name)
    env_value = os.environ.get(env_var)

    if env_value is not None:
        return _env_truthy(env_value)

    return bool(DEFAULT_FLAGS.get(flag_name, False))


def get_all_flags() -> Dict[str, bool]:
    """Return all flag names and their resolved values.

    Useful for debug pages or diagnostic output.
    """
    return {name: is_enabled(name) for name in DEFAULT_FLAGS}


def get_phase() -> str:
    """Return 'phase1' or 'phase2' based on the master multi_user flag.

    Convenience helper for code paths that branch at the phase level
    rather than at the individual flag level.
    """
    if is_enabled("multi_user.enabled"):
        return "phase2"
    return "phase1"


# ============================================================
# DIAGNOSTIC ENTRY POINT
# ============================================================
# Run this file directly to print the current flag state.
# Useful for verifying Phase 1 / Phase 2 mode without starting
# the full platform.
#
#     python config/feature_flags.py
# ============================================================

if __name__ == "__main__":
    print("JOM Feature Flag State")
    print("=" * 60)
    print(f"Current phase: {get_phase()}")
    print()
    print("Flags:")
    for name, value in get_all_flags().items():
        marker = "ON " if value else "off"
        print(f"  [{marker}] {name}")
    print()
    print("Phase 1 baseline confirmed if ALL flags above show [off].")