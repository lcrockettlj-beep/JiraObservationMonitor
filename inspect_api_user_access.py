import json
from pathlib import Path
from collections import Counter

path = Path("static/data/user_access_source.json")
data = json.loads(path.read_text(encoding="utf-8"))

print("SOURCE:", data.get("source"))
print("SUMMARY:")
print(json.dumps(data.get("summary", {}), indent=2))

print()
print("SITE RESULTS:")
for site in data.get("site_results", []):
    print(site)

print()
print("ACCOUNT TYPES:")
print(Counter(str(u.get("account_type", "") or "blank") for u in data.get("users", [])))

print()
print("TOP 10 USERS:")
for user in data.get("users", [])[:10]:
    print({
        "name": user.get("name"),
        "email": user.get("email"),
        "account_type": user.get("account_type"),
        "site_count": user.get("site_count"),
        "sites": user.get("sites"),
    })
