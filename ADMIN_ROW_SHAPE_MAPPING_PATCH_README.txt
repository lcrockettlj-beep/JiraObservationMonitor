Admin Row-Shape Mapping Patch
=============================

Purpose:
Adapt the admin enrichment and runtime adapter to the REAL admin row-shape currently returned by the Atlassian Admin API, which exposes fields such as:
- accountId
- accountType
- accountStatus
- statusInUserbase

This patch does NOT assume claimStatus/platformRoles/mfaEnabled are always present.

Files in this patch:
- admin_api_enrichment.py -> project root
- runtime_source_adapter.py -> backend/runtime_source_adapter.py
- ADMIN_ROW_SHAPE_MAPPING_PATCH_README.txt -> project root

What changes:
1. managed_user_count now falls back to human Atlassian accounts (accountType=atlassian) when claimStatus is absent.
2. New breakdown signals are included:
   - human_user_count
   - app_account_count
   - not_in_userbase_count
3. New drilldowns are added:
   - admin::human_accounts
   - admin::app_accounts
   - admin::not_in_userbase
4. admin::org_admins and admin::mfa_disabled now show explanatory note rows when those fields are unavailable in the payload instead of appearing mysteriously empty.
5. backend/runtime_source_adapter.py maps managed_row_count using accountType fallback when claimStatus is absent.

Run order after replacing files:
1. python admin_api_enrichment.py
2. python web.py
3. Check:
   http://127.0.0.1:5000/api/source-state
   http://127.0.0.1:5000/api/data

Expected improvement:
- users_row_count remains > 0
- managed_row_count becomes > 0 (best-available approximation using accountType=atlassian when claimStatus is absent)
- admin drilldowns no longer show misleading empty arrays where the source payload lacks those fields.
