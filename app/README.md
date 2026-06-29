# JOM App Package Scaffold

This folder is intentionally scaffold-only at this stage.

Current rule:

- `scripts/` remains the operational execution layer.
- Existing root modules remain in place.
- No runtime logic has been moved.
- Future move packs should migrate one area at a time and keep compatibility wrappers.

Target areas:

- `collectors/` — source/API collection modules
- `builders/` — data contract builders and transformers
- `audits/` — reliability, freshness, alignment and validation checks
- `runtime/` — orchestration, sync and snapshot helpers
- `access/` — named access, group expansion, reconciliation, user footprint
- `registry/` — site discovery and site registry logic
- `shared/` — shared helper utilities
