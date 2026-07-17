# Release Candidate Checklist

## Before Demo / Candidate Tag
- [ ] Start Flask using `python -m app.web`.
- [ ] Open `/`, `/estate`, `/reference` and at least one `/site/<site-key>` route.
- [ ] Confirm readiness strip loads.
- [ ] Confirm Admin Intelligence Centre loads.
- [ ] Confirm Site Workspace does not freeze.
- [ ] Confirm no stale `Loading signals...` marker appears.
- [ ] Confirm `git status --short` returns no output.
- [ ] Confirm latest production candidate validation report is PASS or PASS_WITH_CHANGES with no issues.

## Optional Tag Command
Use only after reviewing the validation report:

```powershell
git tag -a production-candidate-v1 -m "JOM production candidate v1"
git push origin production-candidate-v1
```
