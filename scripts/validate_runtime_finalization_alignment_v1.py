from pathlib import Path
import ast,sys
R=Path(__file__).resolve().parents[1];files=[R/'app/runtime/runtime_sources_refresh.py',R/'scripts/audit_source_freshness.py',R/'app/audits/source_reliability.py'];bad=[]
for p in files:
 try:ast.parse(p.read_text(encoding='utf-8'));print('PASS syntax:',p.relative_to(R))
 except Exception as e:bad.append(str(e));print('FAIL syntax:',e)
o,f,s=[p.read_text(encoding='utf-8') for p in files]
checks={'canonical finalized before freshness':o.index("finished_at_utc=finished")<o.index("'source_freshness_final'"),'no full collection rerun':o.count("app.runtime.admin_enriched_chain")==1,'final health assessment present':'final_health_assessment' in o,'in progress distinct':'IN_PROGRESS' in f and 'UNKNOWN_TIMESTAMP' in f,'freshness compatibility fields':"'state':state" in f and "'freshness_state':state" in f,'reliability propagates attention':"overall='attention' if fo=='ATTENTION'" in s,'reliability reads new state':"src.get('state') or src.get('freshness_state')" in s,'atomic outputs':"with_suffix('.json.tmp')" in f and "with_suffix('.json.tmp')" in s}
for n,v in checks.items():print(('PASS' if v else 'FAIL')+': '+n);bad.extend([] if v else [n])
if bad:sys.exit(1)
print('PASS: Runtime Finalization Alignment v1 static validation')
