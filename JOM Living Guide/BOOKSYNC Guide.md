# BOOKSYNC Guide

Trigger word: `BOOKSYNC`.

When BOOKSYNC is invoked, update the current-state summary, affected page chapter, owner map, authority catalogue, progress register, change history, known limitations, current next step and rule changes. Validate paths against the repository. Documentation changes are staged with the product milestone. `GIT SAVE` includes BOOKSYNC before staging and commit. Minor command reruns or cleanup-only actions do not require a book update.

## Estate Configuration BOOKSYNC record
- Milestone authority: `jom-admin-estate-configuration-authority-v1`.
- Product owners: `app/web.py`, Estate Configuration template, dedicated JavaScript, dedicated CSS and validator.
- Validated authority: 4 sites, 100% tenant identity, 75% resource mapping, 75% ownership and 97 assignments.
- Known gaps: business classification, criticality, region, business unit, tags, partial resource mapping and partial ownership.
- Privacy boundary: no personal contact fields returned.
- Commit gate: stage product and documentation owners together only after diff validation.
