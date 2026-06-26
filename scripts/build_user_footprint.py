from __future__ import annotations
import argparse, json
from pathlib import Path

def build_summary(rows, source):
    rows.sort(key=lambda item: (-int(item.get("site_count", 0)), str(item.get("name", "")).lower(), str(item.get("email", "")).lower()))
    total_users = len(rows)
    total_assignments = sum(int(x.get("site_count", 0)) for x in rows)
    return {
        "source": source,
        "summary": {
            "users_analyzed": total_users,
            "total_site_assignments": total_assignments,
            "average_sites_per_user": round(total_assignments / total_users, 2) if total_users else 0,
            "high_duplication_users": len([x for x in rows if x.get("category") == "high"]),
            "medium_duplication_users": len([x for x in rows if x.get("category") == "medium"]),
            "low_duplication_users": len([x for x in rows if x.get("category") == "low"]),
        },
        "users": rows,
        "notes": ["Built from static/data/user_access_source.json.", "High = 3+ sites, Medium = 2 sites, Low = 1 site."]
    }

def main():
    parser = argparse.ArgumentParser(description="Build Estate user footprint JSON from imported access source.")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    project_root = Path(args.project_root)
    source = project_root / "static" / "data" / "user_access_source.json"
    output = Path(args.output)
    rows = []
    source_label = "static/data/user_access_source.json"
    if source.exists():
        payload = json.loads(source.read_text(encoding="utf-8"))
        for item in payload.get("users", []):
            site_count = int(item.get("site_count", 0) or 0)
            if site_count <= 0:
                continue
            category = item.get("category") or ("high" if site_count >= 3 else "medium" if site_count == 2 else "low")
            rows.append({
                "id": item.get("id", ""),
                "name": item.get("name", "Unknown user"),
                "email": item.get("email", ""),
                "status": item.get("status", ""),
                "site_count": site_count,
                "sites": item.get("sites", []),
                "category": category,
            })
    else:
        source_label = "missing static/data/user_access_source.json"
    final = build_summary(rows, source_label)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(final["summary"], indent=2))
if __name__ == "__main__":
    main()
