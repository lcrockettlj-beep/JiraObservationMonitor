import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = ROOT / "static" / "data" / "user_footprint.json"
TRUTH_V2_PATH = ROOT / "static" / "data" / "named_access_truth_v2.json"
RECON_V2_PATH = ROOT / "reports" / "named_access_reconciliation_v2.json"
RECON_V1_PATH = ROOT / "reports" / "named_access_reconciliation.json"
NAMED_DIRECT_PATH = ROOT / "static" / "data" / "admin_named_access.json"
ADMIN_ENRICHED_PATH = ROOT / "latest_run_admin_enriched.json"


def now_utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def read_json(path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        return {"_read_error": str(exc)}


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def unavailable(reason, reconciliation_source=None):
    payload = {
        "schema": "jom-user-footprint-v2",
        "generated_at_utc": now_utc(),
        "source_status": "unavailable",
        "reason": reason,
        "safe_to_show_named_access_ui": False,
        "reconciliation_source": reconciliation_source,
        "summary": {
            "users_analyzed": None,
            "average_sites_per_user": None,
            "high_duplication_users": None,
            "medium_duplication_users": None,
            "total_product_access_assignments": None,
        },
        "users": [],
    }
    write_json(OUT_PATH, payload)
    print(json.dumps({"source_status": "unavailable", "safe": False, "reason": reason, "output": str(OUT_PATH)}, indent=2))


def category(site_count):
    if site_count >= 3:
        return "high"
    if site_count == 2:
        return "medium"
    return "low"


def build_identity_lookup():
    lookup = {}

    direct = read_json(NAMED_DIRECT_PATH, {}) or {}
    for row in direct.get('users', []) or []:
        account_id = row.get('account_id') or row.get('accountId')
        if not account_id:
            continue
        lookup[str(account_id)] = {
            "name": row.get('display_name') or row.get('name') or row.get('email') or str(account_id),
            "email": row.get('email') or "",
        }

    admin = read_json(ADMIN_ENRICHED_PATH, {}) or {}
    drilldowns = admin.get('drilldowns') or {}
    for section in drilldowns.values():
        if not isinstance(section, dict):
            continue
        rows = section.get('rows') or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            account_id = row.get('accountId') or row.get('account_id')
            if account_id and str(account_id) not in lookup:
                lookup[str(account_id)] = {
                    "name": row.get('name') or row.get('email') or str(account_id),
                    "email": row.get('email') or "",
                }
    return lookup


def site_keys_from_truth_user(user):
    sites = []
    access_sources = set(user.get('access_sources') or [])
    product_assignments = 0
    for site in user.get('sites', []) or []:
        if isinstance(site, dict):
            site_key = site.get('site_key') or site.get('site_name') or site.get('cloud_id')
            if site_key:
                sites.append(str(site_key))
            products = site.get('products') or []
            product_assignments += len(products) if isinstance(products, list) else 1
            for source in site.get('sources') or []:
                access_sources.add(str(source))
        elif site:
            sites.append(str(site))
            product_assignments += 1
    return sorted(set(sites)), sorted(access_sources), product_assignments


def main():
    recon = read_json(RECON_V2_PATH)
    reconciliation_source = str(RECON_V2_PATH.relative_to(ROOT)) if recon else None
    if not recon:
        recon = read_json(RECON_V1_PATH)
        reconciliation_source = str(RECON_V1_PATH.relative_to(ROOT)) if recon else None

    if not recon:
        unavailable("No named access reconciliation file is available.", reconciliation_source)
        return

    safe = bool(recon.get('safe_to_enable_named_access_ui') or (recon.get('summary') or {}).get('safe_to_enable_named_access_ui'))
    if not safe:
        unavailable("Named access reconciliation is not safe_to_enable_named_access_ui=true. Named footprint remains unavailable.", reconciliation_source)
        return

    truth = read_json(TRUTH_V2_PATH)
    if not truth:
        unavailable("named_access_truth_v2.json is missing or unreadable even though reconciliation is safe.", reconciliation_source)
        return

    truth_summary = truth.get('summary') or {}
    recon_summary = recon.get('summary') or {}
    users = truth.get('users') or []
    if not isinstance(users, list) or not users:
        unavailable("named_access_truth_v2.json has no users. Named footprint cannot be generated.", reconciliation_source)
        return

    identities = build_identity_lookup()
    out_users = []
    total_site_count = 0
    total_product_assignments = 0
    for user in users:
        if not isinstance(user, dict):
            continue
        account_id = str(user.get('account_id') or user.get('accountId') or '')
        if not account_id:
            continue
        sites, access_sources, product_assignments = site_keys_from_truth_user(user)
        site_count = len(sites)
        total_site_count += site_count
        total_product_assignments += product_assignments
        ident = identities.get(account_id, {})
        out_users.append({
            "account_id": account_id,
            "name": ident.get('name') or account_id,
            "email": ident.get('email') or "",
            "sites": sites,
            "site_count": site_count,
            "products": ["jira-software"] if product_assignments else [],
            "product_access_assignments": product_assignments,
            "access_sources": access_sources,
            "category": category(site_count),
        })

    analysed = len(out_users)
    avg_sites = round(total_site_count / analysed, 2) if analysed else 0
    payload = {
        "schema": "jom-user-footprint-v2",
        "generated_at_utc": now_utc(),
        "source_status": "generated",
        "reason": "Named access footprint generated from named_access_truth_v2 after reconciliation_v2 passed safe_to_enable_named_access_ui=true.",
        "safe_to_show_named_access_ui": True,
        "reconciliation_source": reconciliation_source,
        "truth_source": str(TRUTH_V2_PATH.relative_to(ROOT)),
        "summary": {
            "users_analyzed": analysed,
            "average_sites_per_user": avg_sites,
            "high_duplication_users": sum(1 for row in out_users if row['category'] == 'high'),
            "medium_duplication_users": sum(1 for row in out_users if row['category'] == 'medium'),
            "total_product_access_assignments": total_product_assignments,
            "reconciled_api_product_users": recon_summary.get('api_product_users'),
            "named_minus_api_product": recon_summary.get('named_minus_api_product'),
            "named_unique_users": recon_summary.get('named_unique_users'),
        },
        "users": sorted(out_users, key=lambda row: (-row['site_count'], -row['product_access_assignments'], row.get('name') or row['account_id'])),
    }
    write_json(OUT_PATH, payload)
    print(json.dumps({"source_status": "generated", "safe": True, "users": analysed, "assignments": total_product_assignments, "output": str(OUT_PATH)}, indent=2))


if __name__ == '__main__':
    main()


