import json

from auth import (
    get_valid_access_token,
    run_interactive_oauth_flow,
    validate_auth_config
)
from data_collector import collect_all_sites
from intelligence import enrich_collection
from monitoring import compare_snapshots
from snapshots import load_latest_snapshot, save_snapshot


def main():
    print("Jira Observation Monitor")
    print("=" * 60)
    print()

    try:
        validate_auth_config()
    except Exception as exc:
        print("Auth configuration error:")
        print(str(exc))
        return

    access_token = get_valid_access_token()

    if not access_token:
        print("No valid stored access token found.")
        print("Starting interactive Atlassian OAuth flow...")
        print()

        try:
            access_token = run_interactive_oauth_flow()
        except Exception as exc:
            print("OAuth flow failed:")
            print(str(exc))
            return

    print("Collecting live Jira data...")
    try:
        raw_collection = collect_all_sites(access_token)
    except Exception as exc:
        print("Data collection failed:")
        print(str(exc))
        return

    print("Enriching data...")
    enriched_collection = enrich_collection(raw_collection)

    print("Loading previous snapshot...")
    previous_snapshot = load_latest_snapshot()

    print("Comparing snapshots...")
    comparison = compare_snapshots(previous_snapshot, enriched_collection)

    print("Saving snapshot...")
    snapshot_files = save_snapshot(enriched_collection)

    output = {
        "summary": {
            "site_count": enriched_collection.get("site_count", 0),
            "healthy_count": enriched_collection.get("healthy_count", 0),
            "warning_count": enriched_collection.get("warning_count", 0),
            "critical_count": enriched_collection.get("critical_count", 0)
        },
        "sites": enriched_collection.get("sites", []),
        "comparison": comparison,
        "snapshot_files": snapshot_files
    }

    print()
    print("Run complete")
    print("=" * 60)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()