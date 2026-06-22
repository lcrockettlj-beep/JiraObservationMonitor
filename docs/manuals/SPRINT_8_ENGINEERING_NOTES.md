# Sprint 8 Engineering Notes

## What worked well
- Shared navigation simplified frontend consistency.
- Incremental commits reduced recovery risk.
- CSS-first polish changes improved the UI safely.

## Lessons learned
- Large combined installers are higher risk for templated pages containing Jinja macros.
- Safe recovery using backups prevented bad commits.
- Smaller page-specific passes are more reliable than multi-page structural changes.

## Recommended future rule
When a page contains macros or dense Jinja logic, perform wording and styling changes separately from structural refactors.