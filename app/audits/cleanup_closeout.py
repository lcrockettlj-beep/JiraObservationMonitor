
from __future__ import annotations
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT_JSON=ROOT/'reports'/'cleanup_closeout_handover.json'
OUT_MD=ROOT/'reports'/'cleanup_closeout_handover.md'

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def read_json(path):
    try: return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    except Exception as e: return {'_read_error':str(e)}
def git(args):
    try:
        p=subprocess.run(['git']+args,cwd=ROOT,capture_output=True,text=True,timeout=60)
        return {'returncode':p.returncode,'stdout':p.stdout.strip(),'stderr':p.stderr.strip()}
    except Exception as e: return {'returncode':None,'error':str(e)}
def main():
    reliability=read_json(ROOT/'static/data/source_reliability_status.json') or {}
    freshness=read_json(ROOT/'static/data/source_freshness_audit.json') or {}
    ownership=read_json(ROOT/'reports/project_ownership_map.json') or {}
    route=read_json(ROOT/'reports/route_static_reference_validation.json') or {}
    archive1=read_json(ROOT/'reports/safe_archive_candidates_status.json') or {}
    archive2=read_json(ROOT/'reports/safe_review_archive_status.json') or {}
    alignment=read_json(ROOT/'reports/project_alignment_audit.json') or {}
    git_status=git(['status','--short'])
    git_log=git(['log','--oneline','-n','12'])
    payload={
        'schema':'jom-cleanup-closeout-handover-v1',
        'generated_at_utc':now(),
        'phase':'Cleanup closeout after named access recovery and project alignment cleanup',
        'runtime_truth':{
            'source_reliability_overall':reliability.get('overall_status'),
            'source_reliability_summary':reliability.get('summary'),
            'source_reliability_issues':reliability.get('issues'),
            'source_freshness_overall':freshness.get('overall_state'),
            'source_freshness_counts':freshness.get('counts'),
        },
        'cleanup_summary':{
            'alignment_audit_files_scanned':(alignment.get('summary') or {}).get('total_files'),
            'ownership_files_classified':(ownership.get('summary') or {}).get('files_classified'),
            'ownership_archive_candidates_remaining':(ownership.get('summary') or {}).get('archive_candidates'),
            'ownership_review_like_remaining':(ownership.get('summary') or {}).get('review_like'),
            'ownership_delete_candidates':(ownership.get('summary') or {}).get('delete_candidates'),
            'safe_archive_candidates_moved':archive1.get('moved_count'),
            'safe_review_archive_moved':archive2.get('moved_count'),
            'route_validation_status_counts':(route.get('summary') or {}).get('status_counts'),
        },
        'archive_locations':{
            'safe_archive_candidates':archive1.get('archive_root'),
            'safe_archive_candidates_rollback':archive1.get('rollback_script'),
            'safe_review_archive':archive2.get('archive_root'),
            'safe_review_archive_rollback':archive2.get('rollback_script'),
        },
        'commits':{
            'recent_log':git_log.get('stdout'),
            'known_phase_commits':['c4bcee1 group expansion ARI mapping','49a3992 user footprint unlock','92c443e estate product/access truth refresh','d6fea6d safe archive candidates','5955ef7 inactive review files archive'],
        },
        'git_status_short':git_status,
        'remaining_recommendations':[
            'Do not delete backups yet; apply retention policy only after another clean baseline.',
            'Keep templates/site.html because web.py references it.',
            'Consider Python import bootstrap so scripts no longer need PYTHONPATH for root imports.',
            'Consider controlled folder restructure only after path validation pack for web.py/templates/static references.',
            'Keep named access UI work paused until structure remains stable after cleanup.'
        ]
    }
    OUT_JSON.parent.mkdir(parents=True,exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload,indent=2),encoding='utf-8')
    lines=['# Cleanup Closeout Handover','',f"Generated: `{payload['generated_at_utc']}`",'', '## Runtime Truth State','']
    rt=payload['runtime_truth']
    lines += [f"- Source Reliability: **{rt.get('source_reliability_overall')}**",f"- Source Freshness: **{rt.get('source_freshness_overall')}**",f"- Reliability issues: **{len(rt.get('source_reliability_issues') or [])}**",'', '## Cleanup Summary','']
    for k,v in payload['cleanup_summary'].items(): lines.append(f'- {k}: **{v}**')
    lines += ['', '## Archive / Rollback Locations','']
    for k,v in payload['archive_locations'].items(): lines.append(f'- {k}: `{v}`')
    lines += ['', '## Recent Git Log','', '```text', payload['commits']['recent_log'] or '', '```','', '## Recommendations','']
    for r in payload['remaining_recommendations']: lines.append(f'- {r}')
    lines += ['', '## Git Status At Handover','', '```text', payload['git_status_short'].get('stdout') or '(clean or no output)', '```']
    OUT_MD.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'status':'ok','json':str(OUT_JSON),'report':str(OUT_MD),'reliability':rt.get('source_reliability_overall'),'issues':len(rt.get('source_reliability_issues') or [])},indent=2))
if __name__=='__main__': main()
