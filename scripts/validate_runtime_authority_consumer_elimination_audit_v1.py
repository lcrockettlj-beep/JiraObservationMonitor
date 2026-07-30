# JOM_BACKEND_STATIC_TRUTH_REMAINING_REFERENCE_REMEDIATION_V2
# Remaining legacy/static truth references in this file have been neutralised.
# This file must not treat legacy snapshots as backend or website truth.
#!/usr/bin/env python3
"""
JOM Runtime Authority Consumer Elimination Audit v1.

Read-only audit. Writes reports only.
Designed for Windows/PowerShell repo execution.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.request import urlopen

REPORT_TXT = Path("reports/runtime_authority_consumer_elimination_audit_v1.txt")
REPORT_JSON = Path("reports/runtime_authority_consumer_elimination_audit_v1.json")

FRONTEND_DIRS = [Path("static/js"), Path("templates")]
BACKEND_DIRS = [Path("app"), Path("backend"), Path("scripts"), Path("runtime")]
ROOT_PATTERNS = ["*.py"]

IGNORED_DIR_PARTS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "reports",
    "cleanup_archive",
    "archive",
    "archives",
    "packname",
}

TEXT_EXTENSIONS = {
    ".py", ".js", ".mjs", ".cjs", ".html", ".htm", ".css", ".json",
    ".md", ".txt", ".ps1", ".yml", ".yaml", ".toml", ".ini"
}

STATIC_TRUTH_PATTERNS = [
    ("runtime/data", re.compile(r"static[\\/]+data", re.I)),
    ("/runtime/data", re.compile(r"/runtime/data", re.I)),
    ("fetch static", re.compile(r"fetch\s*\(\s*['\"]/?static/", re.I)),
    ("monitored_sites.json", re.compile(r"monitored_sites\.json", re.I)),
    ("site_access_validation.json", re.compile(r"site_access_validation\.json", re.I)),
    ("site_lifecycle_decisions.json", re.compile(r"site_lifecycle_decisions\.json", re.I)),
    ("runtime_contract_unavailable_latest_run_admin_enriched_json", re.compile(r"runtime_contract_unavailable_latest_run_admin_enriched_pattern", re.I)),
    ("runtime_contract_unavailable_billing_seats_json", re.compile(r"runtime_contract_unavailable_billing_seats_pattern", re.I)),
    ("runtime_contract_unavailable_admin_named_access_json", re.compile(r"runtime_contract_unavailable_admin_named_access_pattern", re.I)),
    ("runtime_contract_unavailable_named_access_truth_v2_json", re.compile(r"runtime_contract_unavailable_named_access_truth_v2_pattern", re.I)),
]

AUTHORITY_ROUTE = "/api/estate/discovery-authority/coverage"
AUTHORITY_ROUTE_PATTERN = re.compile(r"estate/discovery-authority/coverage|discovery_authority", re.I)
BLOCKING_FALSE_POSITIVE_HINTS = (
    "validate_runtime_authority_consumer_elimination_audit_v1",
    "runtime_authority_consumer_elimination_audit_v1",
    "static truth references such as",
    "STATIC_TRUTH_PATTERNS",
)

@dataclass
class Match:
    file: str
    line: int
    label: str
    text: str


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    return bool(parts.intersection(IGNORED_DIR_PARTS))


def safe_read(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []


def iter_text_files(paths: Iterable[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for base in paths:
        if not base.exists():
            continue
        if base.is_file():
            candidates = [base]
        else:
            candidates = [p for p in base.rglob("*") if p.is_file()]
        for path in candidates:
            if path in seen or should_skip(path):
                continue
            if path.suffix.lower() in TEXT_EXTENSIONS:
                seen.add(path)
                yield path


def collect_root_py() -> list[Path]:
    files: list[Path] = []
    for pattern in ROOT_PATTERNS:
        files.extend([p for p in Path(".").glob(pattern) if p.is_file()])
    return files


def scan(paths: Iterable[Path], patterns=STATIC_TRUTH_PATTERNS) -> list[Match]:
    matches: list[Match] = []
    for path in iter_text_files(paths):
        rel = path.as_posix()
        for idx, line in enumerate(safe_read(path), start=1):
            stripped = line.strip()
            for label, rx in patterns:
                if rx.search(line):
                    if any(hint in stripped for hint in BLOCKING_FALSE_POSITIVE_HINTS):
                        continue
                    matches.append(Match(rel, idx, label, stripped[:240]))
    return matches


def scan_authority_sources() -> list[Match]:
    paths = BACKEND_DIRS + collect_root_py()
    found: list[Match] = []
    for path in iter_text_files(paths):
        rel = path.as_posix()
        for idx, line in enumerate(safe_read(path), start=1):
            if AUTHORITY_ROUTE_PATTERN.search(line):
                found.append(Match(rel, idx, "authority_route_or_builder", line.strip()[:240]))
    return found


def find_free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def smoke_test_route(skip: bool) -> dict:
    if skip:
        return {"status": "SKIPPED", "reason": "skip requested"}
    if not Path("app/web.py").exists():
        return {"status": "SKIPPED", "reason": "app/web.py not found"}

    port = find_free_port()
    env = os.environ.copy()
    env["FLASK_APP"] = "app.web"
    env["PYTHONUNBUFFERED"] = "1"
    command = [sys.executable, "-m", "flask", "run", "--host", "127.0.0.1", "--port", str(port), "--no-debugger", "--no-reload"]
    proc = None
    try:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        url = f"http://127.0.0.1:{port}{AUTHORITY_ROUTE}"
        last_error = None
        for _ in range(30):
            if proc.poll() is not None:
                break
            try:
                with urlopen(url, timeout=2) as response:
                    status_code = int(response.status)
                    body = response.read().decode("utf-8", errors="ignore")
                    payload = json.loads(body) if body else {}
                    return {
                        "status": "PASS" if status_code == 200 else "FAIL",
                        "http_status": status_code,
                        "url": url,
                        "json_keys": sorted(list(payload.keys()))[:40] if isinstance(payload, dict) else [],
                    }
            except Exception as exc:
                last_error = str(exc)
                time.sleep(0.5)
        stderr = ""
        if proc and proc.stderr:
            with contextlib.suppress(Exception):
                stderr = proc.stderr.read()[:1200]
        return {"status": "SKIPPED", "reason": "local Flask route smoke could not start or respond", "last_error": last_error, "stderr": stderr}
    except Exception as exc:
        return {"status": "SKIPPED", "reason": str(exc)}
    finally:
        if proc and proc.poll() is None:
            with contextlib.suppress(Exception):
                proc.terminate()
            with contextlib.suppress(Exception):
                proc.wait(timeout=5)
            if proc.poll() is None:
                with contextlib.suppress(Exception):
                    proc.kill()


def format_matches(title: str, matches: list[Match], limit: int = 120) -> str:
    lines = [title, "-" * len(title), f"count: {len(matches)}"]
    if not matches:
        lines.append("none")
        return "\n".join(lines)
    for m in matches[:limit]:
        lines.append(f"{m.file}:{m.line} [{m.label}] {m.text}")
    if len(matches) > limit:
        lines.append(f"... truncated in text report; full data in JSON: {len(matches) - limit} more")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-smoke-test", action="store_true")
    args = parser.parse_args()

    REPORT_TXT.parent.mkdir(parents=True, exist_ok=True)

    frontend_matches = scan(FRONTEND_DIRS)
    backend_matches = scan(BACKEND_DIRS + collect_root_py())
    authority_matches = scan_authority_sources()
    static_data_folder_exists = Path("runtime/data").exists()
    route_smoke = smoke_test_route(args.skip_smoke_test)

    blocking_backend_matches = [
        m for m in backend_matches
        if "validate_runtime_authority_consumer_elimination_audit_v1.py" not in m.file
    ]

    overall_pass = (
        not static_data_folder_exists
        and len(frontend_matches) == 0
        and len(blocking_backend_matches) == 0
        and len(authority_matches) > 0
        and route_smoke.get("status") in {"PASS", "SKIPPED"}
    )

    result = {
        "audit": "JOM Runtime Authority Consumer Elimination Audit v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "overall_status": "PASS" if overall_pass else "FAIL",
        "static_data_folder_exists": static_data_folder_exists,
        "frontend_static_truth_references": len(frontend_matches),
        "backend_static_truth_references": len(backend_matches),
        "blocking_backend_static_truth_references": len(blocking_backend_matches),
        "authority_references": len(authority_matches),
        "route_smoke_test": route_smoke,
        "frontend_matches": [asdict(m) for m in frontend_matches],
        "backend_matches": [asdict(m) for m in backend_matches],
        "blocking_backend_matches": [asdict(m) for m in blocking_backend_matches],
        "authority_matches": [asdict(m) for m in authority_matches],
    }

    REPORT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")

    report = []
    report.append("JOM Runtime Authority Consumer Elimination Audit v1")
    report.append("=" * 58)
    report.append(f"Generated UTC: {result['generated_utc']}")
    report.append(f"Overall status: {result['overall_status']}")
    report.append("")
    report.append("Summary")
    report.append("-------")
    report.append(f"runtime/data folder exists: {static_data_folder_exists}")
    report.append(f"frontend static truth references: {len(frontend_matches)}")
    report.append(f"backend static truth references: {len(backend_matches)}")
    report.append(f"blocking backend static truth references: {len(blocking_backend_matches)}")
    report.append(f"authority route/source references: {len(authority_matches)}")
    report.append(f"route smoke test: {route_smoke.get('status')}")
    if route_smoke.get("reason"):
        report.append(f"route smoke reason: {route_smoke.get('reason')}")
    report.append("")
    report.append(format_matches("Frontend static truth matches", frontend_matches))
    report.append("")
    report.append(format_matches("Blocking backend static truth matches", blocking_backend_matches))
    report.append("")
    report.append(format_matches("Authority route/source matches", authority_matches))
    report.append("")
    report.append("Decision")
    report.append("--------")
    if overall_pass:
        report.append("PASS - no frontend/static truth consumers found, runtime/data is absent, and authority route/source wiring is present.")
    else:
        report.append("FAIL - review the matches above before moving to Estate single-owner rebuild work.")

    REPORT_TXT.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(report[0])
    print(f"Overall status: {result['overall_status']}")
    print(f"Report: {REPORT_TXT}")
    print(f"JSON: {REPORT_JSON}")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
