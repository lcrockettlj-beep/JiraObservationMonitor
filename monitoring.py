from estate_metrics import build_estate_metrics
import csv

def load_users():
    with open("export-users (1).csv", newline='', encoding="utf-8") as f:
        return list(csv.DictReader(f))


users = load_users()

data = build_estate_metrics(users)

print(data)