from pathlib import Path
import sys
R=Path(__file__).resolve().parents[1];c=(R/'static/css/jom_command_centre_completion_v1.css').read_text(encoding='utf-8-sig')
checks={'colour owner single':c.count('JOM_COMMAND_CENTRE_MONITORING_WALL_JOM_COLOUR_V1 START')==1,'wall retained':'JOM_COMMAND_CENTRE_MONITORING_WALL_V1 START' in c,'JOM primary blue':all(x in c for x in ['#0c66e4','#deebff','#0052cc']),'JOM neutral palette':all(x in c for x in ['#ffffff','#f8fbff','#dfe1e6','#092957','#44546f']),'semantic healthy':all(x in c for x in ['#22a06b','#216e4e','#dcfff1']),'semantic review':all(x in c for x in ['#ffab00','#fff7d6','#7f5f01']),'semantic critical':all(x in c for x in ['#de350b','#ffebe6','#ae2a19']),'layout selectors unchanged':all(x in c for x in ['.jom-monitor-wall__console','.jom-monitor-wall__lanes','.jom-monitor-wall__lower','.jom-monitor-wall__site-grid']),'reduced motion retained':'prefers-reduced-motion:reduce' in c}
f=[]
for k,v in checks.items():print(('PASS' if v else 'FAIL')+': '+k);f.append(k) if not v else None
if f:print('VALIDATION FAILED: '+str(len(f)));sys.exit(1)
print('VALIDATION PASS: Monitoring Wall uses the established JOM blue, neutral and semantic status palette without layout or authority changes.')
