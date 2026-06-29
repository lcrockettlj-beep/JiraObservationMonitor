import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = PROJECT_ROOT / "static" / "data" / "user_footprint.json"
NAMED_PATH = PROJECT_ROOT / "static" / "data" / "admin_named_access.json"
RECON_PATH = PROJECT_ROOT / "reports" / "named_access_reconciliation.json"
REGISTRY_PATH = PROJECT_ROOT / "static" / "data" / "site_registry.json"


def now_utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def read_json(path, default=None):
    if not path.exists():
        return default
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def monitored_site_keys():
    registry = read_json(REGISTRY_PATH, {}) or {}
    keys = set()
    for site in registry.get('sites', []):
        if site.get('classification') == 'monitored':
            for field in ('site_key', 'site_name', 'cloud_id'):
                value = site.get(field)
                if value:
                    keys.add(str(value))
    return keys


def category(count):
    if count >= 3:
        return 'high'
    if count == 2:
        return 'medium'
    return 'low'


def unavailable(reason):
    return {
        "schema": "jom-user-footprint-v1",
        "generated_at_utc": now_utc(),
        "source_status": "unavailable",
        "reason": reason,
        "safe_to_show_named_access_ui": False,
        "summary": {
            "users_analyzed": None,
            "average_sites_per_user": None,
            "high_duplication_users": None,
            "medium_duplication_users": None,
        },
        "users": [],
    }


def main():
    named = read_json(NAMED_PATH)
    recon = read_json(RECON_PATH, {}) or {}
    if not named:
        payload = unavailable('admin_named_access.json missing; cannot build verified user footprint.')
    else:
        safe = bool((recon.get('summary') or {}).get('safe_to_enable_named_access_ui'))
        # The file is still generated even when unsafe, but summary values remain null and users remain hidden.
        # This removes MISSING SOURCE while preserving the guard against misleading named-user data.
        if not safe:
            payload = unavailable('Named access source exists but reconciliation says safe_to_enable_named_access_ui=false. Named footprint remains unavailable.')
        else:
            monitored = monitored_site_keys()
            users = []
            for user in named.get('users', []):
                access = user.get('jira_access') or []
                sites = sorted({a.get('site_key') for a in access if a.get('site_key') in monitored})
                count = len(sites)
                users.append({
                    "account_id": user.get('account_id'),
                    "name": user.get('display_name') or '',
                    "email": user.get('email') or '',
                    "sites": sites,
                    "site_count": count,
                    "category": category(count),
                })
            analysed = len(users)
            avg = round(sum(u['site_count'] for u in users) / analysed, 2) if analysed else 0
            payload = {
                "schema": "jom-user-footprint-v1",
                "generated_at_utc": now_utc(),
                "source_status": "generated",
                "safe_to_show_named_access_ui": True,
                "summary": {
                    "users_analyzed": analysed,
                    "average_sites_per_user": avg,
                    "high_duplication_users": sum(1 for u in users if u['category'] == 'high'),
                    "medium_duplication_users": sum(1 for u in users if u['category'] == 'medium'),
                },
                "users": sorted(users, key=lambda u: (-u['site_count'], u.get('name') or u.get('account_id') or '')),
            }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(json.dumps({"source_status": payload.get('source_status'), "safe": payload.get('safe_to_show_named_access_ui'), "output": str(OUT_PATH)}, indent=2))

if __name__ == '__main__':
    main()
