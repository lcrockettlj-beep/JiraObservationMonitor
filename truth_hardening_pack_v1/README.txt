TRUTH HARDENING PACK V1

Apply steps:

1. Place core_truth_guard.js in:
   static/js/

2. Add to all HTML pages inside <head>:
   <script src="/static/js/core_truth_guard.js"></script>

3. Replace all Number(value || 0) patterns with TruthGuard.safeNumber(value)

4. Remove ALL fallback renders returning 0 values

5. Add 'DATA UNAVAILABLE' display when fetch fails

6. Add source labels to panels:
   - runtime
   - snapshot
   - latest run

RESULT:
- No fake data
- No silent fallback
- Full traceable truth
