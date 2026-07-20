# JOM Release Candidate Tagging Guide v1

## Recommended Tag

```text
production-candidate-v2-demo-ready
```

## Create Tag

```powershell
git status --short
git tag production-candidate-v2-demo-ready
git push origin production-candidate-v2-demo-ready
```

Expected before tagging:

```text
nothing returned
```

Current commit at prep time:

```text
555d1d7
```
