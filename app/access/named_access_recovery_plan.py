import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "named_access_recovery_plan.json"
MD = ROOT / "reports" / "named_access_recovery_plan.md"

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def read(path):
    if not path.exists(): return None
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc: return {"_error": str(exc)}

def main():
    recon = read(ROOT/'reports/named_access_reconciliation.json') or {}
    named = read(ROOT/'static/data/live_named_access_contract') or {}
    summary = recon.get('summary') or {}
    conclusion = recon.get('conclusion') or {}
    safe = bool(summary.get('safe_to_enable_named_access_ui'))
    actions = [
        {"order":1,"action":"Keep named footprint UI disabled","status":"required","reason":"safe_to_enable_named_access_ui is false" if not safe else "safe_to_enable_named_access_ui is true"},
        {"order":2,"action":"Confirm group-derived product access expansion path","status":"required","reason": conclusion.get('reason') or 'Named role assignments do not yet reconcile to billing/API product totals.'},
        {"order":3,"action":"Identify unmapped resource IDs/cloud IDs","status":"required","reason":"Unmapped or out-of-scope resources are present in named access reconciliation."},
        {"order":4,"action":"Validate at least 5 known users against Atlassian Directory Apps tab","status":"required","reason":"Direct role-assignment source is valid but incomplete until verified against Directory-level entitlement truth."},
        {"order":5,"action":"Only enable named footprint UI after direct + group-derived mappings reconcile to billing/API product count","status":"gated","reason":"Avoid misleading named-user footprint."},
    ]
    payload = {
        "schema":"jom-named-access-recovery-plan-v1",
        "generated_at_utc": now(),
        "safe_to_enable_named_access_ui": safe,
        "current_reconciliation_summary": summary,
        "named_access_source_status": named.get('summary', {}),
        "conclusion": conclusion,
        "actions": actions,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    lines = ["# Named Access Recovery Plan", "", f"Generated: {payload['generated_at_utc']}", "", f"Safe to enable named access UI: **{safe}**", "", "## Actions"]
    for action in actions:
        lines.append(f"{action['order']}. **{action['action']}** — {action['status']}  ")
        lines.append(f"   - {action['reason']}")
    MD.write_text("\n".join(lines)+"\n", encoding='utf-8')
    print(json.dumps({"safe_to_enable_named_access_ui": safe, "json": str(OUT), "report": str(MD)}, indent=2))

if __name__=='__main__': main()
