import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRUTH = ROOT / "static" / "data" / "live_named_access_contract"
ADMIN_TRUTH = ROOT / "static" / "data" / "admin_truth_v2.json"
OUT = ROOT / "reports" / "named_access_reconciliation_v2.json"
REPORT = ROOT / "reports" / "named_access_recovery_implementation.md"


def now_utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": str(exc)}


def main():
    truth = read_json(TRUTH, {}) or {}
    admin_truth = read_json(ADMIN_TRUTH, {}) or {}
    summary = truth.get("summary") or {}
    admin_summary = admin_truth.get("summary") or {}

    named_assignments = int(summary.get("total_product_access_assignments") or 0)
    named_users = int(summary.get("unique_users") or 0)
    api_product_users = int(admin_summary.get("api_product_users") or 0)
    billing_jira_seats = int(admin_summary.get("billing_jira_seats") or 0)
    admin_human_users = int(admin_summary.get("admin_human_users") or 0)
    group_expansion_safe = bool(summary.get("group_expansion_safe"))

    assignment_delta = named_assignments - api_product_users
    safe = bool(
        group_expansion_safe
        and named_assignments > 0
        and api_product_users > 0
        and named_assignments == api_product_users
        and named_users <= billing_jira_seats
    )

    blockers = []
    if not group_expansion_safe:
        blockers.append("Group-derived product access expansion is not available or not safe.")
    if named_assignments != api_product_users:
        blockers.append(f"Named access assignments ({named_assignments}) do not equal API product users ({api_product_users}).")
    if named_users > billing_jira_seats:
        blockers.append(f"Named users ({named_users}) exceed billing seats ({billing_jira_seats}).")

    payload = {
        "schema": "jom-named-access-reconciliation-v2",
        "generated_at_utc": now_utc(),
        "safe_to_enable_named_access_ui": safe,
        "status": "aligned" if safe else "blocked",
        "summary": {
            "named_unique_users": named_users,
            "named_product_access_assignments": named_assignments,
            "api_product_users": api_product_users,
            "billing_jira_seats": billing_jira_seats,
            "admin_human_users": admin_human_users,
            "named_minus_api_product": assignment_delta,
            "group_expansion_safe": group_expansion_safe,
        },
        "blockers": blockers,
        "next_actions": [
            "Collect group-derived Jira Software product access from Atlassian Directory/App assignment source.",
            "Map group-derived assignments to monitored site keys.",
            "Re-run named access truth v2 and confirm named_product_access_assignments == api_product_users.",
            "Only enable named footprint UI after reconciliation is aligned.",
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Named Access Recovery Implementation",
        "",
        f"Generated: {payload['generated_at_utc']}",
        "",
        f"Safe to enable named access UI: **{safe}**",
        "",
        "## Summary",
        "",
        f"- Named unique users: {named_users}",
        f"- Named product access assignments: {named_assignments}",
        f"- API product users: {api_product_users}",
        f"- Billing Jira seats: {billing_jira_seats}",
        f"- Named minus API product: {assignment_delta}",
        f"- Group expansion safe: {group_expansion_safe}",
        "",
        "## Blockers",
        "",
    ]
    if blockers:
        for blocker in blockers:
            lines.append(f"- {blocker}")
    else:
        lines.append("- None")
    lines.extend(["", "## Next Actions", ""])
    for action in payload["next_actions"]:
        lines.append(f"- {action}")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"safe": safe, "status": payload["status"], "output": str(OUT), "report": str(REPORT)}, indent=2))


if __name__ == "__main__":
    main()
