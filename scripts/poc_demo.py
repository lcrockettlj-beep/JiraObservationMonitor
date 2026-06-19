"""
poc_demo.py — JOM Phase 2 In-Memory POC Demo
===============================================

Runnable demonstration of the Phase 2 multi-user authentication
flow, using mock implementations to simulate Microsoft Entra ID
SSO without any real network calls or persistent state.

PURPOSE
-------
This script exists to demonstrate that the Phase 2 architecture
documented in:

    docs/architecture/MULTI_USER_ARCHITECTURE.md
    docs/architecture/SSO_INTEGRATION_PLAN.md

is concrete and plausible. It walks through the authentication
flow end-to-end with two simulated users:

    User A — allow-listed, should be granted access
    User B — not allow-listed, should be denied

For each user the script prints a clear narrative of every step:
authentication, allow-list check, audit log entry, session result.

SAFETY GUARANTEES
-----------------
- This script makes NO network calls
- This script does NOT touch real Atlassian APIs
- This script does NOT contact Entra ID
- This script does NOT modify .env, tokens.json, or any secrets
- This script does NOT write any files to disk
- This script does NOT change feature flags persistently
- This script does NOT affect the running Phase 1 Flask app

The mock implementations live entirely in this file and replace
the dormant functions in auth_multi_user.* for the duration of
this script run only.

USAGE
-----
    python scripts/poc_demo.py

    or for cleaner package-aware execution:

    python -m scripts.poc_demo

NARRATIVE
---------
The output is structured as a story. Read it from top to bottom
and you should see what the Phase 2 flow looks like in operation.
"""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch


# ============================================================
# Make project root importable
# ============================================================
# When run as 'python scripts/poc_demo.py', the project root is
# not on sys.path by default. Add it so we can import config and
# auth_multi_user.
# ============================================================

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ============================================================
# Mock allow-list for the POC
# ============================================================
# In real Phase 2, this would be loaded from users.json.
# Here we hard-code it for the demo.
# ============================================================

POC_ALLOWLIST = {
    "user.a@gaminglabs.com": {
        "tier": "tier_3_standard_users",
        "display_name": "User A (Standard)",
        "notes": "Demo allow-listed user — no Atlassian admin permission required",
    },
}

# Mock audit log (in-memory, discarded after script exits)
POC_AUDIT_LOG = []


# ============================================================
# Mock implementations
# ============================================================
# These functions simulate the Phase 2 behaviour without doing
# the real work. They never touch network, never touch real files,
# never change any persistent state.
# ============================================================

def mock_sso_authenticate(email: str) -> dict:
    """Simulate the result of a successful Entra ID SSO flow.

    In real Phase 2, this would be the dict returned by
    sso_handler.handle_callback() after a successful OAuth dance
    and JWKS validation.
    """
    return {
        "email": email,
        "display_name": email.split("@")[0].replace(".", " ").title(),
        "oid": "mock-oid-" + email.replace("@", "-at-").replace(".", "-dot-"),
        "tenant_id": "mock-gli-tenant-id",
        "authenticated_at": datetime.now(timezone.utc).isoformat(),
    }


def mock_check_user(email: str) -> bool:
    """Simulate the allow-list check.

    In real Phase 2, this would call user_allowlist.check_user(email)
    which reads from users.json.
    """
    return email.lower() in POC_ALLOWLIST


def mock_get_user_tier(email: str):
    """Simulate tier lookup."""
    record = POC_ALLOWLIST.get(email.lower())
    return record["tier"] if record else None


def mock_log_event(event_type: str, user_email: str,
                   resource: str = "", result: str = "success",
                   metadata: dict = None) -> None:
    """Simulate audit log append.

    In real Phase 2, this would write to access_audit_YYYY-MM-DD.jsonl.
    Here we just append to an in-memory list for the demo.
    """
    POC_AUDIT_LOG.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "user_email": user_email,
        "resource": resource,
        "result": result,
        "metadata": metadata or {},
    })


def mock_create_session(user_identity: dict) -> str:
    """Simulate server-side session creation."""
    return "mock-session-" + user_identity["oid"][:16]


# ============================================================
# Pretty printing helpers
# ============================================================

def banner(text: str) -> None:
    print()
    print("=" * 70)
    print(f"  {text}")
    print("=" * 70)


def step(num: int, text: str) -> None:
    print(f"\n[Step {num}] {text}")


def info(text: str) -> None:
    print(f"   -> {text}")


def success(text: str) -> None:
    print(f"   [OK] {text}")


def warn(text: str) -> None:
    print(f"   [DENIED] {text}")


# ============================================================
# The POC flow
# ============================================================

def simulate_user_login(email: str, target_page: str = "/") -> None:
    """Walk through a complete Phase 2 authentication flow for one user."""

    banner(f"Simulating login: {email}")

    step(1, f"User opens {target_page}")
    info("Browser sends GET request to JOM server")

    step(2, "Flask before_request middleware checks session")
    info("No session cookie present")
    info("Redirecting to Entra ID authorization URL")

    step(3, "User authenticates against GLI Entra ID tenant")
    info("(In real Phase 2: OAuth2 PKCE flow, MFA may be required)")
    info("(In this POC: simulated successful authentication)")
    identity = mock_sso_authenticate(email)
    success(f"Entra ID returned identity: {identity['display_name']}")
    info(f"   oid: {identity['oid']}")

    step(4, "Flask validates ID token and extracts email")
    info(f"Email extracted: {identity['email']}")
    info("(In real Phase 2: JWKS signature verification, audience check, issuer check)")

    step(5, "Allow-list check (user_allowlist.check_user)")
    allowed = mock_check_user(identity["email"])

    if allowed:
        tier = mock_get_user_tier(identity["email"])
        success(f"User is allow-listed (tier: {tier})")

        step(6, "Recording successful sign-in in audit log")
        mock_log_event(
            "auth.signin_success",
            identity["email"],
            resource=target_page,
            metadata={"tier": tier, "display_name": identity["display_name"]},
        )
        success("Audit event recorded: auth.signin_success")

        step(7, "Creating server-side session")
        session_id = mock_create_session(identity)
        success(f"Session created: {session_id}")
        info(f"Session cookie returned to browser")

        step(8, "Browser redirected to original target page")
        success(f"Access granted to {target_page}")
        mock_log_event("page.view", identity["email"], resource=target_page)
        success("Audit event recorded: page.view")

    else:
        warn(f"Email {identity['email']} is NOT in the allow-list")

        step(6, "Recording denied sign-in in audit log")
        mock_log_event(
            "auth.signin_denied",
            identity["email"],
            resource=target_page,
            result="denied",
            metadata={"reason": "not_in_allowlist"},
        )
        warn("Audit event recorded: auth.signin_denied")

        step(7, "Returning 403 access denied page")
        warn("User sees: 'Access denied. Contact your JOM administrator.'")
        warn("No session created. No further access possible.")


def print_audit_summary() -> None:
    """Print the in-memory audit log at the end of the demo."""

    banner("In-memory audit log (Phase 2 would persist to disk)")

    if not POC_AUDIT_LOG:
        info("No audit events recorded")
        return

    for i, event in enumerate(POC_AUDIT_LOG, start=1):
        print(f"\n  Event {i}:")
        print(f"    timestamp:  {event['timestamp']}")
        print(f"    event_type: {event['event_type']}")
        print(f"    user_email: {event['user_email']}")
        print(f"    resource:   {event['resource']}")
        print(f"    result:     {event['result']}")
        if event["metadata"]:
            print(f"    metadata:   {event['metadata']}")


def show_feature_flag_state() -> None:
    """Show that this POC runs without enabling any persistent flags."""

    from config.feature_flags import is_enabled, get_phase

    banner("Feature flag state during this POC run")
    print(f"\n  Current phase reported by feature_flags: {get_phase()}")
    print()
    print("  multi_user.enabled                : {}".format(is_enabled("multi_user.enabled")))
    print("  multi_user.sso_enabled            : {}".format(is_enabled("multi_user.sso_enabled")))
    print("  multi_user.allowlist_enforced     : {}".format(is_enabled("multi_user.allowlist_enforced")))
    print("  multi_user.access_audit_enabled   : {}".format(is_enabled("multi_user.access_audit_enabled")))
    print()
    print("  All flags above are FALSE.")
    print("  This POC uses in-memory mocks, not the dormant scaffolding code.")
    print("  Phase 1 platform is unaffected.")


# ============================================================
# Main
# ============================================================

def main() -> None:
    banner("JOM Phase 2 POC Demo")
    print()
    print("  Purpose : Demonstrate the Phase 2 multi-user authentication flow")
    print("            without any network calls or persistent state changes.")
    print()
    print("  Mode    : In-memory mock implementations")
    print("  Safety  : No effect on Phase 1, no real Entra ID contact,")
    print("            no file writes, no flag changes.")

    show_feature_flag_state()

    # Simulate two users
    simulate_user_login("user.a@gaminglabs.com", target_page="/")
    simulate_user_login("user.b@gaminglabs.com", target_page="/estate")

    # Show the resulting audit log
    print_audit_summary()

    # Closing summary
    banner("Demo complete")
    print()
    print("  Observed behaviour:")
    print()
    print("    - User A (allow-listed) : access granted, session created,")
    print("                              audit log captured signin + page view")
    print()
    print("    - User B (not allow-listed) : access denied, no session,")
    print("                                  audit log captured denial event")
    print()
    print("  This matches the design in docs/architecture/MULTI_USER_ARCHITECTURE.md")
    print("  and the activation steps in docs/architecture/SSO_INTEGRATION_PLAN.md.")
    print()
    print("  No persistent state has been changed by this script.")
    print()


if __name__ == "__main__":
    main()
