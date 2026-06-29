import json
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = PROJECT_ROOT / "static" / "data" / "source_freshness_audit.json"

SOURCES = [
    {"key":"site_registry", "label":"Site Registry", "path":"static/data/site_registry.json", "timestamp_fields":["generated_at_utc"], "source_type":"STATIC_SNAPSHOT", "pages":["Home","Estate","Admin"]},
    {"key":"admin_truth_v2", "label":"Admin Truth Layer v2", "path":"static/data/admin_truth_v2.json", "timestamp_fields":["generated_at_utc"], "source_type":"STATIC_SNAPSHOT", "pages":["Estate","Admin"]},
    {"key":"estate_product_access", "label":"Estate Product Access", "path":"static/data/estate_product_access.json", "timestamp_fields":["generated_at_utc"], "source_type":"STATIC_SNAPSHOT", "pages":["Estate"]},
    {"key":"estate_access_truth", "label":"Estate Access Truth", "path":"static/data/estate_access_truth.json", "timestamp_fields":["generated_at_utc"], "source_type":"STATIC_SNAPSHOT", "pages":["Estate"]},
    {"key":"billing_seats", "label":"Billing Seats", "path":"static/data/billing_seats.json", "timestamp_fields":["generated_at_utc","created_at_utc","updated_at_utc"], "source_type":"STATIC_SNAPSHOT", "pages":["Estate","Admin"]},
    {"key":"user_footprint", "label":"User Footprint", "path":"static/data/user_footprint.json", "timestamp_fields":["generated_at_utc","created_at_utc","updated_at_utc"], "source_type":"STATIC_SNAPSHOT", "pages":["Estate"]},
    {"key":"latest_run", "label":"Latest Jira Runtime Run", "path":"latest_run.json", "timestamp_fields":["raw_collection_summary.collected_at_utc","run_timestamp_local"], "source_type":"LATEST_RUN", "pages":["Home","Estate","Site"]},
    {"key":"latest_run_admin_enriched", "label":"Latest Admin Enriched Run", "path":"latest_run_admin_enriched.json", "timestamp_fields":["raw_collection_summary.collected_at_utc","run_timestamp_local"], "source_type":"LATEST_RUN", "pages":["Home","Estate","Admin","Site"]},
]

def read_json(path):
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)

def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')

def get_nested(data, dotted):
    cur=data
    for part in dotted.split('.'):
        if not isinstance(cur, dict) or part not in cur: return None
        cur=cur[part]
    return cur

def parse_time(value):
    if not value: return None
    text=str(value).strip()
    if text.endswith('Z'): text=text[:-1] + '+00:00'
    try:
        dt=datetime.fromisoformat(text)
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        dt=datetime.strptime(str(value).strip(), '%Y-%m-%d %H:%M:%S')
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None

def display_time(dt):
    if not dt: return None
    return dt.strftime('%Y-%m-%d %H:%M UTC')

def classify(age_hours, exists, timestamp_present):
    if not exists: return 'MISSING'
    if not timestamp_present or age_hours is None: return 'UNKNOWN_TIMESTAMP'
    if age_hours <= 24: return 'CURRENT'
    if age_hours <= 72: return 'AGING'
    return 'STALE'

def operator_label(state):
    return {
        'CURRENT':'CURRENT',
        'AGING':'AGING SNAPSHOT',
        'STALE':'STALE SNAPSHOT',
        'MISSING':'MISSING SOURCE',
        'UNKNOWN_TIMESTAMP':'UNKNOWN TIMESTAMP'
    }.get(state, 'REVIEW')

def maybe_stamp_billing(project_root, now):
    path=project_root/'static/data/billing_seats.json'
    if not path.exists(): return False
    try:
        data=read_json(path)
    except Exception:
        return False
    if any(data.get(k) for k in ('generated_at_utc','created_at_utc','updated_at_utc')):
        return False
    data['generated_at_utc']=now.isoformat().replace('+00:00','Z')
    data['source_freshness_note']='Timestamp added by Source Freshness Audit v1.1 because file existed without freshness metadata.'
    write_json(path, data)
    return True

def main(project_root=PROJECT_ROOT):
    now=datetime.now(timezone.utc)
    billing_timestamp_added=maybe_stamp_billing(project_root, now)
    results=[]
    counts={"CURRENT":0,"AGING":0,"STALE":0,"MISSING":0,"UNKNOWN_TIMESTAMP":0}
    for src in SOURCES:
        path=project_root/src['path']
        exists=path.exists(); timestamp_value=None; timestamp_field=None; parsed=None; error=None
        if exists:
            try:
                data=read_json(path)
                for field in src['timestamp_fields']:
                    candidate=get_nested(data, field)
                    parsed_candidate=parse_time(candidate)
                    if candidate and parsed_candidate:
                        timestamp_value=candidate; timestamp_field=field; parsed=parsed_candidate; break
                    if candidate and not timestamp_value:
                        timestamp_value=candidate; timestamp_field=field
                if timestamp_value and not parsed: error='Timestamp present but not parseable as a freshness timestamp.'
            except Exception as exc:
                error='Could not read JSON: '+str(exc)
        age_hours=round((now-parsed).total_seconds()/3600,2) if parsed else None
        state=classify(age_hours, exists, bool(timestamp_value and parsed)); counts[state]=counts.get(state,0)+1
        results.append({
            'key':src['key'],'label':src['label'],'path':src['path'],'exists':exists,
            'source_type':src['source_type'],'pages':src['pages'],'timestamp_field':timestamp_field,
            'timestamp_value':timestamp_value,
            'parsed_timestamp_utc':parsed.isoformat().replace('+00:00','Z') if parsed else None,
            'display_timestamp_utc':display_time(parsed),'age_hours':age_hours,
            'freshness_state':state,'operator_label':operator_label(state),'error':error
        })
    overall='OK'
    if counts.get('MISSING',0) or counts.get('STALE',0): overall='ATTENTION'
    elif counts.get('UNKNOWN_TIMESTAMP',0): overall='REVIEW'
    payload={
        'schema':'jom-source-freshness-audit-v1.1',
        'generated_at_utc':now.isoformat().replace('+00:00','Z'),
        'display_generated_at_utc':display_time(now),
        'policy':{'current_hours':24,'aging_hours':72,'stale_after_hours':72,'rule':'No timestamp means not trusted as current; missing files are explicit MISSING, never treated as zero.'},
        'summary':{'overall_state':overall,'source_count':len(results),'counts':counts,'billing_timestamp_added':billing_timestamp_added},
        'sources':results
    }
    write_json(OUT_PATH, payload)
    print(json.dumps(payload['summary'], indent=2)); print('Output:', OUT_PATH)
if __name__=='__main__': main()
