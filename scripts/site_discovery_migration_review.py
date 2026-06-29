from __future__ import annotations
import ast,json,subprocess,re
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT_JSON=ROOT/'reports'/'site_discovery_migration_review.json'
OUT_MD=ROOT/'reports'/'site_discovery_migration_review.md'
CANDIDATES=['site_discovery.py','backend/site_registry_runtime.py','app/registry/site_registry_runtime.py','app/registry/site_registry_builder.py','scripts/build_site_registry.py','web.py','config/monitored_sites.json','static/data/site_registry.json']
SKIP={'.git','__pycache__','.venv','venv','node_modules'}
def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def rel(p): return p.relative_to(ROOT).as_posix()
def read(p):
    try: return p.read_text(encoding='utf-8',errors='replace')
    except Exception: return ''
def git(args):
    try:
        p=subprocess.run(['git']+args,cwd=ROOT,capture_output=True,text=True,timeout=60)
        return {'returncode':p.returncode,'stdout':p.stdout.strip(),'stderr':p.stderr.strip()}
    except Exception as e: return {'error':str(e)}
def parse_py(p):
    text=read(p); imports=[]; funcs=[]; classes=[]; errs=[]
    if p.suffix.lower()=='.py':
        try:
            tree=ast.parse(text)
            for n in ast.walk(tree):
                if isinstance(n,ast.Import): imports += [a.name for a in n.names]
                elif isinstance(n,ast.ImportFrom) and n.module: imports.append(n.module)
                elif isinstance(n,ast.FunctionDef): funcs.append(n.name)
                elif isinstance(n,ast.ClassDef): classes.append(n.name)
        except Exception as e: errs.append(str(e))
    hints=[]
    for t in ['site_registry','monitored_sites','cloud_id','discovered','approved','onboarding','Atlassian','admin','runtime','product_access','named_access']:
        if t in text: hints.append(t)
    root=[]
    if 'parents[1]' in text: root.append('parents[1]')
    if 'parents[2]' in text: root.append('parents[2]')
    return {'imports':sorted(set(imports)),'functions':funcs[:80],'classes':classes,'parse_errors':errs,'hints':sorted(set(hints)),'root_patterns':root,'line_count':len(text.splitlines())}
def refs_for(name):
    refs=[]; base=Path(name).name; dotted=name.replace('/', '.').replace('\\','.').replace('.py','')
    tokens={name,name.replace('/','\\'),base,dotted}
    for p in ROOT.rglob('*'):
        if not p.is_file() or any(x in SKIP for x in p.parts): continue
        if p.suffix.lower() not in {'.py','.html','.js','.css','.ps1','.cmd','.md','.txt','.json'}: continue
        rp=rel(p)
        if rp==name: continue
        text=read(p); hits=[t for t in tokens if t and t in text]
        if hits: refs.append({'source':rp,'matched':sorted(set(hits))})
    return refs[:100]
def read_json(p):
    try: return json.loads(read(p))
    except Exception as e: return {'_read_error':str(e)}
def monitored_scope():
    reg=read_json(ROOT/'static/data/site_registry.json'); monitored=[]; discovered=[]
    if isinstance(reg,dict):
        for s in reg.get('sites',[]):
            if not isinstance(s,dict): continue
            key=s.get('site_key') or s.get('key') or s.get('site')
            if s.get('is_monitored') is True or s.get('classification')=='monitored': monitored.append(key)
            elif s.get('classification')=='discovered': discovered.append(key)
    return {'monitored':sorted([x for x in monitored if x]),'discovered':sorted([x for x in discovered if x])}
def row(c):
    p=ROOT/c
    return {'file':c,'exists':p.exists(),'recommended_target':('app/registry/site_discovery.py' if c=='site_discovery.py' else c),'risk':('review_hybrid_collector_registry' if c=='site_discovery.py' else 'context'),'analysis':parse_py(p) if p.exists() else {},'reference_count':len(refs_for(c)) if p.exists() else 0,'references':refs_for(c) if p.exists() else []}
def write_md(payload):
    lines=['# Site Discovery Migration Review','',f"Generated: `{payload['generated_at_utc']}`",'','## Mode','','Report-only. No files were moved.','','## Summary','']
    for k,v in payload['summary'].items(): lines.append(f'- {k}: **{v}**')
    lines+=['','## Recommendation','','Do not move `site_discovery.py` yet unless references and collector responsibilities are explicitly approved. Treat it as a registry/collector hybrid.','','## Candidate Review','']
    for r in payload['candidates']: lines.append(f"- `{r['file']}` → `{r['recommended_target']}` | risk `{r['risk']}` | refs `{r['reference_count']}`")
    lines+=['','## Safety Rules','']
    for s in payload['safety_rules']: lines.append(f'- {s}')
    OUT_MD.parent.mkdir(parents=True,exist_ok=True); OUT_MD.write_text('\n'.join(lines)+'\n',encoding='utf-8')
def main():
    candidates=[row(c) for c in CANDIDATES]
    payload={'schema':'jom-site-discovery-migration-review-v1','generated_at_utc':now(),'mode':'report-only-no-file-moves','summary':{'candidate_count':len(candidates),'existing_count':sum(1 for x in candidates if x['exists']),'git_status_short':git(['status','--short']).get('stdout'),'monitored_scope':monitored_scope()},'candidates':candidates,'recommendation':{'next_action':'Do not move site_discovery.py yet. If continuing, build Site Discovery Migration Pack v1 only after reviewing references and deciding whether target is app/registry or app/collectors.','preferred_target':'app/registry/site_discovery.py only if treated as registry classification/onboarding logic; app/collectors/site_discovery.py if it performs external source collection.'},'safety_rules':['Do not change config/monitored_sites.json path.','Do not change static/data/site_registry.json path.','Do not approve discovered sites during migration.','Keep monitored scope unchanged: gli-it-project, gli-global-technology, gli-delivery-tm.','If moved, leave root site_discovery.py as compatibility shim until imports are updated.']}
    OUT_JSON.parent.mkdir(parents=True,exist_ok=True); OUT_JSON.write_text(json.dumps(payload,indent=2),encoding='utf-8'); write_md(payload)
    print(json.dumps({'status':'ok','mode':payload['mode'],'json':str(OUT_JSON),'report':str(OUT_MD),'next_action':payload['recommendation']['next_action']},indent=2))
if __name__=='__main__': main()
