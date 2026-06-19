# Multi-User Architecture — JOM Phase 2

**Status:** Design document for Phase 2  
**Phase 1 status:** Reference only — no Phase 1 code uses anything described here  
**Last reviewed:** June 2026

---

## Purpose of this document

This document describes the technical architecture for the Phase 2 multi-user expansion of the Jira Observation Monitor. Phase 2 is currently pending senior management approval. This document exists to:

1. Provide a concrete design that future Phase 2 sprint planning can target
2. Document the rationale for architectural decisions while they are fresh
3. Give security reviewers something specific to evaluate
4. Give a successor engineer the technical context to activate Phase 2 efficiently

---

## TL;DR

In Phase 2, JOM moves from a single-user laptop tool to a multi-user centralised server platform. The key change is the addition of an authentication layer (Microsoft Entra ID SSO) and a server-hosted deployment, while preserving the read-only architecture, runtime JSON trust chain, alert and intelligence layers, and audit trail of Phase 1.

The Phase 1 to Phase 2 transition adds:

- An authentication layer (Microsoft Entra ID SSO at the entry of every route)
- A user allow-list (check authenticated identity against a list of authorised users)
- A per-user audit log (every authentication and page view recorded)
- A network posture change (from 127.0.0.1 local-only to internal HTTPS server)

Everything else carries forward unchanged.

---

## Component responsibilities

### Authentication layer (NEW in Phase 2)

| Component | File | Responsibility |
|-----------|------|----------------|
| SSO entry | auth_multi_user/sso_handler.py | Initiate Entra ID OAuth, handle callback, validate tokens, extract identity |
| Allow-list gate | auth_multi_user/user_allowlist.py | Check authenticated identity against allow-list, manage admin operations |
| Audit log | auth_multi_user/access_audit.py | Record every authentication, page view, and admin operation |
| Feature flags | config/feature_flags.py | Gate Phase 2 code paths until activated |

### Runtime engine (UNCHANGED from Phase 1)

| Component | File | Responsibility |
|-----------|------|----------------|
| OAuth + Admin API | auth.py | Atlassian credential management |
| Collector | data_collector.py, jira_client.py | Live Atlassian data ingestion |
| Admin enrichment | admin_api_client.py, admin_api_enrichment.py | Organisation-level user enrichment |
| Alerting | alert_rules_engine.py | Severity classification |
| Intelligence | intelligence_rules_engine.py | Risk posture, watchlist |
| Source adapter | backend/runtime_source_adapter.py | Select highest-order runtime file |
| Web layer | web.py, templates, static | Render runtime truth |

### Operations (PARTIALLY CHANGED in Phase 2)

| Component | Phase 1 | Phase 2 |
|-----------|---------|---------|
| Scheduled sync | Windows Task Scheduler on laptop | Linux cron or systemd timer on server |
| Snapshot store | Local laptop disk | Server-side disk, backed up |
| Logs | Local laptop files | Server-side files, optional SIEM integration |

---

## Authentication flow (Phase 2)

1. User opens https://jom.gaminglabs/
2. Flask before_request checks for a valid session cookie
3. No session: Flask redirects user to Entra ID authorization URL
4. User authenticates against the GLI Entra ID tenant
5. Entra ID redirects user back to JOM with a code and state parameter
6. JOM validates state (CSRF protection)
7. JOM exchanges code for tokens at the Entra ID token endpoint
8. JOM validates the ID token signature against the JWKS endpoint
9. JOM extracts the user email from claims
10. JOM checks the email against the allow-list via user_allowlist.check_user()
11. If not in allow-list: show access denied page, log denied event
12. If in allow-list: create server-side session, log success event, redirect to original page
13. User can now navigate JOM normally; every page view is audited via access_audit.log_event()

---

## Atlassian token model (Phase 2)

Critical design decision: individual users do NOT use their own Atlassian credentials. JOM holds a single admin token centrally, and all Atlassian queries are made by JOM on behalf of users.

Why this matters:

- Users without Atlassian admin permissions can still see JOM outputs
- Only one token needs rotation and monitoring
- Atlassian rate limits apply to a single coordinated source
- The admin token never leaves the server

The Atlassian admin token in Phase 2 will be stored in a server-side secrets store, not in .env on disk. The expected target is Hashicorp Vault, Azure Key Vault, or GLI standard secrets management — to be decided during Phase 2 Sprint A.

---

## Network posture

| Aspect | Phase 1 | Phase 2 |
|--------|---------|---------|
| Flask bind address | 127.0.0.1 | Internal network interface only |
| Public internet access | No | No |
| TLS | None (local only) | Mandatory, internal CA certificate |
| HTTPS redirect | Not applicable | All HTTP traffic redirected to HTTPS |
| TLS versions | Not applicable | 1.2 minimum, 1.3 preferred |
| Allowed outbound | Atlassian APIs only | Atlassian APIs and Entra ID only |
| Firewall | Host firewall only | Network segmentation enforced |

---

## Data storage model

Phase 2 does NOT introduce a database. Persistence remains file-based:

| Data | Storage | Lifetime |
|------|---------|----------|
| Runtime JSON | Server disk | Always current |
| Snapshots | Server disk | Rolling 20 + daily anchors |
| Allow-list | users.json | Persistent, edited by admin operations |
| Sessions | Server memory or Redis | Until timeout |
| Access audit log | access_audit_YYYY-MM-DD.jsonl | 365 days default |
| Admin operation log | admin_audit_YYYY.jsonl | 7 years (compliance retention) |

The decision to stay file-based aligns with the existing JOM architecture and avoids introducing operational complexity (database administration, backups, schema migrations). If volume justifies it in a future phase, the allow-list and audit logs could migrate to a database without changing the API surface.

---

## Compliance considerations

Phase 2 processes personal data: user emails (for authentication), user identifiers (Entra ID OID), and access patterns (which pages were viewed and when).

Legal basis: legitimate interest (operational monitoring of a controlled internal platform).

GDPR rights supported:

- Right to be informed: privacy notice shown on first login
- Right of access: implemented via access_audit.get_user_events() helper
- Right to erasure: limited — operational logs may be retained under legitimate interest

See Security Posture v2 Section 26.7 for the full compliance treatment.

---

## Deferred decisions

The following decisions are deliberately deferred to Phase 2 sprint planning. They are noted here so they are not forgotten:

1. Allow-list mechanism: flat users.json file vs Entra ID security group integration. Group integration is preferred but depends on IT process.
2. Secrets storage backend: Hashicorp Vault, Azure Key Vault, or GLI internal store. Decision depends on IT infrastructure availability.
3. Server hosting: Linux VM, Windows server, or Docker container. Decision based on GLI operations preferences.
4. Session store: in-memory vs Redis. In-memory is simpler. Redis allows multi-instance deployment if needed later.
5. Logging integration: standalone files vs GLI SIEM. Depends on SIEM availability and access.

---

## Sprint mapping

| Phase 2 Sprint | Focus | This document section |
|----------------|-------|----------------------|
| A — Server preparation | Provision server, HTTPS, deployment scripts | Network posture, Operations |
| B — SSO integration | Implement sso_handler.py properly | Authentication flow, see SSO_INTEGRATION_PLAN.md |
| C — Allow-list | Implement user_allowlist.py properly | Authentication layer, Data storage |
| D — Audit logging | Implement access_audit.py properly | Compliance, Data storage |
| E — Production deployment | IT handover, security review, go-live | All sections |

---

## What this document is NOT

- Not implementation code
- Not a commitment to deliver Phase 2
- Not a security review (see Security Posture v2 for that)
- Not a deployment runbook (each Phase 2 sprint produces its own runbook)

This is an architecture document. It captures intent. The actual implementation will follow this design but may deviate where Phase 2 sprint planning identifies a better approach.

---

## Maintenance

If the dormant scaffolding in auth_multi_user/ is modified, this document should be updated to reflect the new design. If the design changes substantially during Phase 2 planning, this document should be rewritten — not retrofitted.

The goal is that anyone reading this document understands what Phase 2 will look like. If reality diverges from this document, fix the document.
