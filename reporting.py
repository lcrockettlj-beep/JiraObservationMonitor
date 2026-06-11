import json
import os
from datetime import datetime


REPORT_DIR = "reports"
LATEST_SUMMARY_JSON = os.path.join(REPORT_DIR, "latest_summary.json")
LATEST_SUMMARY_TXT = os.path.join(REPORT_DIR, "latest_summary.txt")


def ensure_report_dir():
    os.makedirs(REPORT_DIR, exist_ok=True)


def _timestamp_strings():
    now = datetime.now()
    return {
        "timestamp": now.strftime("%Y-%m-%d_%H-%M-%S"),
        "date_folder": now.strftime("%Y-%m-%d"),
        "local_time": now.isoformat()
    }


def _normalise_change_counts(comparison):
    changes = comparison.get("changes", []) or []

    info_count = 0
    warning_count = 0
    critical_count = 0

    for change in changes:
        severity = (change.get("severity") or "info").lower()

        if severity == "critical":
            critical_count += 1
        elif severity == "warning":
            warning_count += 1
        else:
            info_count += 1

    return {
        "info": info_count,
        "warning": warning_count,
        "critical": critical_count,
        "total": len(changes)
    }


def build_export_summary(output):
    summary = output.get("summary", {}) or {}
    risk_summary = output.get("risk_summary", {}) or {}
    raw_collection_summary = output.get("raw_collection_summary", {}) or {}
    comparison = output.get("comparison", {}) or {}
    snapshot_files = output.get("snapshot_files", {}) or {}
    sites = output.get("sites", []) or []

    change_counts = _normalise_change_counts(comparison)

    top_risky_sites = []
    for site in sites[:5]:
        top_risky_sites.append({
            "name": site.get("name"),
            "status": site.get("status"),
            "risk_score": site.get("risk_score", 0),
            "project_count": site.get("project_count", 0),
            "issue_count_total": site.get("issue_count_total", 0),
            "issue_count_unresolved": site.get("issue_count_unresolved", 0),
            "status_reasons": site.get("status_reasons", [])
        })

    return {
        "generated_at_local": datetime.now().isoformat(),
        "summary": summary,
        "risk_summary": risk_summary,
        "raw_collection_summary": raw_collection_summary,
        "change_counts": change_counts,
        "top_risky_sites": top_risky_sites,
        "snapshot_files": snapshot_files
    }


def _build_text_report(export_summary):
    lines = []

    lines.append("Jira Observation Monitor - Summary Report")
    lines.append("=" * 72)
    lines.append(f"Generated at local          : {export_summary.get('generated_at_local')}")
    lines.append("")

    summary = export_summary.get("summary", {}) or {}
    lines.append("STATUS SUMMARY")
    lines.append("-" * 72)
    lines.append(f"Sites total                : {summary.get('site_count', 0)}")
    lines.append(f"Healthy                    : {summary.get('healthy_count', 0)}")
    lines.append(f"Warning                    : {summary.get('warning_count', 0)}")
    lines.append(f"Critical                   : {summary.get('critical_count', 0)}")
    lines.append("")

    risk_summary = export_summary.get("risk_summary", {}) or {}
    lines.append("RISK SUMMARY")
    lines.append("-" * 72)
    lines.append(f"Total risk score           : {risk_summary.get('total_risk_score', 0)}")
    lines.append(f"Average risk score         : {risk_summary.get('average_risk_score', 0)}")
    lines.append(f"Blocking failures          : {risk_summary.get('total_blocking_failures', 0)}")
    lines.append(f"Permission-limited checks  : {risk_summary.get('total_permission_limited_checks', 0)}")
    lines.append("")

    raw_summary = export_summary.get("raw_collection_summary", {}) or {}
    endpoint_totals = raw_summary.get("endpoint_totals", {}) or {}
    lines.append("COLLECTION SUMMARY")
    lines.append("-" * 72)
    lines.append(f"Collected at UTC           : {raw_summary.get('collected_at_utc')}")
    lines.append(f"Collection duration (sec)  : {raw_summary.get('collection_duration_seconds', 0)}")
    lines.append(f"Endpoint checks passed     : {endpoint_totals.get('successful_checks', 0)}")
    lines.append(f"Endpoint checks failed     : {endpoint_totals.get('failed_checks', 0)}")
    lines.append(f"Permission-limited         : {endpoint_totals.get('permission_limited_checks', 0)}")
    lines.append(f"Blocking failed            : {endpoint_totals.get('blocking_failed_checks', 0)}")
    lines.append("")

    change_counts = export_summary.get("change_counts", {}) or {}
    lines.append("CHANGE SUMMARY")
    lines.append("-" * 72)
    lines.append(f"Total changes              : {change_counts.get('total', 0)}")
    lines.append(f"Info changes               : {change_counts.get('info', 0)}")
    lines.append(f"Warning changes            : {change_counts.get('warning', 0)}")
    lines.append(f"Critical changes           : {change_counts.get('critical', 0)}")
    lines.append("")

    top_risky_sites = export_summary.get("top_risky_sites", []) or []
    lines.append("TOP RISKY SITES")
    lines.append("-" * 72)

    if not top_risky_sites:
        lines.append("No site data available.")
    else:
        for index, site in enumerate(top_risky_sites, start=1):
            lines.append(
                f"{index}. {site.get('name')} | status={site.get('status')} | risk={site.get('risk_score', 0)}"
            )
            lines.append(f"   Projects                : {site.get('project_count', 0)}")
            lines.append(f"   Total issues            : {site.get('issue_count_total', 0)}")
            lines.append(f"   Unresolved issues       : {site.get('issue_count_unresolved', 0)}")

            reasons = site.get("status_reasons", []) or []
            if reasons:
                lines.append(f"   Reasons                 : {', '.join(str(r) for r in reasons)}")

            lines.append("")

    snapshot_files = export_summary.get("snapshot_files", {}) or {}
    lines.append("FILES")
    lines.append("-" * 72)
    lines.append(f"Latest snapshot            : {snapshot_files.get('latest_file')}")
    lines.append(f"Timestamp snapshot         : {snapshot_files.get('timestamp_file')}")
    lines.append(f"Snapshot index             : {snapshot_files.get('index_file')}")

    return "\n".join(lines)


def save_reports(output):
    ensure_report_dir()

    export_summary = build_export_summary(output)
    timestamp_info = _timestamp_strings()

    date_folder = os.path.join(REPORT_DIR, timestamp_info["date_folder"])
    os.makedirs(date_folder, exist_ok=True)

    timestamp_json = os.path.join(
        date_folder,
        f"summary_{timestamp_info['timestamp']}.json"
    )
    timestamp_txt = os.path.join(
        date_folder,
        f"summary_{timestamp_info['timestamp']}.txt"
    )

    with open(LATEST_SUMMARY_JSON, "w", encoding="utf-8") as handle:
        json.dump(export_summary, handle, indent=2)

    with open(timestamp_json, "w", encoding="utf-8") as handle:
        json.dump(export_summary, handle, indent=2)

    text_report = _build_text_report(export_summary)

    with open(LATEST_SUMMARY_TXT, "w", encoding="utf-8") as handle:
        handle.write(text_report)

    with open(timestamp_txt, "w", encoding="utf-8") as handle:
        handle.write(text_report)

    return {
        "latest_summary_json": LATEST_SUMMARY_JSON,
        "latest_summary_txt": LATEST_SUMMARY_TXT,
        "timestamp_summary_json": timestamp_json,
        "timestamp_summary_txt": timestamp_txt
    }