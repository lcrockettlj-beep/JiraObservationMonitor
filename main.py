import json
from datetime import datetime

from auth import (
    get_token_status,
    get_valid_access_token,
    run_interactive_oauth_flow,
    validate_auth_config
)
from data_collector import collect_all_sites
from intelligence import enrich_collection
from monitoring import compare_snapshots
from reporting import save_reports
from snapshots import load_latest_snapshot, save_snapshot


RUN_OUTPUT_FILE = "latest_run.json"


def print_divider(char="=", length=90):
    print(char * length)


def print_heading(title):
    print_divider("=")
    print(title)
    print_divider("=")


def print_section(title):
    print()
    print_divider("-")
    print(title)
    print_divider("-")


def status_icon(status):
    mapping = {
        "healthy": "[OK]",
        "warning": "[!]",
        "critical": "[X]"
    }
    return mapping.get(status, "[?]")


def format_list(values):
    if not values:
        return "None"
    return ", ".join(str(v) for v in values)


def save_run_output(output):
    with open(RUN_OUTPUT_FILE, "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)


def print_auth_status():
    token_status = get_token_status()

    print_section("AUTH STATUS")
    print(f"Token file exists            : {token_status.get('exists')}")
    print(f"Stored token valid           : {token_status.get('valid')}")
    print(f"Has refresh token           : {token_status.get('has_refresh_token')}")
    print(f"Token expires at            : {token_status.get('expires_at')}")


def print_runtime_summary(raw_collection, enriched_collection):
    print_section("RUNTIME SUMMARY")

    print(f"Collected at UTC             : {raw_collection.get('collected_at_utc')}")
    print(f"Collection duration (sec)    : {raw_collection.get('collection_duration_seconds', 0)}")
    print(f"Sites collected              : {raw_collection.get('site_count', 0)}")

    endpoint_totals = raw_collection.get("endpoint_totals", {}) or {}
    print(f"Endpoint checks passed       : {endpoint_totals.get('successful_checks', 0)}")
    print(f"Endpoint checks failed       : {endpoint_totals.get('failed_checks', 0)}")
    print(f"Permission-limited endpoints : {endpoint_totals.get('permission_limited_checks', 0)}")
    print(f"Blocking failed endpoints    : {endpoint_totals.get('blocking_failed_checks', 0)}")

    print(f"Total risk score             : {enriched_collection.get('total_risk_score', 0)}")
    print(f"Average risk score           : {enriched_collection.get('average_risk_score', 0)}")
    print(f"Total issue risk score       : {enriched_collection.get('total_issue_risk_score', 0)}")
    print(f"Total operational risk score : {enriched_collection.get('total_operational_risk_score', 0)}")
    print(f"Total blocking API failures  : {enriched_collection.get('total_blocking_failures', 0)}")
    print(f"Permission-limited checks    : {enriched_collection.get('total_permission_limited_checks', 0)}")


def print_status_summary(enriched_collection):
    print_section("STATUS SUMMARY")

    print(f"Sites total                  : {enriched_collection.get('site_count', 0)}")
    print(f"Healthy                      : {enriched_collection.get('healthy_count', 0)}")
    print(f"Warning                      : {enriched_collection.get('warning_count', 0)}")
    print(f"Critical                     : {enriched_collection.get('critical_count', 0)}")


def print_top_risky_sites(sites, limit=5):
    print_section("TOP RISKY SITES")

    if not sites:
        print("No sites available.")
        return

    sorted_sites = sorted(
        sites,
        key=lambda site: (
            0 if site.get("status") == "critical" else
            1 if site.get("status") == "warning" else
            2,
            -site.get("risk_score", 0),
            site.get("name", "")
        )
    )

    for index, site in enumerate(sorted_sites[:limit], start=1):
        print(
            f"{index}. {status_icon(site.get('status'))} "
            f"{site.get('name')} | status={site.get('status')} | risk={site.get('risk_score', 0)}"
        )
        print(f"    Projects                 : {site.get('project_count', 0)}")
        print(f"    Total issues             : {site.get('issue_count_total', 0)}")
        print(f"    Unresolved issues        : {site.get('issue_count_unresolved', 0)}")
        print(f"    Updated last 7 days      : {site.get('issue_count_updated_last_7d', 0)}")
        print(f"    Site collection (sec)    : {site.get('collection_duration_seconds', 0)}")

        status_reasons = site.get("status_reasons", [])
        issue_signals = site.get("issue_risk_signals", [])
        operational_signals = site.get("operational_risk_signals", [])

        if status_reasons:
            print(f"    Status reasons           : {format_list(status_reasons)}")

        if issue_signals:
            print(f"    Issue risk signals       : {format_list(issue_signals)}")

        if operational_signals:
            print(f"    Operational signals      : {format_list(operational_signals)}")

        print()


def print_site_group(title, sites):
    if not sites:
        return

    print_section(title)

    for site in sites:
        icon = status_icon(site.get("status"))

        print(f"{icon} {site.get('name')}")
        print(f"    Status                   : {site.get('status')}")
        print(f"    Risk score               : {site.get('risk_score', 0)}")
        print(f"    URL                      : {site.get('url')}")
        print(f"    Cloud ID                 : {site.get('cloud_id')}")
        print(f"    Collected at UTC         : {site.get('collected_at_utc')}")
        print(f"    Site collection (sec)    : {site.get('collection_duration_seconds', 0)}")

        print(f"    Projects                 : {site.get('project_count', 0)}")
        print(f"    Application roles        : {site.get('application_role_count', 0)}")
        print(f"    Total issues             : {site.get('issue_count_total', 0)}")
        print(f"    Unresolved issues        : {site.get('issue_count_unresolved', 0)}")
        print(f"    Updated last 7 days      : {site.get('issue_count_updated_last_7d', 0)}")
        print(f"    Failed API checks        : {site.get('failed_api_checks', 0)}")

        issue_metrics = site.get("issue_metrics", {}) or {}
        print(f"    Unresolved ratio         : {issue_metrics.get('unresolved_ratio', 0)}")
        print(f"    Issues per project       : {issue_metrics.get('issues_per_project', 0)}")
        print(f"    Unresolved per project   : {issue_metrics.get('unresolved_per_project', 0)}")
        print(f"    Issue risk score         : {site.get('issue_risk_score', 0)}")
        print(f"    Operational risk score   : {site.get('operational_risk_score', 0)}")

        health_breakdown = site.get("site_health_breakdown", {}) or {}
        print(f"    Endpoint failure ratio   : {health_breakdown.get('endpoint_failure_ratio', 0)}")

        endpoint_summary = site.get("endpoint_summary", {}) or {}
        print(f"    Endpoint checks total    : {endpoint_summary.get('total_checks', 0)}")
        print(f"    Endpoint checks passed   : {endpoint_summary.get('successful_checks', 0)}")
        print(f"    Endpoint checks failed   : {endpoint_summary.get('failed_checks', 0)}")

        blocking_failed = site.get("blocking_failed_checks", [])
        permission_limited = site.get("permission_limited_checks", [])
        status_reasons = site.get("status_reasons", [])
        issue_signals = site.get("issue_risk_signals", [])
        operational_signals = site.get("operational_risk_signals", [])

        if blocking_failed:
            print(f"    Blocking failures        : {format_list(blocking_failed)}")

        if permission_limited:
            print(f"    Permission limited       : {format_list(permission_limited)}")

        if issue_signals:
            print(f"    Issue risk signals       : {format_list(issue_signals)}")

        if operational_signals:
            print(f"    Operational signals      : {format_list(operational_signals)}")

        if status_reasons:
            print(f"    Status reasons           : {format_list(status_reasons)}")

        failed_details = endpoint_summary.get("failed_check_details", []) or []
        if failed_details:
            print("    Failed endpoint details  :")
            for detail in failed_details:
                print(
                    f"      - {detail.get('endpoint_key')} "
                    f"(status={detail.get('status_code')}, "
                    f"permission_limited={detail.get('permission_limited')})"
                )

        print()


def print_changes(comparison):
    print_section("SNAPSHOT CHANGES")

    if not comparison.get("has_previous_snapshot"):
        print("No previous snapshot found.")
        return

    summary = comparison.get("summary", {})
    summary_changes = summary.get("changes", {})

    if summary_changes:
        print("Summary changes:")
        for key, change in summary_changes.items():
            print(f"  - {key}: {change.get('old')} -> {change.get('new')}")
        print()
    else:
        print("No summary count changes.")
        print()

    print(f"Detailed changes found       : {comparison.get('change_count', 0)}")
    print(f"Info changes                 : {comparison.get('info_change_count', 0)}")
    print(f"Warning changes              : {comparison.get('warning_change_count', 0)}")
    print(f"Critical changes             : {comparison.get('critical_change_count', 0)}")

    changes = comparison.get("changes", [])
    if not changes:
        print("No detailed changes detected.")
        return

    print()

    for change in changes:
        severity = change.get("severity", "info").upper()
        change_type = change.get("type", "unknown")
        site_name = change.get("site_name", "Unknown site")
        field = change.get("field")
        old_value = change.get("old")
        new_value = change.get("new")

        print(f"[{severity}] {change_type} - {site_name}")

        if field is not None:
            print(f"    Field : {field}")

        if old_value is not None or new_value is not None:
            print(f"    From  : {old_value}")
            print(f"    To    : {new_value}")

        print()


def build_output(raw_collection, enriched_collection, comparison, snapshot_files, report_files):
    return {
        "run_timestamp_local": datetime.now().isoformat(),
        "raw_collection_summary": {
            "collected_at_utc": raw_collection.get("collected_at_utc"),
            "collection_duration_seconds": raw_collection.get("collection_duration_seconds", 0),
            "site_count": raw_collection.get("site_count", 0),
            "endpoint_totals": raw_collection.get("endpoint_totals", {})
        },
        "summary": {
            "site_count": enriched_collection.get("site_count", 0),
            "healthy_count": enriched_collection.get("healthy_count", 0),
            "warning_count": enriched_collection.get("warning_count", 0),
            "critical_count": enriched_collection.get("critical_count", 0)
        },
        "risk_summary": {
            "total_risk_score": enriched_collection.get("total_risk_score", 0),
            "average_risk_score": enriched_collection.get("average_risk_score", 0),
            "total_issue_risk_score": enriched_collection.get("total_issue_risk_score", 0),
            "total_operational_risk_score": enriched_collection.get("total_operational_risk_score", 0),
            "total_blocking_failures": enriched_collection.get("total_blocking_failures", 0),
            "total_permission_limited_checks": enriched_collection.get("total_permission_limited_checks", 0)
        },
        "sites": enriched_collection.get("sites", []),
        "comparison": comparison,
        "snapshot_files": snapshot_files,
        "report_files": report_files
    }


def main():
    print_heading("Jira Observation Monitor")

    try:
        validate_auth_config()
        print("Auth config check            : OK")
    except Exception as exc:
        print("Auth config check            : FAILED")
        print(str(exc))
        return

    print_auth_status()

    access_token = get_valid_access_token()

    if not access_token:
        print("Stored token                 : NOT FOUND")
        print("Starting OAuth flow...")
        print()

        try:
            access_token = run_interactive_oauth_flow()
            print("OAuth flow                   : SUCCESS")
        except Exception as exc:
            print("OAuth flow                   : FAILED")
            print(str(exc))
            return
    else:
        print()
        print("Stored token                 : OK")

    print()
    print("Collecting live Jira data...")

    try:
        raw_collection = collect_all_sites(access_token)
        print("Data collection              : SUCCESS")
    except Exception as exc:
        print("Data collection              : FAILED")
        print(str(exc))
        return

    print("Enriching data...")
    enriched_collection = enrich_collection(raw_collection)
    print("Enrichment                   : SUCCESS")

    print("Loading previous snapshot...")
    previous_snapshot = load_latest_snapshot()

    print("Comparing snapshots...")
    comparison = compare_snapshots(previous_snapshot, enriched_collection)

    print("Saving snapshot...")
    snapshot_files = save_snapshot(enriched_collection)
    print("Snapshot save                : SUCCESS")

    temp_output = {
        "raw_collection_summary": {
            "collected_at_utc": raw_collection.get("collected_at_utc"),
            "collection_duration_seconds": raw_collection.get("collection_duration_seconds", 0),
            "site_count": raw_collection.get("site_count", 0),
            "endpoint_totals": raw_collection.get("endpoint_totals", {})
        },
        "summary": {
            "site_count": enriched_collection.get("site_count", 0),
            "healthy_count": enriched_collection.get("healthy_count", 0),
            "warning_count": enriched_collection.get("warning_count", 0),
            "critical_count": enriched_collection.get("critical_count", 0)
        },
        "risk_summary": {
            "total_risk_score": enriched_collection.get("total_risk_score", 0),
            "average_risk_score": enriched_collection.get("average_risk_score", 0),
            "total_issue_risk_score": enriched_collection.get("total_issue_risk_score", 0),
            "total_operational_risk_score": enriched_collection.get("total_operational_risk_score", 0),
            "total_blocking_failures": enriched_collection.get("total_blocking_failures", 0),
            "total_permission_limited_checks": enriched_collection.get("total_permission_limited_checks", 0)
        },
        "sites": enriched_collection.get("sites", []),
        "comparison": comparison,
        "snapshot_files": snapshot_files
    }

    print("Saving reports...")
    report_files = save_reports(temp_output)
    print("Report save                  : SUCCESS")

    output = build_output(
        raw_collection=raw_collection,
        enriched_collection=enriched_collection,
        comparison=comparison,
        snapshot_files=snapshot_files,
        report_files=report_files
    )

    save_run_output(output)

    sites = output["sites"]

    healthy_sites = [s for s in sites if s.get("status") == "healthy"]
    warning_sites = [s for s in sites if s.get("status") == "warning"]
    critical_sites = [s for s in sites if s.get("status") == "critical"]

    print_runtime_summary(raw_collection, enriched_collection)
    print_status_summary(enriched_collection)
    print_top_risky_sites(sites, limit=5)

    if critical_sites:
        print_site_group("CRITICAL SITES", critical_sites)

    if warning_sites:
        print_site_group("WARNING SITES", warning_sites)

    if healthy_sites:
        print_site_group("HEALTHY SITES", healthy_sites)

    print_changes(comparison)

    print_section("OUTPUT FILES")
    print(f"Latest snapshot file         : {snapshot_files.get('latest_file')}")
    print(f"Timestamp snapshot           : {snapshot_files.get('timestamp_file')}")
    print(f"Snapshot index file          : {snapshot_files.get('index_file')}")
    print(f"Latest run output            : {RUN_OUTPUT_FILE}")
    print(f"Latest summary JSON          : {report_files.get('latest_summary_json')}")
    print(f"Latest summary TXT           : {report_files.get('latest_summary_txt')}")
    print(f"Timestamp summary JSON       : {report_files.get('timestamp_summary_json')}")
    print(f"Timestamp summary TXT        : {report_files.get('timestamp_summary_txt')}")

    print()
    print_divider("=")
    print("Run complete")
    print_divider("=")


if __name__ == "__main__":
    main()