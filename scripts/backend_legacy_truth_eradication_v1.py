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
WEBSITE_FACING_PATHS = {
    "app/web.py",
    "app/operational/operator_surface.py",
    "app/reporting/export_reporting.py",
}
POLICY_OR_AUDIT_FILES = {
    "scripts/backend_legacy_runtime_input_final_truth_chain_audit_v1.py",
    "scripts/backend_legacy_truth_eradication_v1.py",
    "scripts/backend_runtime_freshness_snapshot_elimination_v1.py",
    "scripts/audit_source_freshness.py",
}
INTERNAL_RUNTIME_PREFIXES = (
    "app/runtime/",
    "app/builders/",
    "app/registry/",
    "app/access/",
    "app/audits/",
)
POLICY_MARKERS = (
    "LEGACY_NON_WEBSITE_TRUTH_FILES",
    "LEGACY_INPUTS",
    "blocked_legacy_static_input",
    "not website truth",
    "BLOCKED_LEGACY_STATIC_INPUT",
    "legacy_static_allowed",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        return ""


def write_text_if_changed(path: Path, text: str) -> bool:
    before = read_text(path)
    if before != text:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def iter_text_files(root: Path) -> list[Path]:
    rows: list[Path] = []
    for folder in SCAN_DIRS:
        base = root / folder
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                rows.append(path)
    return sorted(rows)


def line_is_policy_context(lines: list[str], index: int) -> bool:
    start = max(0, index - 8)
    end = min(len(lines), index + 9)
    window = "\n".join(lines[start:end])
    return any(marker in window for marker in POLICY_MARKERS)


def classify_reference(path_rel: str, line_text: str, target: str, policy_context: bool) -> tuple[str, str, bool]:
    if policy_context or path_rel in POLICY_OR_AUDIT_FILES:
        return "POLICY_OR_AUDIT_ONLY", "Reference is inside policy/audit code and is not website data usage.", False
    if path_rel in WEBSITE_FACING_PATHS:
        return "REPLACE_REQUIRED_WEBSITE_RISK", "Website-facing code references a legacy/static input and must not feed the website.", True
    if path_rel.startswith(INTERNAL_RUNTIME_PREFIXES):
        return "INTERNAL_REFRESH_INPUT_REVIEW", "Internal runtime/builder reference; allowed only if it feeds an automatic refresh chain and is never exposed directly.", False
    return "REVIEW_UNKNOWN_USAGE", "Reference needs review before it can remain.", True


def scan_legacy_refs(root: Path) -> list[dict[str, Any]]:
    targets = sorted(LEGACY_INPUTS.keys(), key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(item) for item in targets))
    rows: list[dict[str, Any]] = []
    for path in iter_text_files(root):
        text = read_text(path)
        if not text:
            continue
        lines = text.splitlines()
        path_rel = rel(path, root)
        for idx, line in enumerate(lines):
            for match in pattern.finditer(line):
                target = match.group(0)
                classification, reason, blocking = classify_reference(path_rel, line, target, line_is_policy_context(lines, idx))
                rows.append({
                    "file": path_rel,
                    "line": idx + 1,
                    "target": target,
                    "description": LEGACY_INPUTS[target],
                    "classification": classification,
                    "website_blocking": blocking,
                    "reason": reason,
                    "line_text": line.strip()[:260],
                })
    return rows


def patch_export_reporting(root: Path) -> list[str]:
    path = root / "app" / "reporting" / "export_reporting.py"
    actions: list[str] = []
    if not path.exists():
        return ["export_reporting.py not found; skipped"]
    text = read_text(path)
    before = text

    # Remove latest_run fallback from registry export. Static site_registry.json is the generated/runtime contract.
    text = text.replace(
        '"registry": first_dict(read_json(static / "site_registry.json", {}), read_json(root / "latest_run.json", {}).get("site_registry", {})),',
        '"registry": first_dict(read_json(static / "site_registry.json", {})),',
    )

    # Remove latest_run_safe_partial operator summary fallback. Do not expose legacy runtime snapshots through reports.
    text = text.replace(
        '"operator_summary": first_dict(read_json(root / "latest_run_safe_partial.json", {}).get("operator_summary", {})),',
        '"operator_summary": first_dict(read_json(static / "backend_final_truth_chain_status.json", {})),',
    )

    if text != before:
        path.write_text(text, encoding="utf-8")
        actions.append("Removed website/reporting fallbacks to latest_run.json and latest_run_safe_partial.json")
    else:
        actions.append("No exact legacy reporting fallback patterns found or already removed")
    return actions


def patch_final_audit_classifier(root: Path) -> list[str]:
    # Replace old audit script with this improved classifier so future counts do not flag policy/audit references as website risk.
    source = root / "scripts" / "backend_legacy_truth_eradication_v1.py"
    target = root / "scripts" / "backend_legacy_runtime_input_final_truth_chain_audit_v1.py"
    if not source.exists() or not target.exists():
        return ["Final truth chain audit script replacement skipped; source or target missing"]
    text = read_text(source)
    # Make the copied audit status names match the original audit purpose where possible.
    text = text.replace("backend_legacy_truth_eradication_v1.py", "backend_legacy_runtime_input_final_truth_chain_audit_v1.py")
    changed = write_text_if_changed(target, text)
    return ["Updated final truth-chain audit classifier to ignore policy/audit-only legacy references" if changed else "Final truth-chain audit classifier already aligned"]


def run_compile(root: Path, extra: list[str] | None = None) -> tuple[bool, str]:
    files = ["app/web.py", "app/operational/operator_surface.py", "app/reporting/export_reporting.py"]
    if extra:
        files.extend(extra)
    existing = [item for item in files if (root / item).exists()]
    result = subprocess.run([sys.executable, "-m", "py_compile", *existing], cwd=root, text=True, capture_output=True)
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Backend Legacy Truth Eradication v1")
    lines.append("")
    lines.append(f"- Overall status: **{payload['overall_status']}**")
    lines.append(f"- Generated at UTC: {payload['generated_at_utc']}")
    lines.append(f"- Legacy reference rows: {payload['summary']['legacy_reference_rows']}")
    lines.append(f"- Website-blocking rows: {payload['summary']['website_blocking_rows']}")
    lines.append("")
    lines.append("## Rule")
    lines.append("If it is not live/current or auto-refreshed, it must not feed the website.")
    lines.append("")
    lines.append("## Actions")
    for action in payload["actions"]:
        lines.append(f"- {action}")
    lines.append("")
    lines.append("## Classification Summary")
    for key, value in sorted(payload["summary"]["by_classification"].items()):
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Website Blocking Rows")
    blocking = [row for row in payload["legacy_references"] if row["website_blocking"]]
    if not blocking:
        lines.append("- None found.")
    else:
        for row in blocking:
            lines.append(f"- {row['file']}:{row['line']} - {row['target']} - {row['classification']} - {row['reason']}")
    lines.append("")
    lines.append("## Remaining Legacy References")
    for row in payload["legacy_references"]:
        lines.append(f"- {row['file']}:{row['line']} - {row['target']} - {row['classification']} - blocking={row['website_blocking']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(root: Path, actions: list[str]) -> dict[str, Any]:
    refs = scan_legacy_refs(root)
    by_class: dict[str, int] = {}
    for row in refs:
        by_class[row["classification"]] = by_class.get(row["classification"], 0) + 1
    blocking = [row for row in refs if row["website_blocking"]]
    compile_ok, compile_output = run_compile(root, ["scripts/backend_legacy_runtime_input_final_truth_chain_audit_v1.py", "scripts/backend_legacy_truth_eradication_v1.py"])
    status = "PASS" if compile_ok and not blocking else "REVIEW"
    return {
        "schema": "jom-backend-legacy-truth-eradication-v1",
        "generated_at_utc": now_utc(),
        "overall_status": status,
        "plain_rule": "If it is not live/current or auto-refreshed, it must not feed the website.",
        "actions": actions,
        "summary": {
            "legacy_reference_rows": len(refs),
            "website_blocking_rows": len(blocking),
            "by_classification": by_class,
            "compile_ok": compile_ok,
            "compile_output": compile_output,
        },
        "legacy_references": refs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    if not root.exists():
        raise SystemExit(f"Project root not found: {root}")

    actions: list[str] = []
    actions.extend(patch_export_reporting(root))
    # Copy this script into repo if it is not already running from the target path.
    target_self = root / "scripts" / "backend_legacy_truth_eradication_v1.py"
    current = Path(__file__).resolve()
    if current != target_self:
        target_self.parent.mkdir(parents=True, exist_ok=True)
        target_self.write_text(read_text(current), encoding="utf-8")
        actions.append("Installed scripts/backend_legacy_truth_eradication_v1.py")
    actions.extend(patch_final_audit_classifier(root))

    payload = build_payload(root, actions)
    report_dir = root / "reports" / "backend_legacy_truth_eradication_v1"
    write_json(report_dir / "BACKEND_LEGACY_TRUTH_ERADICATION_V1.json", payload)
    write_markdown(report_dir / "BACKEND_LEGACY_TRUTH_ERADICATION_V1.md", payload)
    write_json(root / "static" / "data" / "backend_legacy_truth_eradication_status.json", {
        "schema": "jom-backend-legacy-truth-eradication-status-v1",
        "generated_at_utc": payload["generated_at_utc"],
        "overall_status": payload["overall_status"],
        "website_truth_rule": payload["plain_rule"],
        "legacy_reference_rows": payload["summary"]["legacy_reference_rows"],
        "website_blocking_rows": payload["summary"]["website_blocking_rows"],
        "compile_ok": payload["summary"]["compile_ok"],
    })

    print(f"Overall status: {payload['overall_status']}")
    print(f"Legacy reference rows: {payload['summary']['legacy_reference_rows']}")
    print(f"Website-blocking rows: {payload['summary']['website_blocking_rows']}")
    print(f"Report: {report_dir / 'BACKEND_LEGACY_TRUTH_ERADICATION_V1.md'}")
    compile_output = payload["summary"].get("compile_output")
    if compile_output:
        print(compile_output)
    return 0 if payload["summary"].get("compile_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
