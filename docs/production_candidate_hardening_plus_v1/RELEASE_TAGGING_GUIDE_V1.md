# Release Tagging Guide v1

## Recommended tag after this hardening pack is committed

```powershell
git tag production-candidate-v2-hardening-v1
git push origin production-candidate-v2-hardening-v1
```

## Pre-tag checks

```powershell
git status --short
```

Expected result:

```text
nothing returned
```

## Tag meaning

This tag represents the JOM Production Candidate v2 baseline after core workspace consolidation, Admin discovery alignment, executive reporting outputs and hardening validation.
