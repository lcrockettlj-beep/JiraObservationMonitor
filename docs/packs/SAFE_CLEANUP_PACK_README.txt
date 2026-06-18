Safe Cleanup Pack
=================

Purpose:
Safely reduce clutter without risking the working build.

Files:
- safe_cleanup_preview.ps1 -> project root
- safe_cleanup_apply.ps1 -> project root
- SAFE_CLEANUP_PACK_README.txt -> project root

Strategy:
- preview first
- move candidates into a quarantine folder instead of deleting outright
- keep all active runtime/auth/web files untouched

Recommended use:
1. Preview:
   powershell -ExecutionPolicy Bypass -File .\safe_cleanup_preview.ps1
2. Apply (moves candidates to _cleanup_quarantine\TIMESTAMP):
   powershell -ExecutionPolicy Bypass -File .\safe_cleanup_apply.ps1
3. Review quarantine folder before deleting permanently.
