
from __future__ import annotations
import json, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CANDIDATES=[
 'static/css/named_access_dashboard.css',
 'static/js/named_access_dashboard.js',
 'static/js/runtime_template_metrics.js',
 'static/css/site_registry_layout_enforcer.css',
 'static/js/site_registry_layout_enforcer.js',
 'templates/admin.html',
]
KEEP=['templates/site.html']
def stamp(): return datetime.now().strftime('%Y%m%d_%H%M%S')
def rel(p): return p.relative_to(ROOT).as_posix()
def write_json(p,obj): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj,indent=2),encoding='utf-8')
def run(cmd):
    try:
        proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=240)
        return {'cmd':' '.join(cmd),'returncode':proc.returncode,'stdout_tail':(proc.stdout or '')[-2000:],'stderr_tail':(proc.stderr or '')[-2000:]}
    except Exception as e:
        return {'cmd':' '.join(cmd),'returncode':None,'error':str(e)}
def main():
    archive_root=ROOT/'backups'/'_project_cleanup_archive'/stamp()
    moved=[]; missing=[]; skipped=[]
    archive_root.mkdir(parents=True,exist_ok=True)
    for item in CANDIDATES:
        src=ROOT/item
        if not src.exists(): missing.append(item); continue
        dest=archive_root/item
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.move(str(src),str(dest))
        moved.append({'from':item,'to':rel(dest)})
    for item in KEEP:
        if not (ROOT/item).exists(): skipped.append({'file':item,'reason':'KEEP file missing unexpectedly'})
    rollback=archive_root/'rollback_safe_review_archive.ps1'
    lines=['param([string]$ProjectRoot = "C:\\Users\\Luke_C\\Desktop\\JiraObservationMonitor")','$ErrorActionPreference="Stop"']
    for m in moved:
        lines.append(f'$src = Join-Path $ProjectRoot "{m["to"].replace("/", "\\\\")}"')
        lines.append(f'$dst = Join-Path $ProjectRoot "{m["from"].replace("/", "\\\\")}"')
        lines.append('if(Test-Path $src){ New-Item -ItemType Directory -Path (Split-Path -Parent $dst) -Force | Out-Null; Move-Item $src $dst -Force; Write-Host "Restored $dst" -ForegroundColor Green }')
    lines.append('Write-Host "Rollback complete." -ForegroundColor Green')
    rollback.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    checks=[]
    for s in ['scripts/audit_source_freshness.py','scripts/source_reliability_audit.py','scripts/project_ownership_map.py','scripts/route_static_reference_validation.py']:
        if (ROOT/s).exists(): checks.append(run([sys.executable,s]))
    status={'schema':'jom-safe-review-archive-status-v1','mode':'archive-only-no-delete','archive_root':str(archive_root),'candidate_count':len(CANDIDATES),'moved_count':len(moved),'missing_count':len(missing),'skipped_count':len(skipped),'moved':moved,'missing':missing,'skipped':skipped,'keep_untouched':KEEP,'validation_runs':checks,'rollback_script':str(rollback)}
    out=ROOT/'reports'/'safe_review_archive_status.json'; write_json(out,status)
    print(json.dumps({'status':'ok','moved_count':len(moved),'missing_count':len(missing),'archive_root':str(archive_root),'status_file':str(out)},indent=2))
if __name__=='__main__': main()
