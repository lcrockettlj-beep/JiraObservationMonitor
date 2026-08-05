## JOM Continuous Improvement Register

Updated: 2026-08-05T16:59:47Z

### Current authority rule
- Current source pipeline: Atlassian OAuth/Admin/runtime authority only.
- If OAuth/Admin/runtime authority cannot prove a data area, the user-facing page must show unavailable or omit the value rather than infer it.
- Product-access assignments are not active-user counts and must be labelled separately.
- Commercial billing values remain unavailable until a proven billing authority source exists.
- Future sources such as webhooks, exports, billing-specific APIs, or manual uploads are later options only.

### Completed authority pages as of 2026-08-05
- Admin / Licensing & Billing: completed and pushed at commit 1c28103.
- Admin / Users & Access: completed and pushed at commit 50cc29b.
- Admin / Monitoring: completed and pushed before System Configuration phase.
- Admin / System Configuration: completed and pushed at commit f9502e8.
- Reporting / Executive Report: completed and pushed at commit 1314695.

### Remaining page build plan
1. Reporting / Estate Report.
2. Reporting / Governance Report.
3. Source Health.
4. Runtime Status.
5. Discovery.
6. Estate Configuration, only if still required after review.

### Core page OAuth reconfirmation queue
The following pages are unlocked for OAuth/runtime data-path reconfirmation after reporting and operational visibility pages are complete:
- Command Centre.
- Estate.
- Site Workspace.
- Site Review / lifecycle handled through Estate.

Reconfirmation scope:
- Confirm shared OAuth/runtime authority paths.
- Confirm metric definitions are consistent across pages.
- Remove stale static or legacy truth references.
- Keep active users unavailable unless proven by unique active-user authority.
- Keep commercial billing unavailable unless proven by billing authority.
- Add Atlassian action links where authority allows safe navigation.

### Improvement areas

#### Admin / Licensing & Billing
- Missing data: invoice amounts, payment methods, billing account details, renewals, and commercial contract evidence.
- Current state: authority page completed; commercial billing remains unavailable when unproven.
- Future option: review billing-admin access, official API availability, exports, webhooks, or approved billing source.
- Priority: Later.

#### Admin / Users & Access
- Missing data: proven unique active-user authority.
- Current state: authority page completed; product-access assignments are separate from active users.
- Future option: add OAuth/Admin-backed unique active-user collector if Atlassian authority can prove it.
- Priority: Later.

#### Admin / Monitoring
- Missing data: deeper collector/job/error evidence by source area.
- Current state: authority page completed; source-health failures are surfaced as review actions.
- Future option: expose collector and job-level runtime status by area.
- Priority: Later.

#### Admin / System Configuration
- Missing data: richer environment/runtime metadata and deployment configuration evidence.
- Current state: authority page completed; guardrails and unavailable authority states are visible.
- Future option: add verified configuration inventory once deployment model is final.
- Priority: Later.

#### Reporting / Executive Report
- Missing data: proven active-user authority, commercial billing authority, and deeper leadership trend evidence.
- Current state: authority page completed; board-level actions and unavailable values are visible.
- Future option: add trend reporting and Atlassian action links after page authority is complete.
- Priority: Later.

#### Reporting / Estate Report
- Missing data: estate report page authority build.
- Current state: next build target.
- Future option: report monitored-site coverage, product access, site status, and source assurance from existing authority contracts.
- Priority: Now.

#### Reporting / Governance Report
- Missing data: governance report page authority build.
- Current state: not yet wired to current OAuth/runtime authority contracts.
- Future option: report truth guardrails, unavailable authority states, source assurance, and governance actions.
- Priority: Now.

#### Runtime Status
- Missing data: detailed app/API/collector/job/error metrics.
- Current state: no dedicated runtime-health page contract completed yet.
- Future option: expose runtime health by area.
- Priority: Next.

#### Source Health
- Missing data: freshness, completeness, and failure evidence by source.
- Current state: partial source reliability exists and is consumed by several authority pages; dedicated source-health page still needed.
- Future option: split source-health contract by source and evidence type.
- Priority: Next.

#### Discovery
- Missing data: clear current discovery authority page after monitored estate stabilisation.
- Current state: monitored estate is currently 4 sites; discovery page still needs review and build.
- Future option: show candidate organisations/sites separately from monitored estate truth.
- Priority: Later.
