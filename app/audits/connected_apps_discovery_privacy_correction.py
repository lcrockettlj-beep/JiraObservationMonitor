from __future__ import annotations
import argparse, json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"reports"/"connected_apps_authority_discovery_v1.json"
OUTPUT=ROOT/"reports"/"connected_apps_authority_discovery_v1_1.json"
UUID_RE=re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?![0-9a-f])")
SENSITIVE_KEYS={"url_hash","started_at","filename","sha256"}


def now_utc(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")

def clean(value: Any, key: str="") -> Any:
    if key in SENSITIVE_KEYS: return None
    if isinstance(value,dict):
        return {k:clean(v,k) for k,v in value.items() if k not in SENSITIVE_KEYS}
    if isinstance(value,list): return [clean(v) for v in value]
    if isinstance(value,str): return UUID_RE.sub("<site-cloud-id>",value)
    return value

def shape_keys(value: Any) -> list[str]:
    keys=set()
    if isinstance(value,dict):
        for k,v in value.items(): keys.add(str(k)); keys.update(shape_keys(v))
    elif isinstance(value,list):
        for v in value: keys.update(shape_keys(v))
    return sorted(keys,key=str.lower)

def main(source: Path=SOURCE, output: Path=OUTPUT) -> int:
    raw=source.read_text(encoding="utf-8-sig")
    data=json.loads(raw)
    cleaned=clean(data)
    candidates=[]
    for row in cleaned.get("candidates",[]):
        req=row.get("request",{}); res=row.get("response",{}); assess=row.get("candidate_assessment",{})
        candidates.append({
            "method":req.get("method"),"host":req.get("host"),"path":req.get("path"),
            "query_parameter_names":req.get("query_parameter_names",[]),"status":res.get("status"),
            "mime_type":res.get("mime_type"),"parse_state":res.get("parse_state"),
            "response_shape":res.get("shape"),"response_shape_keys":shape_keys(res.get("shape")),
            "score":assess.get("score"),"shape_signals":assess.get("shape_key_signals",[]),
        })
    result={
      "schema":"jom-connected-apps-authority-discovery-v1.1","generated_at_utc":now_utc(),
      "status":cleaned.get("status"),
      "privacy":{"raw_har_stored":False,"raw_request_bodies_stored":False,"raw_response_bodies_stored":False,"header_values_stored":False,"query_values_stored":False,"cookies_stored":False,"tokens_stored":False,"cloud_ids_stored":False,"source_hashes_stored":False,"timestamps_from_har_stored":False},
      "summary":cleaned.get("summary",{}),"candidates":candidates,
      "decision":{"connected_apps_authority_proven":False,"marketplace_app_installation_authority_proven":False,"safe_to_publish_marketplace_apps":False,"next_step":"Validate the Jira gateway candidate contract, authentication outside a browser session, site binding, pagination, installation semantics and completeness."},
      "correction":{"source_schema":data.get("schema"),"reason":"v1 retained a site cloud UUID in gateway request paths and response-shape keys could break Windows PowerShell case-insensitive JSON conversion.","uuid_path_segments_redacted":True,"duplicate_case_shape_keys_preserved_for_python_only":True,"v1_must_be_deleted":True}
    }
    rendered=json.dumps(result,indent=2)
    assert not UUID_RE.search(rendered),"UUID remained after sanitization"
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(rendered,encoding="utf-8")
    print(json.dumps({"status":result["status"],"schema":result["schema"],"candidate_count":len(candidates),"cloud_ids_stored":False,"output":str(output)},indent=2))
    return 0

if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--source",default=str(SOURCE)); parser.add_argument("--output",default=str(OUTPUT)); a=parser.parse_args(); raise SystemExit(main(Path(a.source),Path(a.output)))
