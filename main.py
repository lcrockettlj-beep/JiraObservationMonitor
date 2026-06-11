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
from monitoring import apply_snapshot_deltas, compare_snapshots
from reporting import save_reports
from snapshots import load_latest_snapshot, save_snapshot
from trends import analyze_historical_trends


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


def signed_value(value):
    if value is None:
        return "baseline"
    if value > 0:
        return f"+{value}"
    return str(value)


def save_run_output(output):
    with open(RUN_OUTPUT_FILE, "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)


def build_mypermissions_url(cloud_id):
    if not cloud_id:
        return None
    return f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/mypermissions"


def print_auth_status():
    token_status = get_token_status()

    print_section("AUTH STATUS")
    print(f"Token file exists            : {token_status.get('exists')}")
    print(f"Stored token valid           : {token_status.get('valid')}")
    print(f"Has refresh token            : {token_status.get('has_refresh_token')}")
    print(f"Token expires at             : {token_status.get('expires_at')}")


def print_runtime_summary(raw_collection, enriched_collection):
    print_section("RUNTIME SUMMARY")

    print(f"Collected at UTC             : {raw_collection.get('collected_at_utc')}")
    print(f"Collection duration (sec)    : {raw_collection.get('collection_duration_seconds', 0)}")
    print(f"Sites collected              : {raw_collection.get('site_count', 0)}")

    collector_settings = raw_collection.get("collector_settings", {}) or {}
    print(f"Site worker limit            : {collector_settings.get('max_site_workers', 0)}")
    print(f"Site workers used            : {collector_settings.get('site_workers_used', 0)}")
    print(f"Endpoint workers per site    : {collector_settings.get('endpoint_workers', 0)}")

    endpoint_totals = raw_collection.get("endpoint_totals", {}) or {}
    print(f"Endpoint checks passed       : {endpoint_totals.get('successful_checks', 0)}")
    print(f"Endpoint checks failed       : {endpoint_totals.get('failed_checks', 0)}")
    print(f"Permission-limited endpoints : {endpoint_totals.get('permission_limited_checks', 0)}")
    print(f"Core blocking endpoints      : {endpoint_totals.get('core_blocking_failed_checks', 0)}")
    print(f"Enrichment failed endpoints  : {endpoint_totals.get('enrichment_failed_checks', 0)}")

    error_category_totals = raw_collection.get("error_category_totals", {}) or {}
    if error_category_totals:
        print("Error category totals        :")
        for category_name, count in sorted(error_category_totals.items()):
            print(f"  - {category_name}: {count}")

    print(f"Total risk score             : {enriched_collection.get('total_risk_score', 0)}")
    print(f"Average risk score           : {enriched_collection.get('average_risk_score', 0)}")
    print(f"Total issue risk score       : {enriched_collection.get('total_issue_risk_score', 0)}")
    print(f"Total operational risk score : {enriched_collection.get('total_operational_risk_score', 0)}")
    print(f"Total blocking API failures  : {enriched_collection.get('total_blocking_failures', 0)}")
    print(f"Permission-limited checks    : {enriched_collection.get('total_permission_limited_checks', 0)}")


def print_excluded_sites(raw_collection):
    excluded_sites = raw_collection.get("excluded_sites", []) or []

    print_section("EXCLUDED SITES")

    if not excluded_sites:
        print("No excluded sites.")
        return

    for site in excluded_sites:
        print(f"- {site.get('name')} | {site.get('url')} | cloud_id={site.get('cloud_id')}")


def print_status_summary(enriched_collection):
    print_section("STATUS SUMMARY")
    print(f"Sites total                  : {enriched_collection.get('site_count', 0)}")
    print(f"Healthy                      : {enriched_collection.get('healthy_count', 0)}")
    print(f"Warning                      : {enriched_collection.get('warning_count', 0)}")
    print(f"Critical                     : {enriched_collection.get('critical_count', 0)}")


def print_delta_summary(enriched_collection):
    print_section("DELTA SUMMARY")

    delta_summary = enriched_collection.get("delta_summary", {}) or {}

    print(f"Project delta total          : {signed_value(delta_summary.get('project_delta_total'))}")
    print(f"Total users delta total      : {signed_value(delta_summary.get('total_users_delta_total'))}")
    print(f"Active users delta total     : {signed_value(delta_summary.get('active_users_delta_total'))}")
    print(f"Inactive users delta total   : {signed_value(delta_summary.get('inactive_users_delta_total'))}")
    print(f"Licensed users delta total   : {signed_value(delta_summary.get('licensed_users_estimate_delta_total'))}")


def print_permission_checker(sites):
    print_section("PERMISSION CHECKER")

    if not sites:
        print("No sites available.")
        return

    for site in sites:
        checker = site.get("permission_checker", {}) or {}
        endpoint_summary = site.get("endpoint_summary", {}) or {}
        permission_issue_urls = endpoint_summary.get("permission_issue_urls", []) or []

        print(f"{site.get('name')}")
        print(f"  Site URL                  : {site.get('url')}")
        print(f"  My permissions URL        : {build_mypermissions_url(site.get('cloud_id'))}")
        print(f"  Permission data available : {checker.get('available')}")
        print(f"  Has ADMINISTER            : {checker.get('has_administer_jira')}")
        print(f"  Has ADMINISTER_PROJECTS   : {checker.get('has_administer_projects')}")
        print(f"  Has BROWSE_PROJECTS       : {checker.get('has_browse_projects')}")

        if permission_issue_urls:
            for item in permission_issue_urls:
                print(f"  Related failing endpoint  : {item.get('endpoint_key')}")
                print(f"  Related endpoint URL      : {item.get('url')}")
                print(f"  Status code               : {item.get('status_code')}")
                print(f"  Error category            : {item.get('error_category')}")
        else:
            print("  Related failing endpoint  : None")

        print()


def print_user_licence_summary(sites):
    print_section("USER & LICENCE SUMMARY")

    if not sites:
        print("No sites available.")
        return

    for site in sites:
        user_summary = site.get("user_summary", {}) or {}
        licence_summary = site.get("licence_summary", {}) or {}

        print(f"{site.get('name')}")
        print(f"  Total users              : {user_summary.get('total_users')}")
        print(f"  Active users             : {user_summary.get('active_users')}")
        print(f"  Inactive users           : {user_summary.get('inactive_users')}")
        print(f"  Licensed users estimate  : {licence_summary.get('licensed_users_estimate')}")
        print(f"  Total users delta        : {signed_value(site.get('total_users_delta'))}")
        print(f"  Active users delta       : {signed_value(site.get('active_users_delta'))}")
        print(f"  Inactive users delta     : {signed_value(site.get('inactive_users_delta'))}")
        print(f"  Licensed users delta     : {signed_value(site.get('licensed_users_estimate_delta'))}")
        print(f"  Growth status            : {site.get('growth_status')}")

        products = licence_summary.get("products", []) or []
        if products:
            print("  Licence products         :")
            for product in products[:10]:
                print(
                    f"    - {product.get('name')} "
                    f"(key={product.get('key')}, user_count={product.get('user_count')}, "
                    f"seats={product.get('number_of_seats')}, remaining={product.get('remaining_seats')})"
                )
        else:
            print("  Licence products         : None")

        print()


def print_audit_automation_summary(sites):
    print_section("AUTOMATION & AUDIT SUMMARY")

    if not sites:
        print("No sites available.")
        return

    for site in sites:
        audit_summary = site.get("audit_summary", {}) or {}
        audit_fetch_status = site.get("audit_fetch_status", {}) or {}
        automation_summary = site.get("automation_summary", {}) or {}

        print(f"{site.get('name')}")
        print(f"  Audit fetch OK           : {audit_fetch_status.get('ok')}")
        print(f"  Audit record count       : {audit_summary.get('record_count')}")
        print(f"  Automation audit hits    : {audit_summary.get('automation_related_record_count')}")

        category_counts = audit_summary.get("category_counts", {}) or {}
        if category_counts:
            print("  Audit categories         :")
            for category_name, count in sorted(category_counts.items()):
                print(f"    - {category_name}: {count}")

        print("  Automation API support   : "
              f"{automation_summary.get('rule_management_supported_with_current_auth')}")
        print(f"  Automation note          : {automation_summary.get('reason')}")
        print()


def print_historical_trend_summary(historical_trends):
    print_section("HISTORICAL TREND SUMMARY")

    if not historical_trends.get("has_history"):
        print("No historical trend data yet.")
        return

    summary = historical_trends.get("summary", {}) or {}

    print(f"Snapshots analysed           : {historical_trends.get('lookback_snapshots', 0)}")
    print(f"Sites in history             : {summary.get('site_count', 0)}")
    print(f"Warning/Critical streaks     : {summary.get('warning_or_critical_streak_sites', 0)}")
    print(f"Rising unresolved sites      : {summary.get('rising_unresolved_sites', 0)}")
    print(f"Rising risk sites            : {summary.get('rising_risk_sites', 0)}")
    print(f"Recurring blocking sites     : {summary.get('recurring_blocking_failure_sites', 0)}")


def print_top_sites(sites, limit=5):
    print_section("TOP SITES")

    if not sites:
        print("No sites available.")
        return

    for index, site in enumerate(sites[:limit], start=1):
        print(
            f"{index}. {status_icon(site.get('status'))} "
            f"{site.get('name')} | status={site.get('status')} | risk={site.get('risk_score', 0)}"
        )
        print(f"    Projects                 : {site.get('project_count', 0)}")
        print(f"    Project delta            : {signed_value(site.get('project_count_delta'))}")
        print(f"    Total issues             : {site.get('issue_count_total', 0)}")
        print(f"    Issue total delta        : {signed_value(site.get('issue_count_total_delta'))}")
        print(f"    Unresolved issues        : {site.get('issue_count_unresolved', 0)}")
        print(f"    Unresolved delta         : {signed_value(site.get('issue_count_unresolved_delta'))}")
        print(f"    Updated last 7 days      : {site.get('issue_count_updated_last_7d', 0)}")
        print(f"    Site collection (sec)    : {site.get('collection_duration_seconds', 0)}")

        user_summary = site.get("user_summary", {}) or {}
        print(
            "    Users total / active / inactive : "
            f"{user_summary.get('total_users')} / {user_summary.get('active_users')} / {user_summary.get('inactive_users')}"
        )
        print(
            "    User deltas total / active / inactive : "
            f"{signed_value(site.get('total_users_delta'))} / "
            f"{signed_value(site.get('active_users_delta'))} / "
            f"{signed_value(site.get('inactive_users_delta'))}"
        )

        licence_summary = site.get("licence_summary", {}) or {}
        print(f"    Licensed users estimate  : {licence_summary.get('licensed_users_estimate')}")
        print(f"    Licensed users delta     : {signed_value(site.get('licensed_users_estimate_delta'))}")
        print(f"    Growth status            : {site.get('growth_status')}")

        reasons = site.get("status_reasons", []) or []
        print(f"    Reasons                  : {format_list(reasons)}")
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


def build_output(raw_collection, enriched_collection, comparison, snapshot_files, report_files, historical_trends):
    return {
        "run_timestamp_local": datetime.now().isoformat(),
        "raw_collection_summary": {
            "collected_at_utc": raw_collection.get("collected_at_utc"),
            "collection_duration_seconds": raw_collection.get("collection_duration_seconds", 0),
            "site_count": raw_collection.get("site_count", 0),
            "excluded_sites": raw_collection.get("excluded_sites", []),
            "endpoint_totals": raw_collection.get("endpoint_totals", {}),
            "error_category_totals": raw_collection.get("error_category_totals", {}),
            "collector_settings": raw_collection.get("collector_settings", {})
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
        "delta_summary": enriched_collection.get("delta_summary", {}),
        "sites": enriched_collection.get("sites", []),
        "comparison": comparison,
        "historical_trends": historical_trends,
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

    print("Applying snapshot deltas...")
    enriched_collection = apply_snapshot_deltas(previous_snapshot, enriched_collection)
    print("Snapshot delta apply         : SUCCESS")

    print("Comparing snapshots...")
    comparison = compare_snapshots(previous_snapshot, enriched_collection)

    print("Saving snapshot...")
    snapshot_files = save_snapshot(enriched_collection)
    print("Snapshot save                : SUCCESS")

    print("Analysing historical trends...")
    historical_trends = analyze_historical_trends(lookback=10)
    print("Historical trends            : SUCCESS")

    temp_output = {
        "raw_collection_summary": {
            "collected_at_utc": raw_collection.get("collected_at_utc"),
            "collection_duration_seconds": raw_collection.get("collection_duration_seconds", 0),
            "site_count": raw_collection.get("site_count", 0),
            "excluded_sites": raw_collection.get("excluded_sites", []),
            "endpoint_totals": raw_collection.get("endpoint_totals", {}),
            "error_category_totals": raw_collection.get("error_category_totals", {}),
            "collector_settings": raw_collection.get("collector_settings", {})
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
        "delta_summary": enriched_collection.get("delta_summary", {}),
        "sites": enriched_collection.get("sites", []),
        "comparison": comparison,
        "historical_trends": historical_trends,
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
        report_files=report_files,
        historical_trends=historical_trends
    )

    save_run_output(output)

    sites = output["sites"]

    print_runtime_summary(raw_collection, enriched_collection)
    print_excluded_sites(raw_collection)
    print_status_summary(enriched_collection)
    print_delta_summary(enriched_collection)
    print_permission_checker(sites)
    print_user_licence_summary(sites)
    print_audit_automation_summary(sites)
    print_historical_trend_summary(historical_trends)
    print_top_sites(sites, limit=5)
    print_changes(comparison)

    print_section("OUTPUT FILES")
    print(f"Latest snapshot file         : {snapshot_files.get('latest_file')}")
    print(f"Timestamp snapshot           : {snapshot_files.get('timestamp_file')}")
    print(f"Snapshot index file          : {snapshot_files.get('index_file')}")
    print(f"Latest run output            : {RUN_OUTPUT_FILE}")
    print(f"Latest summary JSON          : {report_files.get('latest_summary_json')}")
    print(f"Latest summary TXT           : {report_files.get('latest_summary_txt')}")
    print(f"Latest summary MD            : {report_files.get('latest_summary_md')}")
    print(f"Latest sites CSV             : {report_files.get('latest_sites_csv')}")
    print(f"Latest changes CSV           : {report_files.get('latest_changes_csv')}")
    print(f"Latest permission CSV        : {report_files.get('latest_permission_checker_csv')}")
    print(f"Latest permission issues CSV : {report_files.get('latest_permission_issues_csv')}")
    print(f"Latest excluded sites CSV    : {report_files.get('latest_excluded_sites_csv')}")
    print(f"Latest user/licence CSV      : {report_files.get('latest_user_licence_csv')}")
    print(f"Latest audit/automation CSV  : {report_files.get('latest_audit_automation_csv')}")

    print()
    print_divider("=")
    print("Run complete")
    print_divider("=")


if __name__ == "__main__":
    main()