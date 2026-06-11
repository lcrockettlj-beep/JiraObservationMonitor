import os
import json
import csv
from datetime import datetime

REPORT_DIR = "reports"

def ensure_report_dir():
    os.makedirs(REPORT_DIR, exist_ok=True)


def save_reports(output):
    ensure_report_dir()

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    date_folder = datetime.now().strftime("%Y-%m-%d")

    folder_path = os.path.join(REPORT_DIR, date_folder)
    os.makedirs(folder_path, exist_ok=True)

    # ------------------------------
    # JSON OUTPUT
    # ------------------------------
    latest_json = os.path.join(REPORT_DIR, "latest_summary.json")
    timestamp_json = os.path.join(folder_path, f"summary_{timestamp}.json")

    with open(latest_json, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    with open(timestamp_json, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    # ------------------------------
    # TXT OUTPUT
    # ------------------------------
    latest_txt = os.path.join(REPORT_DIR, "latest_summary.txt")
    timestamp_txt = os.path.join(folder_path, f"summary_{timestamp}.txt")

    summary = output.get("summary", {})
    risk = output.get("risk_summary", {})

    lines = []
    lines.append("Jira Observation Monitor")
    lines.append("=" * 60)
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("")

    lines.append("STATUS")
    lines.append("-" * 60)
    lines.append(f"Sites: {summary.get('site_count')}")
    lines.append(f"Healthy: {summary.get('healthy_count')}")
    lines.append(f"Warning: {summary.get('warning_count')}")
    lines.append(f"Critical: {summary.get('critical_count')}")
    lines.append("")

    lines.append("RISK")
    lines.append("-" * 60)
    lines.append(f"Total risk: {risk.get('total_risk_score')}")
    lines.append(f"Average risk: {risk.get('average_risk_score')}")
    lines.append("")

    text_output = "\n".join(lines)

    with open(latest_txt, "w", encoding="utf-8") as f:
        f.write(text_output)

    with open(timestamp_txt, "w", encoding="utf-8") as f:
        f.write(text_output)

    # ------------------------------
    # BASIC CSV (sites)
    # ------------------------------
    latest_csv = os.path.join(REPORT_DIR, "latest_sites.csv")

    with open(latest_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "name", "status", "risk",
            "projects", "issues_total", "issues_unresolved"
        ])

        for site in output.get("sites", []):
            writer.writerow([
                site.get("name"),
                site.get("status"),
                site.get("risk_score"),
                site.get("project_count"),
                site.get("issue_count_total"),
                site.get("issue_count_unresolved")
            ])

    return {
        "latest_summary_json": latest_json,
        "timestamp_summary_json": timestamp_json,
        "latest_summary_txt": latest_txt,
        "timestamp_summary_txt": timestamp_txt,
        "latest_sites_csv": latest_csv
    }
