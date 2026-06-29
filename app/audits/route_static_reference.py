
from __future__ import annotations
import json,re
from collections import defaultdict,Counter
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT_JSON=ROOT/'reports'/'route_static_reference_validation.json'
OUT_MD=ROOT/'reports'/'route_static_reference_validation.md'
SKIP={'.git','__pycache__','.venv','venv','node_modules'}
REVIEW_FILES=[
 'static/css/named_access_dashboard.css',
 'static/js/named_access_dashboard.js',
 'static/js/runtime_template_metrics.js',
 'static/css/site_registry_layout_enforcer.css',
 'static/js/site_registry_layout_enforcer.js',
 'templates/admin.html',
 'templates/site.html',
]

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def rel(p): return p.relative_to(ROOT).as_posix()
def read(p):
    try: return p.read_text(encoding='utf-8',errors='replace')
    except Exception: return ''
def files():
    return sorted([p for p in ROOT.rglob('*') if p.is_file() and not any(part in SKIP for part in p.parts)], key=lambda p:rel(p))
def route_map():
    web=ROOT/'web.py'; text=read(web); routes=[]
    for m in re.finditer(r"@app\.route\(['\"]([^'\"]+)['\"]", text):
        start=m.start(); tail=text[start:start+900]
        tm=re.search(r"render_template\(['\"]([^'\"]+)['\"]", tail)
        routes.append({'route':m.group(1),'template':tm.group(1) if tm else None})
    return routes
def references_for(target, all_files):
    target_norm=target.replace('static/','/static/').replace('templates/','')
    names=set([target, target.replace('static/',''), target.replace('templates/',''), '/'+target, target_norm, Path(target).name])
    refs=[]
    for p in all_files:
        if rel(p)==target: continue
        if p.suffix.lower() not in {'.py','.html','.js','.css','.ps1','.cmd','.md','.txt'}: continue
        txt=read(p)
        hits=[n for n in names if n and n in txt]
        if hits:
            refs.append({'source':rel(p),'matched':sorted(set(hits))})
    return refs
def classify(target, exists, refs, routes):
    if not exists: return 'MISSING_REVIEW','File listed for review but does not exist.'
    if target.startswith('templates/'):
        tmpl=target.replace('templates/','')
        route_hits=[r for r in routes if r.get('template')==tmpl]
        if route_hits: return 'ROUTE_ACTIVE','Template is directly rendered by web.py route(s).'
        if refs: return 'REFERENCED_REVIEW','Template is referenced indirectly; inspect before moving.'
        return 'UNREFERENCED_REVIEW','No route/static reference found; candidate for archive after approval.'
    if refs: return 'REFERENCED_ACTIVE_OR_REVIEW','Static file is referenced by runtime/template/script; inspect role before moving.'
    return 'UNREFERENCED_REVIEW','No static reference found; candidate for archive after approval.'
def main():
    all_files=files(); routes=route_map(); rows=[]
    for t in REVIEW_FILES:
        p=ROOT/t; refs=references_for(t, all_files); status,reason=classify(t,p.exists(),refs,routes)
        rows.append({'file':t,'exists':p.exists(),'status':status,'reason':reason,'reference_count':len(refs),'references':refs[:50],'route_hits':[r for r in routes if r.get('template')==t.replace('templates/','')]})
    summary={'review_files':len(rows),'status_counts':dict(Counter(r['status'] for r in rows)),'routes_found':len(routes)}
    payload={'schema':'jom-route-static-reference-validation-v1','generated_at_utc':now(),'mode':'report-only-no-changes','summary':summary,'routes':routes,'review_files':rows}
    OUT_JSON.parent.mkdir(parents=True,exist_ok=True); OUT_JSON.write_text(json.dumps(payload,indent=2),encoding='utf-8')
    lines=['# Route and Static Reference Validation','',f"Generated: `{payload['generated_at_utc']}`",'', '## Summary','']
    for k,v in summary.items(): lines.append(f'- {k}: **{v}**')
    lines += ['', '## Review Files','']
    for r in rows:
        lines.append(f"- `{r['status']}` / `{r['file']}` — {r['reason']} References: {r['reference_count']}")
    OUT_MD.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'status':'ok','review_files':len(rows),'status_counts':summary['status_counts'],'json':str(OUT_JSON),'report':str(OUT_MD)},indent=2))
if __name__=='__main__': main()
