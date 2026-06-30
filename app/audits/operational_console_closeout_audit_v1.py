from __future__ import annotations
import json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/operational_console_closeout_audit_v1.json'
MD=ROOT/'reports/operational_console_closeout_audit_v1.md'

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def read(p):
    if not p.exists(): return None
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception as e: return {'_error':str(e)}
def run(cmd):
    try:
        p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=180)
        return {'cmd':' '.join(cmd),'returncode':p.returncode,'stdout_tail':(p.stdout or '')[-4000:],'stderr_tail':(p.stderr or '')[-4000:]}
    except Exception as e: return {'cmd':' '.join(cmd),'error':str(e),'returncode':None}
def exists(rel): return (ROOT/rel).exists()
def main():
    reliability=read(ROOT/'static/data/source_reliability_status.json') or {}
    relsum=reliability.get('summary') or {}
    ui_files=['static/data/operational_console_status.json','static/data/operational_console_ui_view.json','static/data/operational_console_drilldowns.json','static/data/operational_console_insights.json','static/data/operational_console_role_views.json','static/data/site_onboarding_review.json']
    active_scripts=['scripts/run_operational_snapshot.py','scripts/source_reliability_audit.py','scripts/build_site_registry.py','scripts/refresh_runtime_sources.py','scripts/_project_bootstrap.py']
    legacy_root=['scripts/sync_runtime.py','scripts/snapshot_controller.py','scripts/run_sync_for_scheduler.cmd']
    archived_legacy=['scripts/_legacy_review/sync_runtime.py','scripts/_legacy_review/snapshot_controller.py','scripts/_legacy_review/run_sync_for_scheduler.cmd']
    scheduler=run(['schtasks','/Query','/TN','JOM_Sync_Runtime','/V','/FO','LIST'])
    sched_text=scheduler.get('stdout_tail','')
    validations=[run([sys.executable,'-m','py_compile']+active_scripts), run([sys.executable,'scripts/source_reliability_audit.py'])]
    checks={
      'source_reliability_ok': reliability.get('overall_status')=='ok' and relsum.get('issue_count')==0,
      'runtime_advisory_present': relsum.get('runtime_refresh_overall')=='ok_with_advisory',
      'scheduler_targets_operational_snapshot': 'run_operational_snapshot.py' in sched_text and 'sync_runtime.py' not in sched_text and 'run_sync_for_scheduler.cmd' not in sched_text,
      'scheduler_start_in_project': str(ROOT) in sched_text,
      'ui_files_exist': all(exists(x) for x in ui_files),
      'active_scripts_exist': all(exists(x) for x in active_scripts),
      'legacy_not_in_root': all(not exists(x) for x in legacy_root),
      'legacy_archived': all(exists(x) for x in archived_legacy),
      'py_compile_ok': validations[0].get('returncode')==0,
      'reliability_rerun_ok': validations[1].get('returncode')==0,
    }
    overall='ok' if all(checks.values()) else 'attention'
    payload={'schema':'jom-operational-console-closeout-audit-v1','generated_at_utc':now(),'overall_status':overall,'checks':checks,'source_reliability':{'overall_status':reliability.get('overall_status'),'summary':relsum,'advisories':reliability.get('advisories',[])},'scheduler_query':scheduler,'validations':validations,'ui_files':{f:exists(f) for f in ui_files},'active_scripts':{f:exists(f) for f in active_scripts},'legacy_root':{f:exists(f) for f in legacy_root},'archived_legacy':{f:exists(f) for f in archived_legacy}}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,indent=2),encoding='utf-8')
    lines=['# Operational Console Closeout Audit v1','',f'Generated: `{payload["generated_at_utc"]}`','',f'Overall status: **{overall}**','','## Checks']
    for k,v in checks.items(): lines.append(f'- {k}: **{v}**')
    MD.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'status':overall,'report_json':str(OUT),'report_md':str(MD),'checks':checks},indent=2))
    return 0 if overall=='ok' else 1
if __name__=='__main__': raise SystemExit(main())
