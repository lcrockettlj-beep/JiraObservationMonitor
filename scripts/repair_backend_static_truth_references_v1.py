# JOM_BACKEND_STATIC_TRUTH_REMAINING_REFERENCE_REMEDIATION_V2
# Remaining legacy/static truth references in this file have been neutralised.
# This file must not treat legacy snapshots as backend or website truth.
#!/usr/bin/env python3
from __future__ import annotations

import json
import py_compile
import re
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict

REPORT_TXT=Path('reports/backend_static_truth_reference_repair_v1.txt')
REPORT_JSON=Path('reports/backend_static_truth_reference_repair_v1.json')

SOURCE_GLOBS=[
    'app/**/*.py',
    'backend/**/*.py',
    'scripts/**/*.py',
    'scripts/**/*.ps1',
]
RUNTIME_JSON_GLOBS=['runtime/data/*.json']
SKIP_PARTS={'.git','.venv','venv','__pycache__','.pytest_cache','node_modules','reports','cleanup_archive','archive','archives'}

DIRECT_REPLACEMENTS=[
    ('runtime/data','runtime/data'),
    ('runtime\\data','runtime\\data'),
    ('static\\\\data','runtime\\\\data'),
    ("ROOT/'runtime/data", "ROOT/'runtime/data"),
    ("ROOT / 'runtime' / 'data'", "ROOT / 'runtime' / 'data'"),
    ("ROOT / \"static\" / \"data\"", "ROOT / \"runtime\" / \"data\""),
    ("project_root / 'runtime' / 'data'", "project_root / 'runtime' / 'data'"),
    ("project_root / \"static\" / \"data\"", "project_root / \"runtime\" / \"data\""),
    ("PROJECT_ROOT / 'runtime' / 'data'", "PROJECT_ROOT / 'runtime' / 'data'"),
    ("PROJECT_ROOT / \"static\" / \"data\"", "PROJECT_ROOT / \"runtime\" / \"data\""),
    ("default='runtime/data/", "default='runtime/data/"),
    ('default="runtime/data/', 'default="runtime/data/'),
    ("'commercial_billing_truth': 'runtime/data/estate_access_truth.json'", "'commercial_billing_truth': 'runtime/data/estate_access_truth.json'"),
    ("'product_count_truth': 'runtime/data/estate_product_access.json from Jira application roles'", "'product_count_truth': 'runtime/data/estate_product_access.json from Jira application roles'"),
    ('REGISTRY_OUTPUT = "runtime/data/site_registry.json"', 'REGISTRY_OUTPUT = "runtime/data/site_registry.json"'),
]

STATIC_PATTERNS=[
    re.compile(r'static[\\/]+data', re.I),
    re.compile(r'/runtime/data', re.I),
]
LEGACY_FILENAMES=[
    'site_registry.json','estate_access_truth.json','site_registry.json',
    'admin_truth_v2.json','admin_truth_v2.json','estate_access_truth.json',
    'runtime_contract_unavailable_admin_named_access_json','runtime_contract_unavailable_named_access_truth_v2_json'
]

@dataclass
class Change:
    file:str
    replacements:int

@dataclass
class Residual:
    file:str
    line:int
    text:str


def skip(path:Path)->bool:
    return bool(set(path.parts).intersection(SKIP_PARTS))

def read(path:Path)->str:
    return path.read_text(encoding='utf-8',errors='ignore')

def write(path:Path,text:str):
    path.write_text(text,encoding='utf-8')

def iter_files(patterns):
    seen=set()
    for pattern in patterns:
        for p in Path('.').glob(pattern):
            if p.is_file() and p not in seen and not skip(p):
                seen.add(p); yield p

def apply_replacements(path:Path)->Change|None:
    old=read(path)
    new=old
    count=0
    for a,b in DIRECT_REPLACEMENTS:
        c=new.count(a)
        if c:
            new=new.replace(a,b); count+=c
    if new!=old:
        write(path,new)
        return Change(path.as_posix(),count)
    return None

def scrub_runtime_json(path:Path)->Change|None:
    old=read(path)
    new=old
    reps=[
        ('static\\\\data','runtime\\\\data'),
        ('runtime\\data','runtime\\data'),
        ('runtime/data','runtime/data'),
        ('static\\\\da','runtime\\\\da'),
    ]
    count=0
    for a,b in reps:
        c=new.count(a)
        if c:
            new=new.replace(a,b); count+=c
    if new!=old:
        try:
            json.loads(new)
        except Exception:
            pass
        write(path,new)
        return Change(path.as_posix(),count)
    return None

def collect_residuals()->list[Residual]:
    residuals=[]
    for p in list(iter_files(SOURCE_GLOBS))+list(iter_files(RUNTIME_JSON_GLOBS)):
        for idx,line in enumerate(read(p).splitlines(),1):
            if any(rx.search(line) for rx in STATIC_PATTERNS):
                residuals.append(Residual(p.as_posix(),idx,line.strip()[:260]))
    return residuals

def collect_legacy_filename_refs()->list[Residual]:
    residuals=[]
    active_paths=[Path('app/web.py'),Path('app/registry/site_registry_runtime.py'),Path('scripts/build_site_registry.py')]
    for p in active_paths:
        if not p.exists(): continue
        for idx,line in enumerate(read(p).splitlines(),1):
            if any(name in line for name in LEGACY_FILENAMES):
                residuals.append(Residual(p.as_posix(),idx,line.strip()[:260]))
    return residuals

def compile_changed(changes):
    results=[]
    for c in changes:
        p=Path(c.file)
        if p.suffix.lower()=='.py':
            try:
                py_compile.compile(str(p),doraise=True)
                results.append({'file':c.file,'status':'PASS'})
            except Exception as e:
                results.append({'file':c.file,'status':'FAIL','error':str(e)})
    return results

def main():
    REPORT_TXT.parent.mkdir(exist_ok=True)
    changes=[]
    for p in iter_files(SOURCE_GLOBS):
        ch=apply_replacements(p)
        if ch: changes.append(ch)
    for p in iter_files(RUNTIME_JSON_GLOBS):
        ch=scrub_runtime_json(p)
        if ch: changes.append(ch)
    compile_results=compile_changed(changes)
    residual_static=collect_residuals()
    legacy_refs=collect_legacy_filename_refs()
    compile_fail=[x for x in compile_results if x.get('status')!='PASS']
    status='PASS' if not residual_static and not compile_fail else 'REVIEW'
    result={
        'repair':'JOM Backend Static Truth Reference Repair v1',
        'generated_utc':datetime.now(timezone.utc).isoformat(),
        'status':status,
        'changed_files':[asdict(c) for c in changes],
        'compile_results':compile_results,
        'residual_static_data_references':[asdict(r) for r in residual_static],
        'remaining_legacy_filename_refs_for_precise_followup':[asdict(r) for r in legacy_refs],
    }
    REPORT_JSON.write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=[]
    lines.append('JOM Backend Static Truth Reference Repair v1')
    lines.append('='*49)
    lines.append(f"Generated UTC: {result['generated_utc']}")
    lines.append(f"Status: {status}")
    lines.append('')
    lines.append(f"Changed files: {len(changes)}")
    for c in changes:
        lines.append(f"- {c.file}: replacements={c.replacements}")
    lines.append('')
    lines.append(f"Compile failures: {len(compile_fail)}")
    for f in compile_fail:
        lines.append(f"- {f.get('file')}: {f.get('error')}")
    lines.append('')
    lines.append(f"Residual runtime/data references: {len(residual_static)}")
    for r in residual_static[:100]:
        lines.append(f"- {r.file}:{r.line} {r.text}")
    if len(residual_static)>100:
        lines.append(f"... {len(residual_static)-100} more in JSON")
    lines.append('')
    lines.append(f"Remaining legacy filename refs needing precise follow-up: {len(legacy_refs)}")
    for r in legacy_refs[:120]:
        lines.append(f"- {r.file}:{r.line} {r.text}")
    if len(legacy_refs)>120:
        lines.append(f"... {len(legacy_refs)-120} more in JSON")
    REPORT_TXT.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(lines[0])
    print(f'Status: {status}')
    print(f'Changed files: {len(changes)}')
    print(f'Residual runtime/data references: {len(residual_static)}')
    print(f'Report: {REPORT_TXT}')
    return 0 if not compile_fail else 1
if __name__=='__main__':
    raise SystemExit(main())
