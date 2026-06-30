from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "reports" / "post_migration_structure_audit.json"
OUT_MD = ROOT / "reports" / "post_migration_structure_audit.md"

EXPECTED_APP_FILES = [
    "app/audits/cleanup_closeout.py",
    "app/audits/project_alignment.py",
    "app/audits/project_ownership.py",
    "app/audits/route_static_reference.py",
    "app/audits/source_freshness.py",
    "app/audits/source_reliability.py",
    "app/audits/tree_final_sanity.py",
    "app/access/named_access_reconciliation.py",
    "app/access/named_access_recovery_plan.py",
    "app/access/named_access_recovery_runner.py",
    "app/access/named_access_truth_v2.py",
    "app/access/reconcile_named_access_truth_v2.py",
    "app/access/user_footprint_source.py",
    "app/access/user_footprint_unlock_runner.py",
    "app/access/group_expansion_recovery_runner.py",
    "app/registry/site_registry_builder.py",
    "app/registry/site_registry_runtime.py",
]

EXPECTED_WRAPPERS_OR_SHIMS = [
    "scripts/build_site_registry.py",
    "backend/site_registry_runtime.py",
    "scripts/run_operational_snapshot.py",
    "scripts/build_named_access_truth_v2.py",
    "scripts/build_user_footprint_source.py",
    "scripts/source_reliability_audit.py",
    "scripts/audit_source_freshness.py",
]

ARCHIVED_TOOLING_SHOULD_BE_ABSENT = [
    "scripts/run_audit_module_migration_v1.py",
    "scripts/run_audit_module_migration_v2.py",
    "scripts/run_builder_module_migration_v1.py",
    "scripts/run_builder_module_migration_v2.py",
    "scripts/run_builder_module_migration_v3.py",
    "scripts/run_registry_module_migration_v1.py",
    "scripts/run_registry_module_migration_v2.py",
    "scripts/repair_audit_module_roots_v1.py",
    "scripts/audit_module_migration_plan.py",
    "scripts/builder_module_migration_plan.py",
    "scripts/registry_module_migration_plan.py",
    "scripts/site_discovery_migration_review.py",
]

EXPECTED_MONITORED = {"gli-it-project", "gli-global-technology", "gli-delivery-tm"}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run(cmd: list[str]) -> dict:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=300)
        return {
            "cmd": " ".join(cmd),
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-3000:],
            "stderr_tail": (proc.stderr or "")[-3000:],
        }
    except Exception as exc:
        return {"cmd": " ".join(cmd), "returncode": None, "error": str(exc)}


def read_json(path: Path):
    if not path.exists(): return None
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc: return {"_read_error": str(exc)}


def git_status() -> str:
    result = run(["git", "status", "--short"])
    return result.get("stdout_tail", "")


def monitored_scope() -> dict:
    reg = read_json(ROOT / "static" / "data" / "site_registry.json") or {}
    monitored, discovered = [], []
    if isinstance(reg, dict):
        for site in reg.get("sites", []):
            if not isinstance(site, dict): continue
            key = site.get("site_key") or site.get("key") or site.get("site")
            if site.get("is_monitored") is True or site.get("classification") == "monitored":
                monitored.append(key)
            elif site.get("classification") == "discovered":
                discovered.append(key)
    monitored = sorted([x for x in monitored if x])
    discovered = sorted([x for x in discovered if x])
    return {
        "monitored": monitored,
        "discovered": discovered,
        "expected_monitored": sorted(EXPECTED_MONITORED),
        "monitored_matches_expected": set(monitored) == EXPECTED_MONITORED,
    }


def main() -> int:
    checks = []
    for rel in EXPECTED_APP_FILES:
        checks.append({"type": "expected_app_file", "path": rel, "ok": (ROOT / rel).exists()})
    for rel in EXPECTED_WRAPPERS_OR_SHIMS:
        checks.append({"type": "expected_wrapper_or_shim", "path": rel, "ok": (ROOT / rel).exists()})
    for rel in ARCHIVED_TOOLING_SHOULD_BE_ABSENT:
        checks.append({"type": "archived_tooling_absent", "path": rel, "ok": not (ROOT / rel).exists()})

    py_files = [str(ROOT / p) for p in EXPECTED_APP_FILES + EXPECTED_WRAPPERS_OR_SHIMS if p.endswith(".py") and (ROOT / p).exists()]
    compile_run = run([sys.executable, "-m", "py_compile"] + py_files) if py_files else {"returncode": 1, "error": "no python files found"}
    import_run = run([sys.executable, "-c", "import backend.site_registry_runtime; import app.registry.site_registry_runtime; print('registry imports ok')"])
    snapshot_run = run([sys.executable, "scripts/run_operational_snapshot.py"])
    reliability_run = run([sys.executable, "scripts/source_reliability_audit.py"])
    route_run = run([sys.executable, "scripts/route_static_reference_validation.py"])

    reliability = read_json(ROOT / "static" / "data" / "source_reliability_status.json") or {}
    issue_count = (reliability.get("summary") or {}).get("issue_count", reliability.get("issue_count"))
    freshness_overall = (reliability.get("summary") or {}).get("freshness_overall", reliability.get("freshness_overall"))
    scope = monitored_scope()

    validation_runs = [compile_run, import_run, snapshot_run, reliability_run, route_run]
    all_file_checks_ok = all(c["ok"] for c in checks)
    validation_ok = all(v.get("returncode") == 0 for v in validation_runs)
    ok = all_file_checks_ok and validation_ok and issue_count == 0 and scope["monitored_matches_expected"]

    payload = {
        "schema": "jom-post-migration-structure-audit-v1",
        "generated_at_utc": now_utc(),
        "status": "ok" if ok else "attention",
        "summary": {
            "file_checks_ok": all_file_checks_ok,
            "validation_ok": validation_ok,
            "issue_count": issue_count,
            "freshness_overall": freshness_overall,
            "monitored_matches_expected": scope["monitored_matches_expected"],
            "git_status_short": git_status(),
        },
        "file_checks": checks,
        "validation_runs": validation_runs,
        "monitored_scope": scope,
        "remaining_work_recommendation": [
            "Review site_discovery.py at function level before moving it.",
            "Continue with app/builders for admin/estate/product truth builders only after a dedicated plan.",
            "Review root collectors and API clients before moving admin/data collection logic.",
            "Do not split web.py until runtime and collectors are stable.",
            "Review cleanup/archive policy for pycache and backup volume separately.",
        ],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = ["# Post-Migration Structure Audit", "", f"Generated: `{payload['generated_at_utc']}`", "", f"Status: **{payload['status']}**", "", "## Summary", ""]
    for k, v in payload["summary"].items(): lines.append(f"- {k}: **{v}**")
    lines += ["", "## Remaining Work Recommendation", ""]
    for item in payload["remaining_work_recommendation"]: lines.append(f"- {item}")
    lines += ["", "## File Check Failures", ""]
    failures = [c for c in checks if not c["ok"]]
    if failures:
        for f in failures: lines.append(f"- `{f['path']}` ({f['type']})")
    else:
        lines.append("- None")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": payload["status"], "issue_count": issue_count, "validation_ok": validation_ok, "file_checks_ok": all_file_checks_ok, "json": str(OUT_JSON), "report": str(OUT_MD)}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
