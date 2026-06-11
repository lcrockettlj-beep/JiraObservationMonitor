import csv
import json
import os
from datetime import datetime


REPORT_DIR = "reports"

LATEST_SUMMARY_JSON = os.path.join(REPORT_DIR, "latest_summary.json")
LATEST_SUMMARY_TXT = os.path.join(REPORT_DIR, "latest_summary.txt")
LATEST_SUMMARY_MD = os.path.join(REPORT_DIR, "latest_summary.md")

LATEST_SITES_CSV = os.path.join(REPORT_DIR, "latest_sites.csv")
LATEST_CHANGES_CSV = os.path.join(REPORT_DIR, "latest_changes.csv")
LATEST_PERMISSION_CHECKER_CSV = os.path.join(REPORT_DIR, "latest_permission_checker.csv")
LATEST_PERMISSION_ISSUES_CSV = os.path.join(REPORT_DIR, "latest_permission_issues.csv")
LATEST_EXCLUDED_SITES_CSV = os.path.join(REPORT_DIR, "latest_excluded_sites.csv")


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


def _extract_permission_overview(sites):
    checked_sites = 0
    available_sites = 0
    administer_true = 0
    administer_projects_true = 0
    browse_projects_true = 0

    for site in sites:
        checker = site.get("permission_checker", {}) or {}

        if checker:
            checked_sites += 1

        if checker.get("available"):
            available_sites += 1

        if checker.get("has_administer_jira") is True:
            administer_true += 1

        if checker.get("has_administer_projects") is True:
            administer_projects_true += 1

        if checker.get("has_browse_projects") is True:
            browse_projects_true += 1

    return {
        "checked_sites": checked_sites,
        "available_sites": available_sites,
        "administer_true": administer_true,
        "administer_projects_true": administer_projects_true,
        "browse_projects_true": browse_projects_true
    }


def _extract_permission_issue_rows(sites):
    rows = []

    for site in sites:
        endpoint_summary = site.get("endpoint_summary", {}) or {}
        permission_issue_urls = endpoint_summary.get("permission_issue_urls", []) or []

        mypermissions_url = None
        cloud_id = site.get("cloud_id")
        if cloud_id:
            mypermissions_url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/mypermissions"

        for issue in permission_issue_urls:
            rows.append({
                "site_name": site.get("name"),
                "site_url": site.get("url"),
                "cloud_id": cloud_id,
                "mypermissions_url": mypermissions_url,
                "endpoint_key": issue.get("endpoint_key"),
                "related_endpoint_url": issue.get("url"),
                "status_code": issue.get("status_code"),
                "error_category": issue.get("error_category")
            })

    return rows


def build_export_summary(output):
    summary = output.get("summary", {}) or {}
    risk_summary = output.get("risk_summary", {}) or {}
    raw_collection_summary = output.get("raw_collection_summary", {}) or {}
    comparison = output.get("comparison", {}) or {}
    snapshot_files = output.get("snapshot_files", {}) or {}
    historical_trends = output.get("historical_trends", {}) or {}
    sites = output.get("sites", []) or []

    excluded_sites = raw_collection_summary.get("excluded_sites", []) or []
    change_counts = _normalise_change_counts(comparison)
    permission_overview = _extract_permission_overview(sites)
    permission_issue_rows = _extract_permission_issue_rows(sites)

    top_risky_sites = []
    for site in sites[:5]:
        top_risky_sites.append({
            "name": site.get("name"),
            "status": site.get("status"),
            "risk_score": site.get("risk_score", 0),
            "project_count": site.get("project_count", 0),
            "issue_count_total": site.get("issue_count_total", 0),
            "issue_count_unresolved": site.get("issue_count_unresolved", 0),
            "issue_count_updated_last_7d": site.get("issue_count_updated_last_7d", 0),
            "permission_limited_checks": site.get("permission_limited_checks", []),
            "status_reasons": site.get("status_reasons", []),
            "permission_checker": site.get("permission_checker", {})
        })

    return {
        "generated_at_local": datetime.now().isoformat(),
        "summary": summary,
        "risk_summary": risk_summary,
        "raw_collection_summary": raw_collection_summary,
        "change_counts": change_counts,
        "historical_trend_summary": historical_trends.get("summary", {}),
        "permission_overview": permission_overview,
        "permission_issue_count": len(permission_issue_rows),
        "permission_issues": permission_issue_rows,
        "excluded_sites": excluded_sites,
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
    lines.append(f"Core blocking             : {endpoint_totals.get('core_blocking_failed_checks', 0)}")
    lines.append(f"Enrichment failed         : {endpoint_totals.get('enrichment_failed_checks', 0)}")
    lines.append("")

    excluded_sites = export_summary.get("excluded_sites", []) or []
    lines.append("EXCLUDED SITES")
    lines.append("-" * 72)
    if not excluded_sites:
        lines.append("No excluded sites.")
    else:
        for site in excluded_sites:
            lines.append(f"- {site.get('name')} | {site.get('url')} | cloud_id={site.get('cloud_id')}")
    lines.append("")

    permission_overview = export_summary.get("permission_overview", {}) or {}
    lines.append("PERMISSION OVERVIEW")
    lines.append("-" * 72)
    lines.append(f"Checked sites              : {permission_overview.get('checked_sites', 0)}")
    lines.append(f"Permission data available  : {permission_overview.get('available_sites', 0)}")
    lines.append(f"Has ADMINISTER            : {permission_overview.get('administer_true', 0)}")
    lines.append(f"Has ADMINISTER_PROJECTS   : {permission_overview.get('administer_projects_true', 0)}")
    lines.append(f"Has BROWSE_PROJECTS       : {permission_overview.get('browse_projects_true', 0)}")
    lines.append(f"Permission issue count     : {export_summary.get('permission_issue_count', 0)}")
    lines.append("")

    permission_issues = export_summary.get("permission_issues", []) or []
    lines.append("PERMISSION ISSUES")
    lines.append("-" * 72)
    if not permission_issues:
        lines.append("No permission issues.")
    else:
        for issue in permission_issues:
            lines.append(f"- Site                     : {issue.get('site_name')}")
            lines.append(f"  My permissions URL       : {issue.get('mypermissions_url')}")
            lines.append(f"  Related endpoint         : {issue.get('endpoint_key')}")
            lines.append(f"  Related endpoint URL     : {issue.get('related_endpoint_url')}")
            lines.append(f"  Status code              : {issue.get('status_code')}")
            lines.append(f"  Error category           : {issue.get('error_category')}")
            lines.append("")
    lines.append("")

    historical_summary = export_summary.get("historical_trend_summary", {}) or {}
    lines.append("HISTORICAL TREND SUMMARY")
    lines.append("-" * 72)
    lines.append(f"Sites in history           : {historical_summary.get('site_count', 0)}")
    lines.append(f"Warning/Critical streaks   : {historical_summary.get('warning_or_critical_streak_sites', 0)}")
    lines.append(f"Rising unresolved sites    : {historical_summary.get('rising_unresolved_sites', 0)}")
    lines.append(f"Rising risk sites          : {historical_summary.get('rising_risk_sites', 0)}")
    lines.append(f"Recurring blocking sites   : {historical_summary.get('recurring_blocking_failure_sites', 0)}")
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
            lines.append(f"   Updated last 7 days     : {site.get('issue_count_updated_last_7d', 0)}")

            perm = site.get("permission_limited_checks", []) or []
            if perm:
                lines.append(f"   Permission limited      : {', '.join(str(v) for v in perm)}")

            checker = site.get("permission_checker", {}) or {}
            if checker:
                lines.append(f"   Has ADMINISTER          : {checker.get('has_administer_jira')}")
                lines.append(f"   Has ADMINISTER_PROJECTS : {checker.get('has_administer_projects')}")
                lines.append(f"   Has BROWSE_PROJECTS     : {checker.get('has_browse_projects')}")

            reasons = site.get("status_reasons", []) or []
            if reasons:
                lines.append(f"   Reasons                 : {', '.join(str(r) for r in reasons)}")

            lines.append("")

    return "\n".join(lines)


def _build_markdown_report(export_summary):
    summary = export_summary.get("summary", {}) or {}
    risk_summary = export_summary.get("risk_summary", {}) or {}
    raw_summary = export_summary.get("raw_collection_summary", {}) or {}
    endpoint_totals = raw_summary.get("endpoint_totals", {}) or {}
    historical_summary = export_summary.get("historical_trend_summary", {}) or {}
    top_risky_sites = export_summary.get("top_risky_sites", []) or []
    excluded_sites = export_summary.get("excluded_sites", []) or []
    permission_overview = export_summary.get("permission_overview", {}) or {}
    permission_issues = export_summary.get("permission_issues", []) or []

    lines = []
    lines.append("# Jira Observation Monitor Summary")
    lines.append("")
    lines.append(f"- **Generated:** {export_summary.get('generated_at_local')}")
    lines.append(f"- **Sites total:** {summary.get('site_count', 0)}")
    lines.append(f"- **Healthy / Warning / Critical:** {summary.get('healthy_count', 0)} / {summary.get('warning_count', 0)} / {summary.get('critical_count', 0)}")
    lines.append(f"- **Total risk score:** {risk_summary.get('total_risk_score', 0)}")
    lines.append(f"- **Average risk score:** {risk_summary.get('average_risk_score', 0)}")
    lines.append(f"- **Collection duration (sec):** {raw_summary.get('collection_duration_seconds', 0)}")
    lines.append(f"- **Endpoint checks passed / failed:** {endpoint_totals.get('successful_checks', 0)} / {endpoint_totals.get('failed_checks', 0)}")
    lines.append(f"- **Permission-limited endpoints:** {endpoint_totals.get('permission_limited_checks', 0)}")
    lines.append("")
    lines.append("## Excluded sites")
    lines.append("")
    if not excluded_sites:
        lines.append("- No excluded sites.")
    else:
        for site in excluded_sites:
            lines.append(f"- **{site.get('name')}** — {site.get('url')} (cloud_id={site.get('cloud_id')})")
    lines.append("")
    lines.append("## Permission overview")
    lines.append("")
    lines.append(f"- Checked sites: {permission_overview.get('checked_sites', 0)}")
    lines.append(f"- Permission data available: {permission_overview.get('available_sites', 0)}")
    lines.append(f"- Has ADMINISTER: {permission_overview.get('administer_true', 0)}")
    lines.append(f"- Has ADMINISTER_PROJECTS: {permission_overview.get('administer_projects_true', 0)}")
    lines.append(f"- Has BROWSE_PROJECTS: {permission_overview.get('browse_projects_true', 0)}")
    lines.append(f"- Permission issue count: {export_summary.get('permission_issue_count', 0)}")
    lines.append("")
    lines.append("## Permission issues")
    lines.append("")
    if not permission_issues:
        lines.append("- No permission issues.")
    else:
        for issue in permission_issues:
            lines.append(f"### {issue.get('site_name')}")
            lines.append(f"- My permissions URL: {issue.get('mypermissions_url')}")
            lines.append(f"- Related endpoint: {issue.get('endpoint_key')}")
            lines.append(f"- Related endpoint URL: {issue.get('related_endpoint_url')}")
            lines.append(f"- Status code: {issue.get('status_code')}")
            lines.append(f"- Error category: {issue.get('error_category')}")
            lines.append("")
    lines.append("## Historical trend summary")
    lines.append("")
    lines.append(f"- Sites in history: {historical_summary.get('site_count', 0)}")
    lines.append(f"- Warning/Critical streaks: {historical_summary.get('warning_or_critical_streak_sites', 0)}")
    lines.append(f"- Rising unresolved sites: {historical_summary.get('rising_unresolved_sites', 0)}")
    lines.append(f"- Rising risk sites: {historical_summary.get('rising_risk_sites', 0)}")
    lines.append("")
    lines.append("## Top risky sites")
    lines.append("")

    if not top_risky_sites:
        lines.append("- No site data available.")
    else:
        for site in top_risky_sites:
            lines.append(f"### {site.get('name')}")
            lines.append(f"- Status: {site.get('status')}")
            lines.append(f"- Risk score: {site.get('risk_score', 0)}")
            lines.append(f"- Projects: {site.get('project_count', 0)}")
            lines.append(f"- Total issues: {site.get('issue_count_total', 0)}")
            lines.append(f"- Unresolved issues: {site.get('issue_count_unresolved', 0)}")
            lines.append(f"- Updated last 7 days: {site.get('issue_count_updated_last_7d', 0)}")

            checker = site.get("permission_checker", {}) or {}
            if checker:
                lines.append(f"- Has ADMINISTER: {checker.get('has_administer_jira')}")
                lines.append(f"- Has ADMINISTER_PROJECTS: {checker.get('has_administer_projects')}")
                lines.append(f"- Has BROWSE_PROJECTS: {checker.get('has_browse_projects')}")

            perm = site.get("permission_limited_checks", []) or []
            if perm:
                lines.append(f"- Permission limited: {', '.join(str(v) for v in perm)}")

            reasons = site.get("status_reasons", []) or []
            if reasons:
                lines.append(f"- Reasons: {', '.join(str(v) for v in reasons)}")

            lines.append("")

    return "\n".join(lines)


def _save_sites_csv(output, path):
    sites = output.get("sites", []) or []

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "name",
            "status",
            "risk_score",
            "project_count",
            "application_role_count",
            "issue_count_total",
            "issue_count_unresolved",
            "issue_count_updated_last_7d",
            "collection_duration_seconds",
            "permission_limited_checks",
            "has_administer_jira",
            "has_administer_projects",
            "has_browse_projects",
            "status_reasons"
        ])

        for site in sites:
            checker = site.get("permission_checker", {}) or {}

            writer.writerow([
                site.get("name"),
                site.get("status"),
                site.get("risk_score", 0),
                site.get("project_count", 0),
                site.get("application_role_count", 0),
                site.get("issue_count_total", 0),
                site.get("issue_count_unresolved", 0),
                site.get("issue_count_updated_last_7d", 0),
                site.get("collection_duration_seconds", 0),
                ", ".join(site.get("permission_limited_checks", []) or []),
                checker.get("has_administer_jira"),
                checker.get("has_administer_projects"),
                checker.get("has_browse_projects"),
                ", ".join(site.get("status_reasons", []) or [])
            ])


def _save_changes_csv(output, path):
    comparison = output.get("comparison", {}) or {}
    changes = comparison.get("changes", []) or []

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "severity",
            "type",
            "site_name",
            "cloud_id",
            "field",
            "old",
            "new"
        ])

        for change in changes:
            writer.writerow([
                change.get("severity"),
                change.get("type"),
                change.get("site_name"),
                change.get("cloud_id"),
                change.get("field"),
                change.get("old"),
                change.get("new")
            ])


def _save_permission_checker_csv(output, path):
    sites = output.get("sites", []) or []

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "site_name",
            "site_url",
            "cloud_id",
            "mypermissions_url",
            "permission_data_available",
            "has_administer_jira",
            "has_administer_projects",
            "has_browse_projects"
        ])

        for site in sites:
            checker = site.get("permission_checker", {}) or {}
            cloud_id = site.get("cloud_id")
            mypermissions_url = (
                f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/mypermissions"
                if cloud_id else None
            )

            writer.writerow([
                site.get("name"),
                site.get("url"),
                cloud_id,
                mypermissions_url,
                checker.get("available"),
                checker.get("has_administer_jira"),
                checker.get("has_administer_projects"),
                checker.get("has_browse_projects")
            ])


def _save_permission_issues_csv(output, path):
    sites = output.get("sites", []) or []

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "site_name",
            "site_url",
            "cloud_id",
            "mypermissions_url",
            "endpoint_key",
            "related_endpoint_url",
            "status_code",
            "error_category"
        ])

        for site in sites:
            endpoint_summary = site.get("endpoint_summary", {}) or {}
            permission_issue_urls = endpoint_summary.get("permission_issue_urls", []) or []
            cloud_id = site.get("cloud_id")
            mypermissions_url = (
                f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/mypermissions"
                if cloud_id else None
            )

            for item in permission_issue_urls:
                writer.writerow([
                    site.get("name"),
                    site.get("url"),
                    cloud_id,
                    mypermissions_url,
                    item.get("endpoint_key"),
                    item.get("url"),
                    item.get("status_code"),
                    item.get("error_category")
                ])


def _save_excluded_sites_csv(output, path):
    raw_summary = output.get("raw_collection_summary", {}) or {}
    excluded_sites = raw_summary.get("excluded_sites", []) or []

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "name",
            "site_url",
            "cloud_id"
        ])

        for site in excluded_sites:
            writer.writerow([
                site.get("name"),
                site.get("url"),
                site.get("cloud_id")
            ])


def save_reports(output):
    ensure_report_dir()

    export_summary = build_export_summary(output)
    timestamp_info = _timestamp_strings()

    date_folder = os.path.join(REPORT_DIR, timestamp_info["date_folder"])
    os.makedirs(date_folder, exist_ok=True)

    timestamp_json = os.path.join(date_folder, f"summary_{timestamp_info['timestamp']}.json")
    timestamp_txt = os.path.join(date_folder, f"summary_{timestamp_info['timestamp']}.txt")
    timestamp_md = os.path.join(date_folder, f"summary_{timestamp_info['timestamp']}.md")
    timestamp_sites_csv = os.path.join(date_folder, f"sites_{timestamp_info['timestamp']}.csv")
    timestamp_changes_csv = os.path.join(date_folder, f"changes_{timestamp_info['timestamp']}.csv")
    timestamp_permission_checker_csv = os.path.join(date_folder, f"permission_checker_{timestamp_info['timestamp']}.csv")
    timestamp_permission_issues_csv = os.path.join(date_folder, f"permission_issues_{timestamp_info['timestamp']}.csv")
    timestamp_excluded_sites_csv = os.path.join(date_folder, f"excluded_sites_{timestamp_info['timestamp']}.csv")

    with open(LATEST_SUMMARY_JSON, "w", encoding="utf-8") as handle:
        json.dump(export_summary, handle, indent=2)

    with open(timestamp_json, "w", encoding="utf-8") as handle:
        json.dump(export_summary, handle, indent=2)

    text_report = _build_text_report(export_summary)
    markdown_report = _build_markdown_report(export_summary)

    with open(LATEST_SUMMARY_TXT, "w", encoding="utf-8") as handle:
        handle.write(text_report)

    with open(timestamp_txt, "w", encoding="utf-8") as handle:
        handle.write(text_report)

    with open(LATEST_SUMMARY_MD, "w", encoding="utf-8") as handle:
        handle.write(markdown_report)

    with open(timestamp_md, "w", encoding="utf-8") as handle:
        handle.write(markdown_report)

    _save_sites_csv(output, LATEST_SITES_CSV)
    _save_sites_csv(output, timestamp_sites_csv)

    _save_changes_csv(output, LATEST_CHANGES_CSV)
    _save_changes_csv(output, timestamp_changes_csv)

    _save_permission_checker_csv(output, LATEST_PERMISSION_CHECKER_CSV)
    _save_permission_checker_csv(output, timestamp_permission_checker_csv)

    _save_permission_issues_csv(output, LATEST_PERMISSION_ISSUES_CSV)
    _save_permission_issues_csv(output, timestamp_permission_issues_csv)

    _save_excluded_sites_csv(output, LATEST_EXCLUDED_SITES_CSV)
    _save_excluded_sites_csv(output, timestamp_excluded_sites_csv)

    return {
        "latest_summary_json": LATEST_SUMMARY_JSON,
        "latest_summary_txt": LATEST_SUMMARY_TXT,
        "latest_summary_md": LATEST_SUMMARY_MD,
        "latest_sites_csv": LATEST_SITES_CSV,
        "latest_changes_csv": LATEST_CHANGES_CSV,
        "latest_permission_checker_csv": LATEST_PERMISSION_CHECKER_CSV,
        "latest_permission_issues_csv": LATEST_PERMISSION_ISSUES_CSV,
        "latest_excluded_sites_csv": LATEST_EXCLUDED_SITES_CSV,
        "timestamp_summary_json": timestamp_json,
        "timestamp_summary_txt": timestamp_txt,
        "timestamp_summary_md": timestamp_md,
        "timestamp_sites_csv": timestamp_sites_csv,
        "timestamp_changes_csv": timestamp_changes_csv,
        "timestamp_permission_checker_csv": timestamp_permission_checker_csv,
        "timestamp_permission_issues_csv": timestamp_permission_issues_csv,
        "timestamp_excluded_sites_csv": timestamp_excluded_sites_csv
    }