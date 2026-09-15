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

### 8 September 2026 - Site Workspace and Discovery operational completion closeout

#### Accepted milestones

Two consumer-integration milestones were installed, validated, isolated from unrelated runtime drift, committed to `main`, and accepted:

- **Site Workspace Project Authority Integration**, commit `7a51d3ec489c4405de285fe136a65f4957f950ae` (`7a51d3e`), message `Site Workspace: integrate project authority`.
- **Discovery Authority Integration**, commit `ec38a54d576ffb68d621df83575593146dc17d82` (`ec38a54`), message `Discovery: integrate existing authority`.

#### Site Workspace current owner and authority position

Site Workspace now consumes the existing governance project authorities for the selected site. No new collector, runtime authority contract, or backend API was created.

Owner boundary:

- `templates/site_workspace.html`
- `static/js/jom_site_workspace_shell_v1.js`
- `static/css/jom_site_workspace_shell_v1.css`
- `scripts/validate_site_workspace_project_integration_v1.py`

Reused read-only routes:

- `/api/governance/projects`
- `/api/governance/projects/leads`
- `/api/governance/projects/owners`

The selected-site surface now presents project inventory, project lead authority, governance-defined space-owner authority, and governance coverage or gap state. Marketplace Apps and Automation remain explicitly unavailable where current authority does not prove those populations.

#### Discovery current owner and authority position

The Admin Discovery placeholder was replaced by a dedicated read-only consumer of the existing Discovery authority. No new collector, runtime authority contract, or backend API was created.

Owner boundary:

- `templates/admin_discovery.html`
- `static/js/jom_admin_discovery_v1.js`
- `static/css/jom_admin_discovery_v1.css`
- `scripts/validate_discovery_authority_integration_v1.py`

Reused read-only routes:

- `/api/estate/discovery-authority`
- `/api/estate/discovery-authority/coverage`

Discovery now presents current discovered identity scope, lifecycle review items, monitored classification, and source coverage. Lifecycle decisions remain owned by Estate and Site Review. Static fallback remains disabled. Retired-site population remains unavailable unless a current authority contract explicitly publishes it.

#### Foundation Recovery and surface-classification position

- FR-001, FR-002, and FR-003 remain verified resolved.
- FR-004 timestamp meaning consistency remains an evidence-controlled limitation until every affected consumer has been proven to distinguish collection, derivation, refresh completion, and authority-change time. This closeout does not fabricate closure of FR-004.
- FR-005 is materially reduced: Runtime Status and Source Health already had passing current-contract validation, Site Workspace project authority is now integrated, and Discovery is no longer a static placeholder. Any remaining surface must still be classified from its own owner and runtime evidence rather than by broad programme assumption.

#### Repository state at continuity gate

The product commits are complete. The working tree still contains unrelated generated runtime drift and untracked audit or report artefacts. These were deliberately excluded from both product commits and must not be deleted, staged, or committed without controlled classification. Known outstanding local items include:

- modified files under `runtime/data/`;
- `builders.txt`;
- `scripts.txt`;
- `scripts/validate_runtime_truth_chain_alignment_v1.py`;
- `test-validator-output.txt`.

The current authoritative next workstream is **Controlled Repository Hygiene Classification**. Classify each remaining item as `KEEP`, `COMMIT`, `GENERATED_RUNTIME`, `REPORT_ONLY`, `TRANSIENT`, or another explicitly justified category before taking action.

#### Continuation and Git gate

After installing this BOOKSYNC pack:

1. Run the packaged BOOKSYNC validator.
2. Run `git diff --check`.
3. Inspect `git status --short`.
4. Stage only the nine BOOKSYNC owners and the packaged BOOKSYNC validator.
5. Run `git diff --cached --check` and inspect the staged boundary.
6. Commit the continuity milestone separately from runtime drift.
7. Do not push or clean unrelated files unless the current operator workflow explicitly reaches that gate.

Continue using full owner-file replacements and complete downloadable packs. No patches, snippets, manual editing, wrappers, or overlay layers. Conclusions must remain backed by repository, validator, API, or live runtime evidence.
### 14 September 2026 - Command Centre UX Phase 4.3 closeout

#### Accepted outcome
- Baseline commit before this uncommitted milestone: 3b8b6b9, Command Centre UX Phase 3: monitoring wall and colour harmonisation.
- Current milestone: Command Centre UX Phase 4.3, Continuous Telemetry Recorder.
- Status: implemented, validated and visually accepted; pending BOOKSYNC installation, exact-boundary staging, commit and push.
- The Command Centre is now monitoring-first. A compact operational header is followed by the Monitoring Wall, monitored-estate and current-evidence areas, then the Action Required workflow.
- The fixed right operations rail is retained and contained within the viewport. Monitoring Coverage, Estate Snapshot and Operational Status remain in one rail with internal scrolling where required.
- Runtime, Source Health, Discovery and Users & Access use gapless continuous right-to-left recorder tracks. Each track contains two equal waveform segments in a 200 percent flex track translated exactly 50 percent, preventing blank gaps and visible restarts.
- Travelling dots, whole-wave vertical bobbing and SVG path morphing are absent. Reduced-motion handling is retained.
- The wall uses the established JOM blue, neutral and semantic healthy, review and critical palette.

#### Authority and operational boundary
- Page: /home.
- Existing read-only information route: /api/workspace/command-centre.
- No backend route, collector, runtime contract or authority source changed.
- Animation visualises the state loaded in the current Command Centre contract. Animation is not evidence of a network request, continuous poll or live collector execution.
- The current-evidence Contract served value is request-serving evidence. It must not be interpreted as collection time, derived-authority time or an authority-change timestamp. FR-004 Timestamp Meaning Consistency remains open.
- Command Centre is no longer a legacy-placeholder presentation for FR-005 purposes. This records accepted consumer presentation and operator workflow only; it does not fabricate closure of FR-004 or claim new collector authority.

#### Current owners
- templates/home.html
- static/js/jom_command_centre_completion_v1.js
- static/css/jom_command_centre_completion_v1.css
- scripts/validate_command_centre_ux_phase1_v1.py
- scripts/validate_command_centre_ux_phase4_3_v1.py

#### Validator hygiene
- Permanent validation owners for the accepted state are scripts/validate_command_centre_ux_phase1_v1.py and scripts/validate_command_centre_ux_phase4_3_v1.py.
- The following intermediate milestone and delivery validators are obsolete after Phase 4.3 acceptance and must be removed before staging: scripts/validate_command_centre_ux_phase4_v1.py, scripts/validate_command_centre_ux_phase4_jom_colour_owner_v1.py, scripts/validate_command_centre_ux_phase4_1_v1.py, scripts/validate_command_centre_ux_phase4_1_eof_v1.py, scripts/validate_command_centre_ux_phase4_2_v1.py and scripts/validate_command_centre_ux_phase4_3_eof_v1.py.
- Git history and the delivery packs remain the recovery evidence for those intermediate gates. They are not active repository authority.

#### Validation and acceptance evidence
- Phase 1 regression validation passed.
- Phase 4.3 continuous-recorder validation passed after the CSS terminal-newline correction.
- /home returned HTTP 200.
- /api/workspace/command-centre returned HTTP 200.
- Fixed right-rail bindings and viewport containment passed.
- JOM colour ownership, monitored-site filtering, no-polling boundary and reduced-motion handling passed.
- Luke visually accepted the final continuous recorder on 14 September 2026.
- Generated runtime drift was preserved outside the repository and restored before BOOKSYNC.

#### Commit boundary and continuation
- Product owners to stage: templates/home.html, static/js/jom_command_centre_completion_v1.js and static/css/jom_command_centre_completion_v1.css.
- Retained validators to stage: scripts/validate_command_centre_ux_phase1_v1.py and scripts/validate_command_centre_ux_phase4_3_v1.py.
- BOOKSYNC owners to stage: BOOKSYNC Guide.md, GitHub Repository Record.json, JOM Change History.md, JOM Guide v2 Additions.md, JOM Progress and Improvements.md, JOM Quick Start.md, JOM Recovery Guide.md, JOM System and File Map.md and The Jira Observation Monitor Guide.md.
- BOOKSYNC validator to stage: scripts/validate_command_centre_ux_phase4_3_booksync_v1.py.
- Immediate next step: install this BOOKSYNC pack, run the product and BOOKSYNC validators, delete the six obsolete untracked validators through the packaged runner, inspect git status and git diff, stage only the approved fifteen-file boundary, run git diff --cached --check, inspect staged names, commit and push.
- Next workstream after clean push: continue FR-005 Placeholder and Legacy Surface Classification with the next unaccepted surface selected from current repository evidence. FR-004 remains open.
- Working rule remains Audit -> Build -> Install -> Validate -> Live test -> Clean -> BOOKSYNC -> Stage -> Commit -> Push, using full owner-file replacement packs and no manual editing.
