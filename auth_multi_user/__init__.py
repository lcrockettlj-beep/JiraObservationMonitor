"""
auth_multi_user â€” JOM Phase 2 Multi-User Scaffolding
======================================================

DORMANT PACKAGE â€” Phase 2 scaffolding.

This package contains skeleton modules for the future Phase 2
multi-user expansion of JOM:

    sso_handler.py      â€” Microsoft Entra ID OAuth handler
    user_allowlist.py   â€” User access allow-list management
    access_audit.py     â€” Access event logging

All modules in this package are DORMANT in Phase 1. They are
guarded by the master feature flag:

    config.feature_flags.is_enabled('multi_user.enabled')

When the master flag is False (Phase 1 default), the modules
in this package refuse to execute their core functions. Importing
them is safe; calling their functions raises a clear RuntimeError.

PURPOSE
-------
The scaffolding exists to:

1. Document the Phase 2 architecture in code form, not just prose.
2. Reduce the engineering cost of Phase 2 activation when sanctioned.
3. Provide a stable contract that Phase 2 development can target.
4. Demonstrate architectural intent to security reviewers and auditors.

SAFETY
------
- Importing this package performs zero I/O.
- The modules contain no auto-execution paths.
- Each function checks the master feature flag before running.
- No secrets are read or stored by this package in Phase 1.
- No network ports are opened by this package in Phase 1.

ACTIVATION
----------
See docs/architecture/SSO_INTEGRATION_PLAN.md for the activation
procedure. Activation requires:

  - Senior management approval for Phase 2
  - All Phase 2 preconditions met (Master Governance Pack v3 Â§12.8)
  - Security review of this package's final implementation
  - Microsoft Entra ID tenant configuration
"""

__all__ = []
__phase__ = "phase2-scaffolding"
__status__ = "dormant"
