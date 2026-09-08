from pathlib import Path
import re, sys
root=Path(__file__).resolve().parents[1]
checks=[]
def need(path,terms):
    text=(root/path).read_text(encoding='utf-8-sig')
    for term in terms: checks.append((f'{path}: {term}',term in text))
need(Path('templates/site_workspace.html'),['workspace-project-panel','workspace-project-rows','workspace-source-projects','Marketplace apps</dt><dd>Unavailable','Automation</dt><dd>Unavailable'])
need(Path('static/js/jom_site_workspace_shell_v1.js'),['/api/governance/projects','/api/governance/projects/leads','/api/governance/projects/owners','Project authorities are not synchronized','norm(row.site_key)===wanted'])
need(Path('static/css/jom_site_workspace_shell_v1.css'),['JOM_SITE_WORKSPACE_PROJECT_AUTHORITY_INTEGRATION_V1','site-workspace-state--ok','site-workspace-state--gap'])
web=(root/'app/web.py').read_text(encoding='utf-8-sig')
for route in ['/api/governance/projects','/api/governance/projects/leads','/api/governance/projects/owners']:
    checks.append((f'app/web.py existing route: {route}',route in web))
failed=[name for name,ok in checks if not ok]
for name,ok in checks: print(('PASS' if ok else 'FAIL')+': '+name)
if failed: print(f'VALIDATION FAILED: {len(failed)}');sys.exit(1)
print('VALIDATION PASS: Site Workspace project authority integration owner boundary.')
