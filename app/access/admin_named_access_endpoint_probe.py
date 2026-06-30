from __future__ import annotations
import argparse, json, os, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

API_HOST='https://api.atlassian.com/admin'

def utc_now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')

def load_env(root: Path)->Dict[str,str]:
    env=dict(os.environ); p=root/'.env'
    if p.exists():
        for raw in p.read_text(encoding='utf-8').splitlines():
            line=raw.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k,v=line.split('=',1); env[k.strip()]=v.strip().strip('"').strip("'")
    return env

def read_json(p: Path)->Dict[str,Any]:
    if not p.exists(): return {}
    try:
        x=json.loads(p.read_text(encoding='utf-8'))
        return x if isinstance(x,dict) else {}
    except Exception: return {}

def write_json(p: Path, payload: Dict[str,Any]):
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding='utf-8')

def req(method: str, url: str, token: str, body: Optional[Dict[str,Any]]=None)->Dict[str,Any]:
    data=None
    headers={'Authorization':f'Bearer {token}','Accept':'application/json'}
    if body is not None:
        data=json.dumps(body).encode('utf-8'); headers['Content-Type']='application/json'
    r=urllib.request.Request(url=url,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(r,timeout=45) as resp:
            raw=resp.read().decode('utf-8')
            parsed=json.loads(raw) if raw else {}
            return {'ok':True,'status':resp.status,'url':url,'method':method,'json':parsed}
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8',errors='ignore')
        return {'ok':False,'status':e.code,'url':url,'method':method,'body':raw[:4000]}
    except Exception as e:
        return {'ok':False,'status':0,'url':url,'method':method,'body':str(e)}

def get_first(row:Dict[str,Any], names:List[str])->str:
    folded={str(k).lower().replace(' ','_').replace('-','_'):v for k,v in row.items()}
    for name in names:
        if row.get(name): return str(row.get(name)).strip()
        v=folded.get(name.lower().replace(' ','_').replace('-','_'))
        if v: return str(v).strip()
    return ''

def drill_rows(payload:Dict[str,Any],key:str)->List[Dict[str,Any]]:
    rows=((payload.get('drilldowns') or {}).get(key) or {}).get('rows') or []
    return [r for r in rows if isinstance(r,dict)] if isinstance(rows,list) else []

def human_users(root:Path, limit:int)->List[Dict[str,Any]]:
    for n in ['latest_run_admin_enriched_pretty.json','latest_run_admin_enriched.json','latest_run_pretty.json','latest_run.json']:
        payload=read_json(root/n)
        if not payload: continue
        rows=drill_rows(payload,'admin::human_accounts')
        out=[]; seen=set()
        for r in rows:
            aid=get_first(r,['account_id','accountId','Atlassian ID','User id','id'])
            email=get_first(r,['email','Email','emailAddress'])
            key=aid or email
            if key and key not in seen:
                seen.add(key); out.append({'account_id':aid,'email':email})
        if out: return out[:limit]
    return []

def extract_data_list(x:Any)->List[Dict[str,Any]]:
    if isinstance(x,dict):
        for k in ['data','values','directories','workspaces']:
            if isinstance(x.get(k),list): return [i for i in x[k] if isinstance(i,dict)]
    if isinstance(x,list): return [i for i in x if isinstance(i,dict)]
    return []

def ids_from(items:List[Dict[str,Any]], names:List[str])->List[str]:
    out=[]
    for item in items:
        for n in names:
            v=item.get(n)
            if v and str(v) not in out: out.append(str(v))
    return out

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--project-root',default='.')
    ap.add_argument('--sample-users',type=int,default=3)
    args=ap.parse_args(); root=Path(args.project_root).resolve(); env=load_env(root)
    org=env.get('ATLASSIAN_ADMIN_ORG_ID','').strip(); token=env.get('ATLASSIAN_ADMIN_API_KEY','').strip()
    if not org or not token: raise SystemExit('Missing ATLASSIAN_ADMIN_ORG_ID or ATLASSIAN_ADMIN_API_KEY')
    users=human_users(root,args.sample_users)
    probes=[]
    def add(name,method,path,body=None):
        res=req(method,f'{API_HOST}{path}',token,body); res['name']=name; probes.append(res); return res
    org_v1=add('v1 org details','GET',f'/v1/orgs/{org}')
    org_users=add('v1 org users page','GET',f'/v1/orgs/{org}/users?limit=5')
    directories=add('v2 directories','GET',f'/v2/orgs/{org}/directories?limit=20')
    workspaces=add('v2 workspaces','POST',f'/v2/orgs/{org}/workspaces',{})
    directory_ids=ids_from(extract_data_list(directories.get('json')),['id','directoryId','directory_id'])
    if not directory_ids:
        # Also inspect workspace directory field if directories call shape differs or is unavailable.
        for w in extract_data_list(workspaces.get('json')):
            d=w.get('directory')
            if isinstance(d,dict):
                v=d.get('id') or d.get('directoryId')
            else:
                v=d
            if v and str(v) not in directory_ids: directory_ids.append(str(v))
    for d in directory_ids[:3]:
        add(f'v2 directory users {d}','GET',f'/v2/orgs/{org}/directories/{d}/users?limit=5')
        add(f'v2 directory groups {d}','GET',f'/v2/orgs/{org}/directories/{d}/groups?limit=5')
        for u in users[:2]:
            aid=u.get('account_id')
            if aid:
                add(f'v2 role assignments user {aid} dir {d}','GET',f'/v2/orgs/{org}/directories/{d}/users/{aid}/role-assignments?limit=20')
    for u in users[:3]:
        aid=u.get('account_id')
        if aid:
            add(f'v1 last active {aid}','GET',f'/v1/orgs/{org}/directory/users/{aid}/last-active-dates')
    summary={
        'generated_at_utc':utc_now(),
        'org_id_present':bool(org),
        'sample_user_count':len(users),
        'directory_ids_discovered':directory_ids,
        'successful_probe_count':sum(1 for p in probes if p.get('ok')),
        'failed_probe_count':sum(1 for p in probes if not p.get('ok')),
        'candidate_next_step':'Use successful v2 directory/role assignment or last-active response shape to build verified named access collector.'
    }
    payload={'schema':'jom-admin-named-access-endpoint-probe','summary':summary,'sample_users':users,'probes':probes}
    out=root/'reports/admin_named_access_endpoint_probe.json'; write_json(out,payload)
    md=root/'reports/admin_named_access_endpoint_probe.md'
    lines=['# Admin Named Access Endpoint Probe','',f"Generated: `{summary['generated_at_utc']}`",'',f"Successful probes: **{summary['successful_probe_count']}**",f"Failed probes: **{summary['failed_probe_count']}**",f"Directory IDs discovered: `{', '.join(directory_ids) if directory_ids else 'none'}`",'','## Probe Results','']
    for p in probes:
        lines.append(f"- {'✅' if p.get('ok') else '❌'} **{p.get('name')}** — {p.get('method')} {p.get('url')} — HTTP {p.get('status')}")
    md.write_text('\n'.join(lines),encoding='utf-8')
    print('Endpoint probe complete.')
    print(json.dumps(summary,indent=2))
    print(f'JSON: {out}')
    print(f'Report: {md}')
    return 0
if __name__=='__main__': raise SystemExit(main())
