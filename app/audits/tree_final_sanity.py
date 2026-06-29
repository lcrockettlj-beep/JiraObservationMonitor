
from __future__ import annotations
import json, subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
OUT_JSON=ROOT/'reports'/'tree_final_sanity_report.json'
OUT_MD=ROOT/'reports'/'tree_final_sanity_report.md'
SKIP={'.git','__pycache__','.venv','venv','node_modules'}

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def rel(p): return p.relative_to(ROOT).as_posix()
def read_json(p):
    try: return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None
    except Exception as e: return {'_read_error':str(e)}
def git(args):
    try:
        p=subprocess.run(['git']+args,cwd=ROOT,capture_output=True,text=True,timeout=60)
        return {'returncode':p.returncode,'stdout':p.stdout.strip(),'stderr':p.stderr.strip()}
    except Exception as e: return {'returncode':None,'error':str(e)}
def bucket(path:Path):
    parts=path.relative_to(ROOT).parts
    if not parts: return 'root'
    first=parts[0]
    if first=='static' and len(parts)>1: return 'static/'+parts[1]
    return first

def scan():
    files=[]
    for p in ROOT.rglob('*'):
        if p.is_file() and not any(part in SKIP for part in p.parts):
            files.append(p)
    return files

def main():
    files=scan(); buckets=Counter(bucket(p) for p in files); suffixes=Counter(p.suffix.lower() or '<none>' for p in files)
    reliability=read_json(ROOT/'static/data/source_reliability_status.json') or {}
    freshness=read_json(ROOT/'static/data/source_freshness_audit.json') or {}
    ownership=read_json(ROOT/'reports/project_ownership_map.json') or {}
    route=read_json(ROOT/'reports/route_static_reference_validation.json') or {}
    bootstrap=read_json(ROOT/'reports/python_import_bootstrap_verify.json') or {}
    closeout=read_json(ROOT/'reports/cleanup_closeout_handover.json') or {}
    py_files=[p for p in files if p.suffix.lower()=='.py']
    active_templates=sorted(rel(p) for p in (ROOT/'templates').glob('*.html')) if (ROOT/'templates').exists() else []
    root_files=sorted(rel(p) for p in ROOT.iterdir() if p.is_file())
    payload={
        'schema':'jom-tree-final-sanity-report-v1',
        'generated_at_utc':now(),
        'mode':'report-only-no-changes',
        'summary':{
            'total_files':len(files),
            'python_files':len(py_files),
            'root_files':len(root_files),
            'templates':len(active_templates),
            'bucket_counts':dict(sorted(buckets.items())),
            'suffix_counts':dict(sorted(suffixes.items())),
        },
        'runtime_truth':{
            'source_reliability_overall':reliability.get('overall_status'),
            'source_reliability_summary':reliability.get('summary'),
            'source_reliability_issues':reliability.get('issues'),
            'source_freshness_overall':freshness.get('overall_state'),
            'source_freshness_counts':freshness.get('counts'),
        },
        'structure_truth':{
            'ownership_summary':ownership.get('summary'),
            'route_validation_summary':route.get('summary'),
            'python_bootstrap_safe':bootstrap.get('safe'),
            'python_bootstrap_compile_errors':bootstrap.get('compile_error_count'),
            'cleanup_closeout_phase':closeout.get('phase'),
        },
        'active_templates':active_templates,
        'root_files':root_files,
        'git':{
            'status_short':git(['status','--short']),
            'latest_commits':git(['log','--oneline','-n','15']),
        },
        'next_phase_recommendations':[
            'Commit this final sanity report if the git status only contains this report/script and expected refreshed audit JSON files.',
            'Do not start folder moves today.',
            'Next phase should be a report-only folder refactor plan before any physical move.',
            'Keep templates/site.html active because route validation still references it via web.py.',
            'Backups should remain protected until a dedicated retention pack is approved.'
        ]
    }
    OUT_JSON.parent.mkdir(parents=True,exist_ok=True); OUT_JSON.write_text(json.dumps(payload,indent=2),encoding='utf-8')
    lines=['# Tree Final Sanity Report','',f"Generated: `{payload['generated_at_utc']}`",'', '## Runtime Truth','']
    rt=payload['runtime_truth']; lines += [f"- Source Reliability: **{rt.get('source_reliability_overall')}**",f"- Source Freshness: **{rt.get('source_freshness_overall')}**",f"- Reliability issue count: **{len(rt.get('source_reliability_issues') or [])}**",'', '## Tree Summary','']
    for k,v in payload['summary'].items():
        if isinstance(v,dict): continue
        lines.append(f'- {k}: **{v}**')
    lines += ['', '## Bucket Counts','']
    for k,v in payload['summary']['bucket_counts'].items(): lines.append(f'- `{k}`: {v}')
    lines += ['', '## Structure Truth','']
    st=payload['structure_truth']
    lines.append(f"- Python bootstrap safe: **{st.get('python_bootstrap_safe')}**")
    lines.append(f"- Python compile errors: **{st.get('python_bootstrap_compile_errors')}**")
    lines.append(f"- Ownership delete candidates: **{(st.get('ownership_summary') or {}).get('delete_candidates')}**")
    lines.append(f"- Ownership archive candidates: **{(st.get('ownership_summary') or {}).get('archive_candidates')}**")
    lines += ['', '## Next Recommendations','']
    for r in payload['next_phase_recommendations']: lines.append(f'- {r}')
    lines += ['', '## Git Status Short','', '```text', payload['git']['status_short'].get('stdout') or '(clean or no output)', '```']
    OUT_MD.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'status':'ok','json':str(OUT_JSON),'report':str(OUT_MD),'reliability':rt.get('source_reliability_overall'),'issues':len(rt.get('source_reliability_issues') or []),'total_files':len(files)},indent=2))
if __name__=='__main__': main()
