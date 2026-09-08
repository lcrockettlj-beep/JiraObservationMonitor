# JOM Guide v2 Additions

This file records the full v2 additions applied to the Word guide: GitHub Repository Authority, Full System Architecture Document, Full Technical Specification, Evidence Classification and Assurance, Deployment Readiness, and BOOKSYNC v2 Control. The original full Markdown guide remains included without summarising its detailed appendices or change history.

## GitHub Repository Record

```json
{
  "name": "JiraObservationMonitor",
  "full_name": "lcrockettlj-beep/JiraObservationMonitor",
  "visibility": "public",
  "private": false,
  "html_url": "https://github.com/lcrockettlj-beep/JiraObservationMonitor",
  "default_branch": "main",
  "created_at": "2026-06-11T10:14:13Z",
  "updated_at": "2026-08-14T14:26:01Z",
  "pushed_at": "2026-08-14T14:25:57Z",
  "size": 4421,
  "language": "Python",
  "open_issues_count": 0
}
```

## 8 September 2026 - Foundation Recovery closeout and current continuation

### Evidence-backed current state

This record updates the definitive JOM continuity position from the later runtime-alignment reports, retained validators, repository-cleanup validation and live checks completed on 8 September 2026. Earlier Foundation Recovery entries remain historical evidence, but their open-finding list is superseded by this current-state record where closure is proven.

- **FR-001 Users & Access drill-downs:** verified resolved. The current `runtime/data/users_access_actionable_drilldown_v1.json` contract regenerates with `status: ok`, `authority.safe_to_serve: true`, current freshness, complete organisation and directory pagination, supported categories available, email storage disabled, and export, download and write actions disabled. The Not invited population remains honestly unavailable because the tested Atlassian APIs do not expose that administration state.
- **FR-002 Unified runtime refresh status:** verified resolved. `runtime/data/runtime_refresh_status.json` exists and records canonical execution lifecycle and completion evidence.
- **FR-003 Refresh architecture:** verified resolved. Runtime Truth Alignment v1.1 Corrected, Runtime Finalization Alignment, Runtime Truth Chain validation, and Runtime Status / Source Health UX validation passed against the canonical architecture.
- **FR-004 Timestamp meaning consistency:** open and current. Consumers must distinguish live collection time, derived-contract time, refresh completion time, and configuration or authority-change time. File modification time or an unclassified `generated_at_utc` value is not sufficient proof of timestamp meaning.
- **FR-005 Placeholder and legacy surface classification:** open and next. Runtime Status and Source Health now have passing current-contract validation, but Discovery and remaining legacy or placeholder surfaces require explicit page-by-page classification and acceptance.

### Product Access authority evidence

The live Product Access collector `app/builders/estate_product_access.py` regenerated `runtime/data/estate_product_access.json` and `runtime/data/estate_access_truth.json` on 8 September 2026.

- Status: `partial`
- OAuth-accessible Jira resources: 6
- Successfully collectible application-role sites: 5
- Jira role rows: 5
- Live Jira product users across collectible resources: 169
- Reported seat limit: 12,150
- Reported remaining seats: 11,981
- Error sites: 1

`gli-usa` returned HTTP 403 with `Tenant is restricted: user-cancellation`. This is an Atlassian-controlled tenant restriction, not a JOM collector defect. The 169 total is current live authority for five collectible resources and is not presented as complete coverage of all six OAuth-accessible resources. No stale static Product Access fallback was used.

### Users & Access live evidence

The actionable drill-down builder was run directly on 8 September 2026 and reported 1,218 organisation accounts, 145 directory accounts, 92 MFA-disabled accounts, 4 organisation administrators, 4 site administrators, 41 user-access administrators, 1 high-access-concentration account, 7 unmanaged accounts, and zero suspended, deactivated or deletion-marked accounts. These are time-sensitive evidence values and must not be hard-coded into consumers or validators.

### Current and next workstream

- **Current phase:** Foundation Recovery closeout and runtime-truth hardening.
- **Current workstream:** FR-004 Timestamp Meaning Consistency audit.
- **Next workstream:** FR-005 Placeholder and Legacy Surface Classification audit.
- Do not reopen FR-001, FR-002 or FR-003 unless an owner changes, a retained validator fails, or new live evidence contradicts this record.
- Do not classify the `gli-usa` restriction as a JOM defect unless a later live Atlassian response proves a different tenant state.

### Working and Git rules

Continue: `Audit -> Build -> Install -> Validate -> Live test -> Clean -> BOOKSYNC -> Stage -> Commit -> Push`.

Use complete downloadable packs and full owner-file replacements only. Do not use patches, snippets, manual edits, wrappers or overlay layers. Surface repository and runtime evidence before conclusions, report unavailable authority as unavailable, keep temporary artefacts out of the repository root, run `git diff --check` before staging, inspect the exact milestone boundary, and run `git diff --cached --check` after staging.
