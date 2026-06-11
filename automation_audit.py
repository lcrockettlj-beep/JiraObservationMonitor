from jira_client import safe_jira_get


def _safe_list(value):
    if isinstance(value, list):
        return value
    return []


def _summarise_audit_records(audit_payload):
    records = _safe_list((audit_payload or {}).get("records"))
    total = len(records)

    automation_related = 0
    categories = {}

    for record in records:
        if not isinstance(record, dict):
            continue

        summary = (record.get("summary") or "").lower()
        category = (record.get("category") or "").lower()

        if "automation" in summary or "automation" in category:
            automation_related += 1

        if category:
            categories[category] = categories.get(category, 0) + 1

    return {
        "record_count": total,
        "automation_related_record_count": automation_related,
        "category_counts": categories,
        "records_sample": records[:10]
    }


def collect_audit_and_automation_data(access_token, cloud_id):
    """
    Audit:
      - supported via Jira audit records endpoint when the caller has Administer Jira.
    Automation:
      - rule management is NOT supported through the current OAuth2 app flow.
      - we return an honest capability state instead of fake values.
    """
    audit_result = safe_jira_get(
        access_token=access_token,
        cloud_id=cloud_id,
        endpoint="auditing/record",
        params={"limit": 50}
    )

    if audit_result.get("ok"):
        audit_summary = _summarise_audit_records(audit_result.get("data"))
    else:
        audit_summary = {
            "record_count": None,
            "automation_related_record_count": None,
            "category_counts": {},
            "records_sample": []
        }

    automation_summary = {
        "rule_management_supported_with_current_auth": False,
        "reason": (
            "Automation REST rule management is not accessible with the current Jira OAuth2 app flow. "
            "The official Automation REST API uses API token or browser session authentication, "
            "and the rule management endpoints are not available to OAuth2 apps."
        ),
        "rule_count": None,
        "failure_count": None,
        "processing_metrics": None
    }

    return {
        "audit_summary": audit_summary,
        "audit_fetch_status": {
            "ok": audit_result.get("ok"),
            "error": audit_result.get("error"),
            "error_category": audit_result.get("error_category"),
            "status_code": audit_result.get("status_code"),
            "url": audit_result.get("url")
        },
        "automation_summary": automation_summary
    }