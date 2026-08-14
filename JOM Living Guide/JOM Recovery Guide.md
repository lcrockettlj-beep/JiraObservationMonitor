# JOM Recovery Guide

After an interrupted session, first inspect branch, HEAD and working tree. Do not reapply packs blindly. Identify modified tracked files, untracked pack folders, transient logs and runtime drift. Restore unrelated runtime files only after confirming they are not the intended milestone. Re-run syntax and contract checks. Use the latest committed guide and Git history to locate the last complete milestone.

For a new conversation, provide the Quick Start section, current `git status --short`, latest commit, current workstream and relevant owner files. Broad repository re-audits should be avoided when the guide is current.

## Repository recovery checklist
- `git branch --show-current`
- `git log -1 --oneline`
- `git status --short`
- Separate intended owner changes from runtime drift.
- Remove extracted `_pack_` and `_audit_` folders after evidence is retained.
- Remove transient access logs before commit.
- Compile Python owners and run packaged validators.
- Run `git diff --check` before staging and `git diff --cached --check` after staging.

### Estate Configuration recovery point
If work is interrupted before commit, retain only the five Estate Configuration product owners and the BOOKSYNC documentation replacements. Restore unrelated runtime JSON drift and remove transient JSONL access logs before staging. Re-run `python scripts\validate_estate_configuration_v1.py`, `python -m py_compile app\web.py`, `git diff --check` and live contract validation before committing.
