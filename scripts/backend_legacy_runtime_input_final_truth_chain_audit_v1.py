from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEGACY_INPUTS = {
    "latest_run.json": "legacy runtime collector snapshot",
    "latest_run_pretty.json": "legacy runtime collector pretty snapshot",
    "latest_run_safe_partial.json": "legacy safe partial runtime snapshot",
    "latest_run_admin_enriched.json": "legacy admin enriched runtime snapshot",
    "latest_run_admin_enriched_pretty.json": "legacy admin enriched pretty snapshot",
    "billing_seats.json": "legacy billing seat snapshot",
    "latest_snapshot.json": "legacy snapshot controller output",
    "snapshot_index.json": "legacy snapshot index",
}

SCAN_DIRS = ["app", "scripts"]
TEXT_SUFFIXES = {".py", ".ps1", ".html", ".js", ".css", ".md", ".txt", ".json", ".yaml", ".yml"}
WEBSITE_FACING_PATH_PARTS = {
    "app/web.py",
    "app/operational/operator_surface.py",
    "app/reporting/export_reporting.py",
}
POLICY_MARKERS = {
    "LEGACY_NON_WEBSITE_TRUTH_FILES",
    "blocked_legacy_static_input",
    "not website truth",
    "BLOCKED_LEGACY_STATIC_INPUT",
}
RUNTIME_INTERNAL_PATH_PARTS = {
    "app/runtime/",
    "app/builders/",
    "app/registry/",
    "app/access/",
    "scripts/audit_source_freshness.py",
    "scripts/backend_runtime_freshness_snapshot_elimination_v1.py",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        return ""


def iter_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for folder in SCAN_DIRS:
        base = root / folder
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                files.append(path)
    return sorted(files)


def classify_reference(path_rel: str, line_text: str, target: str) -> tuple[str, str, bool]:
    policy_only = any(marker in line_text for marker in POLICY_MARKERS)
    if policy_only:
        return "POLICY_BLOCK_REFERENCE", "Reference is part of the live-truth block policy, not data usage.", False

    if path_rel in WEBSITE_FACING_PATH_PARTS:
        return "REPLACE_REQUIRED_WEBSITE_RISK", "Website-facing code references a legacy/static input and should be replaced with a live or auto-refreshed source.", True

    if any(part in path_rel for part in RUNTIME_INTERNAL_PATH_PARTS):
        if target in {"latest_snapshot.json", "snapshot_index.json"}:
            return "REVIEW_REMOVE_OR_RUNTIME_ONLY", "Snapshot controller reference must remain internal only or be removed after endpoint validation.", False
        return "INTERNAL_REFRESH_INPUT_REVIEW", "Reference is inside a builder/runtime pipeline; keep only if it feeds an auto-refresh chain and is not exposed directly to the website.", False

    return "REVIEW_UNKNOWN_USAGE", "Legacy/static input reference found outside known classifications; review before keeping.", True


def scan_legacy_refs(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    targets = sorted(LEGACY_INPUTS.keys(), key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(item) for item in targets))
    for path in iter_text_files(root):
        text = read_text(path)
        if not text:
            continue
        path_rel = rel(path, root)
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in pattern.finditer(line):
                target = match.group(0)
                classification, reason, blocking = classify_reference(path_rel, line, target)
                rows.append({
                    "file": path_rel,
                    "line": line_number,
                    "target": target,
                    "source_description": LEGACY_INPUTS[target],
                    "classification": classification,
                    "website_blocking": blocking,
                    "reason": reason,
                    "line_text": line.strip()[:260],
                })
    return rows


def endpoint_truth_map() -> list[dict[str, Any]]:
    return [
        {
            "endpoint": "/api/operator/status",
            "builder": "build_operator_summary()",
            "allowed_sources": ["runtime_execution_status.json", "source_freshness_audit.json", "source_reliability_status.json", "admin_truth_v2.json"],
            "truth_rule": "live or auto-refreshed only",
            "legacy_static_allowed": False,
        },
        {
            "endpoint": "/api/operator/insights / drilldowns / role-views / ui-view",
            "builder": "build_operator_surface()",
            "allowed_sources": ["runtime_execution_status.json", "site_registry.json", "source_freshness_audit.json", "source_reliability_status.json", "admin_truth_v2.json", "user_footprint.json", "estate_product_access.json"],
            "truth_rule": "live or auto-refreshed only",
            "legacy_static_allowed": False,
        },
        {
            "endpoint": "/admin/truth",
            "builder": "admin truth chain / generated admin_truth_v2.json",
            "allowed_sources": ["admin_truth_v2.json", "runtime/live admin source chain"],
            "truth_rule": "generated output must be refreshed by backend chain before website trust",
            "legacy_static_allowed": False,
        },
        {
            "endpoint": "/users/footprint",
            "builder": "user footprint source chain / generated user_footprint.json",
            "allowed_sources": ["user_footprint.json", "named access reconciliation runtime outputs"],
            "truth_rule": "guarded live/generated output only",
            "legacy_static_allowed": False,
        },
        {
            "endpoint": "/api/source-health or source contract routes",
            "builder": "source freshness and reliability audits",
            "allowed_sources": ["source_freshness_audit.json", "source_reliability_status.json", "runtime_live_truth_status.json"],
            "truth_rule": "status outputs describe freshness and must not become stale truth themselves",
            "legacy_static_allowed": False,
        },
    ]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    rows = payload["legacy_references"]
    lines: list[str] = []
    lines.append("# Backend Legacy Runtime Input Replacement & Final Truth Chain Audit v1")
    lines.append("")
    lines.append("## Result")
    lines.append(f"- Overall status: **{payload['overall_status']}**")
    lines.append(f"- Generated at UTC: {payload['generated_at_utc']}")
    lines.append(f"- Legacy reference rows: {payload['summary']['legacy_reference_rows']}")
    lines.append(f"- Website-blocking rows: {payload['summary']['website_blocking_rows']}")
    lines.append("")
    lines.append("## Plain Rule")
    lines.append("If it is not live/current or auto-refreshed, it must not feed the website.")
    lines.append("")
    lines.append("## Classification Summary")
    for key, value in sorted(payload["summary"]["by_classification"].items()):
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Endpoint Truth Map")
    for item in payload["endpoint_truth_map"]:
        lines.append(f"### {item['endpoint']}")
        lines.append(f"- Builder: {item['builder']}")
        lines.append(f"- Truth rule: {item['truth_rule']}")
        lines.append(f"- Legacy/static allowed: {item['legacy_static_allowed']}")
        lines.append("- Allowed sources:")
        for source in item["allowed_sources"]:
            lines.append(f"  - {source}")
        lines.append("")
    lines.append("## Blocking Rows")
    blocking = [row for row in rows if row["website_blocking"]]
    if not blocking:
        lines.append("- None found.")
    else:
        for row in blocking:
            lines.append(f"- {row['file']}:{row['line']} - {row['target']} - {row['classification']} - {row['reason']}")
    lines.append("")
    lines.append("## All Legacy Reference Rows")
    if not rows:
        lines.append("- None found.")
    else:
        for row in rows:
            lines.append(f"- {row['file']}:{row['line']} - {row['target']} - {row['classification']} - blocking={row['website_blocking']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_compile(root: Path) -> tuple[bool, str]:
    cmd = [sys.executable, "-m", "py_compile", "app/web.py", "app/operational/operator_surface.py"]
    result = subprocess.run(cmd, cwd=root, text=True, capture_output=True)
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--fail-on-blocking", action="store_true")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    if not root.exists():
        raise SystemExit(f"Project root not found: {root}")

    refs = scan_legacy_refs(root)
    by_class: dict[str, int] = {}
    for row in refs:
        by_class[row["classification"]] = by_class.get(row["classification"], 0) + 1
    blocking_rows = [row for row in refs if row["website_blocking"]]
    compile_ok, compile_output = run_compile(root)

    status = "PASS" if compile_ok and not blocking_rows else "REVIEW"
    payload = {
        "schema": "jom-backend-legacy-runtime-input-final-truth-chain-audit-v1",
        "generated_at_utc": now_utc(),
        "overall_status": status,
        "plain_rule": "If it is not live/current or auto-refreshed, it must not feed the website.",
        "summary": {
            "legacy_reference_rows": len(refs),
            "website_blocking_rows": len(blocking_rows),
            "by_classification": by_class,
            "compile_ok": compile_ok,
            "compile_output": compile_output,
        },
        "endpoint_truth_map": endpoint_truth_map(),
        "legacy_references": refs,
        "next_actions": [
            "Replace every REPLACE_REQUIRED_WEBSITE_RISK row with a live endpoint or auto-refreshed generated output.",
            "Keep INTERNAL_REFRESH_INPUT_REVIEW rows only if they are part of an automatic refresh chain and never exposed directly as website truth.",
            "Remove snapshot controller outputs from website-facing paths if any remain.",
            "After all blocking rows are zero, delete unused legacy files if no builder/runtime chain still needs them.",
        ],
    }

    report_dir = root / "reports" / "backend_legacy_runtime_input_final_truth_chain_audit_v1"
    write_json(report_dir / "BACKEND_LEGACY_RUNTIME_INPUT_FINAL_TRUTH_CHAIN_AUDIT_V1.json", payload)
    write_markdown(report_dir / "BACKEND_LEGACY_RUNTIME_INPUT_FINAL_TRUTH_CHAIN_AUDIT_V1.md", payload)
    write_json(root / "static" / "data" / "backend_final_truth_chain_status.json", {
        "schema": "jom-backend-final-truth-chain-status-v1",
        "generated_at_utc": payload["generated_at_utc"],
        "overall_status": status,
        "website_truth_rule": payload["plain_rule"],
        "legacy_reference_rows": len(refs),
        "website_blocking_rows": len(blocking_rows),
        "compile_ok": compile_ok,
    })

    print(f"Overall status: {status}")
    print(f"Legacy reference rows: {len(refs)}")
    print(f"Website-blocking rows: {len(blocking_rows)}")
    print(f"Report: {report_dir / 'BACKEND_LEGACY_RUNTIME_INPUT_FINAL_TRUTH_CHAIN_AUDIT_V1.md'}")
    if compile_output:
        print(compile_output)
    if args.fail_on_blocking and blocking_rows:
        return 2
    return 0 if compile_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
