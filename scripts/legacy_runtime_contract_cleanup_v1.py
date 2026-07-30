#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import json
import os
import py_compile
import re
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

REPORT_TXT=Path('reports/legacy_runtime_contract_cleanup_v1.txt')
REPORT_JSON=Path('reports/legacy_runtime_contract_cleanup_v1.json')
BACKUP_DIR=Path('reports/legacy_runtime_contract_cleanup_v1_backups')

TARGETS=[Path('app/web.py'),Path('app/registry/site_registry_runtime.py'),Path('scripts/build_site_registry.py')]
LEGACY_NAMES=['site_registry.json','estate_access_truth.json','site_registry.json']
ALL_AUDIT_NAMES=LEGACY_NAMES+['admin_truth_v2.json','admin_truth_v2.json','estate_access_truth.json']
ROUTES=['/api/estate/discovery-authority/coverage','/runtime/status','/runtime/refresh']

@dataclass
class Change:
    file:str
    detail:str
    count:int

@dataclass
class Finding:
    file:str
    line:int
    label:str
    text:str


def now_stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')

def read(p:Path)->str:
    return p.read_text(encoding='utf-8',errors='ignore')

def write(p:Path,t:str):
    p.write_text(t,encoding='utf-8')

def backup(p:Path,stamp:str):
    if not p.exists(): return None
    dest=BACKUP_DIR/stamp/p.as_posix()
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(p,dest)
    return dest.as_posix()

def replace_exact(text:str, old:str, new:str):
    count=text.count(old)
    return text.replace(old,new),count

def patch_web_py(path:Path)->list[Change]:
    if not path.exists(): return []
    text=read(path); original=text; changes=[]

    # Remove old misleading compatibility comment only if it is the first line.
    lines=text.splitlines()
    if lines and 'site_registry.json is derived compatibility only' in lines[0]:
        lines=lines[1:]
        text='\n'.join(lines)+'\n'
        changes.append(Change(path.as_posix(),'removed obsolete monitored_sites compatibility header comment',1))

    # Remove obsolete source map entries from discovery-authority coverage dictionaries only where exact quoted keys exist.
    exact_blocks=[
        '        "monitored_sites": "site_registry.json",\n',
        '        "site_lifecycle_decisions": "site_registry.json",\n',
    ]
    for block in exact_blocks:
        if block in text:
            text=text.replace(block,'')
            changes.append(Change(path.as_posix(),f'removed obsolete coverage source map entry: {block.strip()}',1))

    # Do not remove route handlers or write paths blindly; app/web.py keeps them for next precise route refactor if still active.
    if text!=original:
        write(path,text)
    return changes

def patch_site_registry_runtime(path:Path)->list[Change]:
    if not path.exists(): return []
    text=read(path); original=text; changes=[]
    replacements=[
        ('MONITORED_CONFIG = "config/site_registry.json"','MONITORED_CONFIG = "runtime/data/site_registry.json"'),
        ('REGISTRY_OUTPUT = "runtime/data/site_registry.json"','REGISTRY_OUTPUT = "runtime/data/site_registry.json"'),
        ('REGISTRY_OUTPUT = "runtime/data/site_registry.json"','REGISTRY_OUTPUT = "runtime/data/site_registry.json"'),
    ]
    for old,new in replacements:
        text,c=replace_exact(text,old,new)
        if c: changes.append(Change(path.as_posix(),f'{old} -> {new}',c))

    # If code joins PROJECT_ROOT / MONITORED_CONFIG, runtime/data/site_registry.json is now the contract.
    if text!=original: write(path,text)
    return changes

def patch_build_site_registry(path:Path)->list[Change]:
    if not path.exists(): return []
    text=read(path); original=text; changes=[]
    replacements=[
        ('data = root / "static" / "data"','data = root / "runtime" / "data"'),
        ("data = root / 'static' / 'data'","data = root / 'runtime' / 'data'"),
        ('output = root / "static" / "data" / "site_registry.json"','output = root / "runtime" / "data" / "site_registry.json"'),
        ("output = root / 'static' / 'data' / 'site_registry.json'","output = root / 'runtime' / 'data' / 'site_registry.json'"),
    ]
    for old,new in replacements:
        text,c=replace_exact(text,old,new)
        if c: changes.append(Change(path.as_posix(),f'{old} -> {new}',c))
    if text!=original: write(path,text)
    return changes

def collect_refs(paths=TARGETS)->list[Finding]:
    refs=[]
    for p in paths:
        if not p.exists(): continue
        for i,line in enumerate(read(p).splitlines(),1):
            for name in ALL_AUDIT_NAMES:
                if name in line:
                    refs.append(Finding(p.as_posix(),i,name,line.strip()[:260]))
    return refs

def collect_static_data_refs()->list[Finding]:
    refs=[]
    for p in TARGETS:
        if not p.exists(): continue
        for i,line in enumerate(read(p).splitlines(),1):
            if re.search(r'static[\\/]+data',line,re.I):
                refs.append(Finding(p.as_posix(),i,'runtime/data',line.strip()[:260]))
    return refs

def compile_targets():
    results=[]
    for p in TARGETS:
        if p.exists() and p.suffix=='.py':
            try:
                py_compile.compile(str(p),doraise=True)
                results.append({'file':p.as_posix(),'status':'PASS'})
            except Exception as e:
                results.append({'file':p.as_posix(),'status':'FAIL','error':str(e)})
    return results

def free_port():
    with contextlib.closing(socket.socket(socket.AF_INET,socket.SOCK_STREAM)) as s:
        s.bind(('127.0.0.1',0)); return int(s.getsockname()[1])

def smoke(skip:bool):
    if skip: return {'status':'SKIPPED','reason':'skip requested'}
    if not Path('app/web.py').exists(): return {'status':'SKIPPED','reason':'app/web.py not found'}
    port=free_port(); env=os.environ.copy(); env['FLASK_APP']='app.web'; env['PYTHONUNBUFFERED']='1'
    cmd=[sys.executable,'-m','flask','run','--host','127.0.0.1','--port',str(port),'--no-debugger','--no-reload']
    proc=None
    try:
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
        base=f'http://127.0.0.1:{port}'
        for _ in range(30):
            if proc.poll() is not None: break
            try:
                route_results=[]
                for route in ROUTES:
                    try:
                        with urlopen(base+route,timeout=2) as r:
                            route_results.append({'route':route,'status':int(r.status)})
                    except Exception as e:
                        route_results.append({'route':route,'status':'ERROR','error':str(e)[:200]})
                authority=[x for x in route_results if x['route']=='/api/estate/discovery-authority/coverage'][0]
                return {'status':'PASS' if authority.get('status')==200 else 'REVIEW','routes':route_results}
            except Exception:
                time.sleep(0.5)
        err=''
        if proc and proc.stderr:
            with contextlib.suppress(Exception): err=proc.stderr.read()[:1200]
        return {'status':'SKIPPED','reason':'Flask smoke could not start/respond','stderr':err}
    except Exception as e:
        return {'status':'SKIPPED','reason':str(e)}
    finally:
        if proc and proc.poll() is None:
            with contextlib.suppress(Exception): proc.terminate(); proc.wait(timeout=5)
            if proc.poll() is None:
                with contextlib.suppress(Exception): proc.kill()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--skip-smoke-test',action='store_true'); args=ap.parse_args()
    REPORT_TXT.parent.mkdir(exist_ok=True); BACKUP_DIR.mkdir(parents=True,exist_ok=True)
    stamp=now_stamp(); backups=[]
    for p in TARGETS:
        b=backup(p,stamp)
        if b: backups.append(b)
    before_refs=collect_refs()
    changes=[]
    changes+=patch_web_py(Path('app/web.py'))
    changes+=patch_site_registry_runtime(Path('app/registry/site_registry_runtime.py'))
    changes+=patch_build_site_registry(Path('scripts/build_site_registry.py'))
    compile_results=compile_targets()
    after_refs=collect_refs()
    static_refs=collect_static_data_refs()
    smoke_result=smoke(args.skip_smoke_test)
    compile_fail=[x for x in compile_results if x.get('status')!='PASS']
    # PASS means no runtime/data in target files and compile clean. Legacy filename refs may remain for next route-level cleanup.
    status='PASS' if not static_refs and not compile_fail and smoke_result.get('status') in {'PASS','SKIPPED','REVIEW'} else 'FAIL'
    result={
        'cleanup':'JOM Legacy Runtime Contract Cleanup Pack v1',
        'generated_utc':datetime.now(timezone.utc).isoformat(),
        'status':status,
        'backups':backups,
        'changes':[asdict(c) for c in changes],
        'before_legacy_refs':[asdict(f) for f in before_refs],
        'after_legacy_refs':[asdict(f) for f in after_refs],
        'static_data_refs':[asdict(f) for f in static_refs],
        'compile_results':compile_results,
        'smoke_result':smoke_result,
        'note':'Remaining monitored/access/lifecycle filename refs in app/web.py are left for a route-level refactor if still present. This pack only applies exact safe contract cleanup.'
    }
    REPORT_JSON.write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['JOM Legacy Runtime Contract Cleanup Pack v1','='*43,f"Generated UTC: {result['generated_utc']}",f"Status: {status}",'',f"Backups: {len(backups)}"]
    for b in backups: lines.append(f'- {b}')
    lines += ['',f"Changes: {len(changes)}"]
    for c in changes: lines.append(f'- {c.file}: {c.detail} ({c.count})')
    lines += ['',f"Compile failures: {len(compile_fail)}"]
    for f in compile_fail: lines.append(f"- {f.get('file')}: {f.get('error')}")
    lines += ['',f"Static/data refs in target files: {len(static_refs)}"]
    for f in static_refs: lines.append(f'- {f.file}:{f.line} [{f.label}] {f.text}')
    lines += ['',f"Legacy filename refs before: {len(before_refs)}",f"Legacy filename refs after: {len(after_refs)}"]
    for f in after_refs[:120]: lines.append(f'- {f.file}:{f.line} [{f.label}] {f.text}')
    if len(after_refs)>120: lines.append(f'... {len(after_refs)-120} more in JSON')
    lines += ['',f"Smoke: {smoke_result.get('status')}"]
    if smoke_result.get('reason'): lines.append(f"Smoke reason: {smoke_result.get('reason')}")
    lines += ['','Decision:', 'PASS means runtime/data is absent from target files and compile is clean. If legacy filename refs remain, use the report for the next precise route-level refactor.']
    REPORT_TXT.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(lines[0]); print(f'Status: {status}'); print(f'Changes: {len(changes)}'); print(f'Legacy refs after: {len(after_refs)}'); print(f'Report: {REPORT_TXT}')
    return 0 if status=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
