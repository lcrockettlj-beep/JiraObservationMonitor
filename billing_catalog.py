def get_billing_catalog():
    """
    Static billing/app coverage snapshot based on the billing information supplied.
    Safe temporary layer until live billing/API integration is added.
    """
    entries = [
        # Atlassian app coverage
        {"bucket": "atlassian", "app_name": "Jira (Gaminglabs Enterprise)", "plan": "Enterprise", "users": "0 / 5000", "site": "Gaminglabs", "next_price_estimate": "", "billing_cycle": "annual", "next_bill_date": "Jul 03, 2026"},
        {"bucket": "atlassian", "app_name": "Service Collection", "plan": "Gaminglabs", "users": "", "site": "Gaminglabs", "next_price_estimate": "", "billing_cycle": "", "next_bill_date": ""},
        {"bucket": "atlassian", "app_name": "Bitbucket (gli-delivery)", "plan": "Standard", "users": "13 / 13", "site": "Gaminglabs", "next_price_estimate": "USD 47.45", "billing_cycle": "monthly", "next_bill_date": "Jul 03, 2026"},
        {"bucket": "atlassian", "app_name": "Bitbucket (GLI-DEV)", "plan": "Standard", "users": "36 / 36", "site": "Gaminglabs", "next_price_estimate": "USD 131.40", "billing_cycle": "monthly", "next_bill_date": "Jul 11, 2026"},
        {"bucket": "atlassian", "app_name": "Bitbucket (jira-ops-dashboard)", "plan": "Free", "users": "1", "site": "Gaminglabs", "next_price_estimate": "", "billing_cycle": "", "next_bill_date": ""},
        {"bucket": "atlassian", "app_name": "Rovo", "plan": "Free", "users": "", "site": "Gaminglabs", "next_price_estimate": "", "billing_cycle": "", "next_bill_date": ""},
        {"bucket": "atlassian", "app_name": "Rovo Credits", "plan": "Free", "users": "", "site": "Gaminglabs", "next_price_estimate": "", "billing_cycle": "", "next_bill_date": ""},
        {"bucket": "atlassian", "app_name": "Jira (gli-delivery-tm)", "plan": "Standard", "users": "28 / 50", "site": "https://gli-delivery-tm.atlassian.net", "next_price_estimate": "", "billing_cycle": "annual", "next_bill_date": "Nov 08, 2026"},
        {"bucket": "atlassian", "app_name": "Confluence (gli-delivery-tm)", "plan": "Free", "users": "4", "site": "https://gli-delivery-tm.atlassian.net", "next_price_estimate": "", "billing_cycle": "", "next_bill_date": ""},
        {"bucket": "atlassian", "app_name": "Jira (gli-global-technology)", "plan": "Standard", "users": "53 / 53", "site": "https://gli-global-technology.atlassian.net", "next_price_estimate": "USD 479.65", "billing_cycle": "monthly", "next_bill_date": "Jul 03, 2026"},
        {"bucket": "atlassian", "app_name": "Jira (gli-it-project)", "plan": "Standard", "users": "58 / 100", "site": "https://gli-it-project.atlassian.net", "next_price_estimate": "", "billing_cycle": "annual", "next_bill_date": "Aug 28, 2026"},
        {"bucket": "atlassian", "app_name": "Atlas", "plan": "Free", "users": "10", "site": "https://gli-it-project.atlassian.net", "next_price_estimate": "", "billing_cycle": "", "next_bill_date": ""},
        {"bucket": "atlassian", "app_name": "Goals", "plan": "Free", "users": "", "site": "https://gli-it-project.atlassian.net", "next_price_estimate": "", "billing_cycle": "", "next_bill_date": ""},
        {"bucket": "atlassian", "app_name": "Projects", "plan": "Free", "users": "", "site": "https://gli-it-project.atlassian.net", "next_price_estimate": "", "billing_cycle": "", "next_bill_date": ""},
        {"bucket": "atlassian", "app_name": "Confluence (gli-it-project)", "plan": "Standard", "users": "38 / 38", "site": "https://gli-it-project.atlassian.net", "next_price_estimate": "USD 260.61", "billing_cycle": "monthly", "next_bill_date": "Jul 08, 2026"},

        # Marketplace / third-party coverage
        {"bucket": "marketplace", "app_name": "Easy PDF Export, Word Export, HTML Export, with Automation", "plan": "Standard", "users": "28 / 50", "site": "https://gli-delivery-tm.atlassian.net", "next_price_estimate": "", "billing_cycle": "annual", "next_bill_date": "Nov 08, 2026"},
        {"bucket": "marketplace", "app_name": "Zephyr - Test Management and Automation for Jira", "plan": "Expired", "users": "", "site": "https://gli-delivery-tm.atlassian.net", "next_price_estimate": "USD 0.00", "billing_cycle": "", "next_bill_date": ""},
        {"bucket": "marketplace", "app_name": "Tricentis Test Management for Jira", "plan": "Standard", "users": "28 / 50", "site": "https://gli-delivery-tm.atlassian.net", "next_price_estimate": "", "billing_cycle": "annual", "next_bill_date": "Nov 08, 2026"},
        {"bucket": "marketplace", "app_name": "Tricentis Test Management for Jira", "plan": "Standard", "users": "58 / 100", "site": "https://gli-it-project.atlassian.net", "next_price_estimate": "", "billing_cycle": "annual", "next_bill_date": "Aug 28, 2026"},
        {"bucket": "marketplace", "app_name": "Checklists for Jira", "plan": "Free", "users": "58", "site": "https://gli-it-project.atlassian.net", "next_price_estimate": "", "billing_cycle": "", "next_bill_date": ""},
        {"bucket": "marketplace", "app_name": "Easy Reports Free - Custom Charts for Jira Dashboard", "plan": "Free", "users": "58", "site": "https://gli-it-project.atlassian.net", "next_price_estimate": "", "billing_cycle": "", "next_bill_date": ""},
        {"bucket": "marketplace", "app_name": "Agile Poker for Jira - Planning & Estimation", "plan": "Standard", "users": "58 / 100", "site": "https://gli-it-project.atlassian.net", "next_price_estimate": "", "billing_cycle": "annual", "next_bill_date": "Aug 28, 2026"},
        {"bucket": "marketplace", "app_name": "Zephyr - Test Management and Automation for Jira", "plan": "Expired", "users": "", "site": "https://gli-it-project.atlassian.net", "next_price_estimate": "USD 0.00", "billing_cycle": "", "next_bill_date": ""},
    ]

    atlassian_rows = [e for e in entries if e["bucket"] == "atlassian"]
    marketplace_rows = [e for e in entries if e["bucket"] == "marketplace"]
    jira_rows = [e for e in atlassian_rows if e["app_name"].startswith("Jira")]
    bitbucket_rows = [e for e in atlassian_rows if e["app_name"].startswith("Bitbucket")]
    confluence_rows = [e for e in atlassian_rows if e["app_name"].startswith("Confluence")]
    rovo_rows = [e for e in atlassian_rows if e["app_name"].startswith("Rovo")]

    billing_columns = ["app_name", "plan", "users", "site", "next_price_estimate", "billing_cycle", "next_bill_date"]

    return {
        "summary": {
            "atlassian_app_entry_count": len(atlassian_rows),
            "marketplace_app_entry_count": len(marketplace_rows),
            "unique_jira_entries": len(jira_rows),
            "unique_bitbucket_entries": len(bitbucket_rows),
            "unique_confluence_entries": len(confluence_rows),
            "unique_rovo_entries": len(rovo_rows),
        },
        "drilldowns": {
            "billing::atlassian_apps": {
                "title": "Billing Coverage — Atlassian Apps",
                "reason": "These entries reflect broader Atlassian app billing coverage beyond the tracked Jira operational estate.",
                "atlassian_area": "Atlassian Administration → Billing / Apps",
                "columns": billing_columns,
                "rows": atlassian_rows,
            },
            "billing::marketplace_apps": {
                "title": "Billing Coverage — Marketplace Apps",
                "reason": "These entries reflect Marketplace and third-party app billing coverage that is not yet part of the tracked operational site metrics.",
                "atlassian_area": "Atlassian Administration → Billing / Marketplace apps",
                "columns": billing_columns,
                "rows": marketplace_rows,
            },
            "billing::jira_entries": {
                "title": "Billing Coverage — Jira Entries",
                "reason": "These entries are the Jira billing records currently present in the supplied billing snapshot.",
                "atlassian_area": "Atlassian Administration → Billing / Apps",
                "columns": billing_columns,
                "rows": jira_rows,
            },
            "billing::bitbucket_entries": {
                "title": "Billing Coverage — Bitbucket Entries",
                "reason": "These entries are the Bitbucket billing records currently present in the supplied billing snapshot.",
                "atlassian_area": "Atlassian Administration → Billing / Apps",
                "columns": billing_columns,
                "rows": bitbucket_rows,
            },
            "billing::confluence_entries": {
                "title": "Billing Coverage — Confluence Entries",
                "reason": "These entries are the Confluence billing records currently present in the supplied billing snapshot.",
                "atlassian_area": "Atlassian Administration → Billing / Apps",
                "columns": billing_columns,
                "rows": confluence_rows,
            },
            "billing::rovo_entries": {
                "title": "Billing Coverage — Rovo Entries",
                "reason": "These entries are the Rovo billing records currently present in the supplied billing snapshot.",
                "atlassian_area": "Atlassian Administration → Billing / Apps",
                "columns": billing_columns,
                "rows": rovo_rows,
            },
        },
    }