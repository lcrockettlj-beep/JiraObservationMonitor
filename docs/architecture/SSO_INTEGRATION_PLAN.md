# SSO Integration Plan — Microsoft Entra ID

**Status:** Phase 2 activation guide  
**Phase 1 status:** Reference only — not used during Phase 1  
**Last reviewed:** June 2026

---

## Purpose of this document

This document is a step-by-step activation guide for integrating JOM with Microsoft Entra ID SSO when Phase 2 is sanctioned. It is intended for the engineer who will execute Phase 2 Sprint B (the SSO integration sprint).

This document assumes:

- Phase 2 has been approved by senior management
- The JOM server has been provisioned (Phase 2 Sprint A complete)
- You have collaboration access with GLI IT for Entra ID configuration

---

## Prerequisites — confirm before starting

| Requirement | How to verify |
|-------------|---------------|
| Phase 2 approval is documented | Senior management email or written approval |
| Server provisioned with HTTPS | https://jom.gaminglabs/ returns Flask welcome page |
| GLI Entra ID tenant ID known | IT can provide it (looks like xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx) |
| Permission to register an app in Entra ID | Either you have rights, or IT will register on your behalf |
| Allow-list policy drafted | Written list of who gets initial Tier 1-4 access |

If any of these are uncertain, stop here and resolve them first. SSO integration without these prerequisites tends to produce a half-broken state that is harder to fix than to delay.

---

## Step 1 — Register JOM as an Entra ID application

The Entra ID app registration tells the GLI tenant that JOM exists, what redirect URIs it will use, and what scopes it needs.

Either do this yourself in the Entra ID admin centre, or submit a request to GLI IT with the spec below.

### App registration spec

| Field | Value |
|-------|-------|
| App name | JOM — Jira Observation Monitor |
| Supported account types | Single tenant (this GLI tenant only) |
| Redirect URI (web) | https://jom.gaminglabs/auth/callback |
| Front-channel logout URL | https://jom.gaminglabs/auth/logout |
| ID tokens | Yes (we need OpenID Connect) |
| Access tokens | Yes |

### API permissions to request

| API | Permission | Type | Reason |
|-----|-----------|------|--------|
| Microsoft Graph | openid | Delegated | Standard OIDC scope |
| Microsoft Graph | profile | Delegated | Get display name |
| Microsoft Graph | email | Delegated | Get user email |
| Microsoft Graph | User.Read | Delegated | Optional, for richer profile |

Do NOT request application-level (non-delegated) permissions. Phase 2 acts on behalf of the user, not as the application.

### Credentials to obtain

After registration, capture these values:

- Tenant ID (the GLI Entra ID tenant)
- Application (client) ID (the JOM app identifier)
- Client secret (or upload a certificate — preferred for production)

Store these in the Phase 2 server secrets store, NOT in .env on disk.

---

## Step 2 — Configure JOM environment variables

On the Phase 2 server, set the following environment variables (or load from secrets store):

- JOM_ENTRA_TENANT_ID
- JOM_ENTRA_CLIENT_ID
- JOM_ENTRA_CLIENT_SECRET
- JOM_ENTRA_REDIRECT_URI (e.g. https://jom.gaminglabs/auth/callback)
- JOM_ENTRA_SCOPES (typically: openid profile email)

Do not flip the feature flag yet. Flipping the flag activates the import contract — code that is not implemented yet will throw NotImplementedError.

---

## Step 3 — Implement sso_handler.py properly

Replace the dormant skeleton with real implementations:

| Function | What to implement |
|----------|-------------------|
| get_entra_config() | Read env vars, build endpoint URLs from tenant ID, return dict |
| build_authorization_url(state) | Construct OAuth URL with all required params |
| handle_callback(code, state, expected_state) | Exchange code, validate token, return identity |
| validate_id_token(id_token) | Fetch JWKS, verify signature and claims |
| extract_user_identity(claims) | Pull email, name, oid from claims dict |
| create_session(identity) | Generate session ID, store in session store |
| revoke_session(session_id) | Sign-out handler |

Library recommendation: use the msal Python library (pip install msal). It handles JWKS caching, token validation, and the OAuth2 dance correctly. Do not implement OAuth from scratch.

---

## Step 4 — Wire SSO into Flask before_request

The integration point is a Flask middleware that runs before every request. The pattern (pseudocode):

- If multi_user.enabled flag is False, return (Phase 1 mode, no auth)
- If request path starts with /auth/, allow through without check
- If session contains user_email, allow through (already authenticated)
- Otherwise: generate state token, save to session, redirect to Entra ID authorization URL

The /auth/callback route:

- Exchange the code for tokens via sso_handler.handle_callback
- Check the returned email against user_allowlist.check_user
- If not in allow-list: log auth.signin_denied event, return 403 access denied page
- If in allow-list: log auth.signin_success event, store user_email in session, redirect to /

---

## Step 5 — Implement user_allowlist.py properly

Replace the dormant skeleton with real implementations. The flat JSON file approach is simpler for Sprint B; you can migrate to Entra ID security groups later if IT prefers.

Key behaviours:

- Load users.json on startup, cache in memory
- check_user(email) is hot path — must be O(1)
- Admin operations write atomically (write to .tmp, rename)
- Every admin operation logs to access_audit

---

## Step 6 — Implement access_audit.py properly

Replace the dormant skeleton with real implementations. Key behaviours:

- Write to access_audit_YYYY-MM-DD.jsonl (JSON Lines, one event per line)
- Daily rotation via scheduled task
- Retention policy: 365 days for access events, 7 years for admin events
- Failures here must NOT crash the user request — log to stderr instead

---

## Step 7 — Populate users.json

Copy users.example.json to users.json and populate with the agreed initial user list. Set file permissions so only the Flask process user can read it.

---

## Step 8 — Activate the feature flags

Once steps 3-7 are complete and tested, flip the flags by setting environment variables:

- JOM_FLAG_MULTI_USER_ENABLED=true
- JOM_FLAG_MULTI_USER_SSO_ENABLED=true
- JOM_FLAG_MULTI_USER_ALLOWLIST_ENFORCED=true
- JOM_FLAG_MULTI_USER_ACCESS_AUDIT_ENABLED=true

Persist these in the server environment config (systemd service file, Docker env, or equivalent). Restart Flask.

---

## Step 9 — Verify activation

Walk through this checklist with another engineer or IT representative present:

| Check | Expected result |
|-------|-----------------|
| Open https://jom.gaminglabs/ in browser | Redirects to Entra ID login |
| Sign in with an allow-listed email | Returns to JOM homepage |
| Try signing in with a non-allow-listed email | Shows access denied page |
| Inspect today access_audit log | Contains entries for both attempts |
| Inspect users.json permissions | Restricted as expected |
| Try accessing /api/data without session | Redirected to SSO |
| Try direct localhost access to Flask | Refused (server should bind to network interface) |
| Verify Atlassian admin token still in secrets store | Not in .env file |

If all checks pass, Phase 2 SSO is live.

---

## Common pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Wrong redirect URI in Entra ID | AADSTS50011 reply URL mismatch | Update redirect URI in app registration to match exactly |
| Token validation failing | Signature verification failed | Check tenant ID is correct in config; JWKS keys rotate |
| Session not persisting | User re-prompted for SSO every request | Check Flask session cookie config (Secure, HttpOnly, domain) |
| Allow-list not being checked | Any user can sign in | Check multi_user.allowlist_enforced flag is on |
| Audit log not writing | Sign-ins succeed but no log entries | Check file permissions on log directory |
| First SSO call slow | First call takes 5+ seconds | JWKS fetch on first call — cache, subsequent calls fast |

---

## Rollback plan

If Phase 2 has problems in production, the rollback is fast:

- Set JOM_FLAG_MULTI_USER_ENABLED=false
- Restart Flask

All dormant guards re-activate. The platform returns to Phase 1 single-user mode. The Atlassian admin token still works. Snapshot history is preserved. No data is lost.

Document the rollback in docs/control/mechanics_change_log.md and investigate the issue without time pressure.

---

## After successful Phase 2 go-live

Update:

- docs/governance/JOM_Master_Governance_Delivery_Handover_Pack_v4.docx to reflect Phase 2 active
- docs/security/JOM_Security_Posture_v3.docx to remove pending Phase 2 language
- docs/sprints/JOM_Sprint_Deliverables_v3.docx to log actual Phase 2 effort
- docs/control/mechanics_change_log.md with the activation event

Schedule a stakeholder walkthrough for the initial 13-user cohort.

---

## What this document is NOT

- Not a script you can run end-to-end
- Not a commitment to deliver Phase 2
- Not a substitute for actually thinking during the Sprint B work

It is a checklist. Use it as a guide, but expect to make adjustments based on what you find when you start the work.
