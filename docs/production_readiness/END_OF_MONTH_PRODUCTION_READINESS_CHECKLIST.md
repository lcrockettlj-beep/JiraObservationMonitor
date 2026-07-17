# JOM End-of-Month Production Readiness Checklist

## Goal
Prepare JOM for a reliable end-of-month operational demonstration / production-baseline handover.

## Current Production-Baseline Workspaces
- Command Centre: estate-wide operational overview.
- Estate: estate operations and site drilldown entry point.
- Admin: governance, identity, source and runtime control workspace.
- Site Workspace: site-level investigation view.

## Required Go-Live Checks
- [ ] Flask app starts cleanly with `python -m app.web`.
- [ ] `/` returns HTTP 200.
- [ ] `/estate` returns HTTP 200.
- [ ] `/reference` returns HTTP 200.
- [ ] `/site/gli-it-project` returns HTTP 200.
- [ ] `/site/gli-delivery-tm` returns HTTP 200.
- [ ] `/site/gli-global-technology` returns HTTP 200.
- [ ] Operator endpoints return HTTP 200.
- [ ] Registry, product-access, user-footprint and admin-truth endpoints return HTTP 200.
- [ ] No stale frontend overlay assets remain.
- [ ] No `Loading signals...` or duplicate Home intelligence markers remain.
- [ ] Git working tree is clean before stakeholder demo.

## Known Current Scope
- Platform is read-only.
- `/api/*` compatibility fallback routes are retained.
- Export buttons may remain planned placeholders unless an export pack is applied.
- Admin actions are represented as governance/control visibility unless explicit write controls are introduced later.

## End-of-Month Readiness Decision
Use the latest generated `END_OF_MONTH_PRODUCTION_READINESS_SUMMARY.md` report as the release gate.
