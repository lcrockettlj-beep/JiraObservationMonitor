# JOM Legacy Runtime Contract Cleanup Pack v1

Purpose: targeted cleanup of remaining legacy estate runtime filename references after backend static truth reference repair.

Targets:
- `app/web.py`
- `app/registry/site_registry_runtime.py`
- `scripts/build_site_registry.py`

Scope:
- No UI changes
- No CSS changes
- No HTML changes
- No frontend JS changes
- No overlays/layers
- No runtime truth fabrication

What it does:
1. Creates timestamped backups under `reports/legacy_runtime_contract_cleanup_v1_backups/`.
2. Removes the obsolete top-of-file monitored-sites compatibility comment if present.
3. Repoints site registry output defaults from old/static locations to `runtime/data/site_registry.json`.
4. Repoints registry build script reads to `runtime/data` instead of static data where exact safe patterns exist.
5. Adds a report of remaining legacy filename references that require deeper route-level refactor if still present.
6. Runs `py_compile` on changed Python files.
7. Optionally smoke-tests key routes if Flask can start locally.

## Run from repo root

```powershell
cd C:\Users\Luke_C\Desktop\JiraObservationMonitor
Expand-Archive -Path "$HOME\Downloads\jom_legacy_runtime_contract_cleanup_pack_v1.zip" -DestinationPath ".\jom_legacy_runtime_contract_cleanup_pack_v1" -Force
.\jom_legacy_runtime_contract_cleanup_pack_v1\save_legacy_runtime_contract_cleanup_v1.ps1
```

## Output

```text
reports/legacy_runtime_contract_cleanup_v1.txt
reports/legacy_runtime_contract_cleanup_v1.json
```

## Review after running

```powershell
git diff --stat
git status --short
python -m py_compile app\web.py
python -m py_compile app\registry\site_registry_runtime.py
```

Do not commit until the report is reviewed.
