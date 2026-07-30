#!/usr/bin/env python3
from __future__ import annotations
import json, shutil
from pathlib import Path
from datetime import datetime, timezone

REPORT_TXT=Path('reports/residual_static_string_cleanup_v1.txt')
REPORT_JSON=Path('reports/residual_static_string_cleanup_v1.json')
TARGETS=[
    Path('runtime/data/admin_enriched_refresh_status.json'),
    Path('runtime/data/runtime_execution_status.json'),
]
PACK_DIRS=[
    Path('jom_backend_static_truth_reference_repair_pack_v1'),
    Path('jom_runtime_authority_consumer_elimination_audit_pack_v1'),
]
REPLACEMENTS=[
    ('static\\\\data','runtime\\\\data'),
    ('static\\data','runtime\\data'),
    ('runtime/data','runtime/data'),
]

def read(p): return p.read_text(encoding='utf-8',errors='ignore')
def write(p,t): p.write_text(t,encoding='utf-8')

def main():
    REPORT_TXT.parent.mkdir(exist_ok=True)
    changed=[]
    removed=[]
    for p in TARGETS:
        if not p.exists():
            continue
        old=read(p); new=old; count=0
        for a,b in REPLACEMENTS:
            c=new.count(a)
            if c:
                new=new.replace(a,b); count+=c
        if new!=old:
            try:
                json.loads(new)
            except Exception as e:
                raise SystemExit(f'JSON validation failed for {p}: {e}')
            write(p,new)
            changed.append({'file':p.as_posix(),'replacements':count})
    for d in PACK_DIRS:
        if d.exists() and d.is_dir():
            shutil.rmtree(d)
            removed.append(d.as_posix())
    residual=[]
    for p in TARGETS:
        if p.exists():
            for i,line in enumerate(read(p).splitlines(),1):
                if 'static\\data' in line or 'runtime/data' in line or 'static\\\\data' in line:
                    residual.append({'file':p.as_posix(),'line':i,'text':line.strip()[:240]})
    result={
        'cleanup':'JOM Residual Static String Cleanup v1',
        'generated_utc':datetime.now(timezone.utc).isoformat(),
        'status':'PASS' if not residual else 'REVIEW',
        'changed_files':changed,
        'removed_pack_dirs':removed,
        'residual_static_strings':residual,
        'note':'app/web.py legacy filename refs are intentionally left for the next precise runtime contract pack.'
    }
    REPORT_JSON.write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['JOM Residual Static String Cleanup v1','='*43,f"Generated UTC: {result['generated_utc']}",f"Status: {result['status']}",'',f"Changed files: {len(changed)}"]
    for x in changed: lines.append(f"- {x['file']}: replacements={x['replacements']}")
    lines += ['',f"Removed extracted pack dirs: {len(removed)}"]
    for x in removed: lines.append(f'- {x}')
    lines += ['',f"Residual static strings: {len(residual)}"]
    for x in residual: lines.append(f"- {x['file']}:{x['line']} {x['text']}")
    lines += ['','Next: run a precise app/web.py legacy filename/runtime contract cleanup pack.']
    REPORT_TXT.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(lines[0]); print(f"Status: {result['status']}"); print(f"Changed files: {len(changed)}"); print(f"Removed pack dirs: {len(removed)}"); print(f"Report: {REPORT_TXT}")
    return 0 if not residual else 1
if __name__=='__main__': raise SystemExit(main())
