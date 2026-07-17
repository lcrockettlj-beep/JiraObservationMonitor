# Release Tagging Guide

## Suggested Candidate Tag
`production-candidate-v1`

## PowerShell Commands
```powershell
cd "C:\Users\Luke_C\Desktop\JiraObservationMonitor"
git status --short
git tag -a production-candidate-v1 -m "JOM production candidate v1"
git push origin production-candidate-v1
```

## Rule
Only tag after the production candidate validation report has no issues and the working tree is clean.
