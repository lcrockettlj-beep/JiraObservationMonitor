from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
web=(ROOT/'app/web.py').read_text(encoding='utf-8-sig')
failed=[]
def check(label,ok):
 print(('PASS' if ok else 'FAIL')+': '+label)
 if not ok: failed.append(label)
check('Response imported globally','from flask import Flask, jsonify, render_template, send_from_directory, request, redirect, Response' in web[:500])
for route in ['/api/estate/admin-site-inventory','/api/estate/discovery-authority','/api/estate/discovery-authority/coverage']:
 check('route retained: '+route,route in web)
check('inventory endpoint retains JSON Response','return Response(json.dumps(data, indent=2), mimetype="application/json")' in web)
check('two Response-backed authority endpoints retained',web.count('return Response(json.dumps(data, indent=2), mimetype="application/json")')>=2)
try:
 compile(web,str(ROOT/'app/web.py'),'exec'); compiled=True
except Exception as exc:
 print('COMPILE ERROR: '+str(exc)); compiled=False
check('app/web.py compiles',compiled)
if failed: print('VALIDATION FAILED: '+str(len(failed)));sys.exit(1)
print('VALIDATION PASS: Discovery and Admin Site Inventory Response import correction is present.')
