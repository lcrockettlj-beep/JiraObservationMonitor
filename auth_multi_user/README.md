\# auth/multi\_user â€” Phase 2 Scaffolding



\*\*Status:\*\* Dormant â€” Phase 2 only  

\*\*Phase 1 impact:\*\* None  

\*\*Activation:\*\* Requires senior management approval



\---



\## What this is



This folder contains skeleton modules for the \*\*future Phase 2 multi-user expansion\*\* of JOM. None of the code in this folder is active in Phase 1. The folder exists as architectural scaffolding to make a future Phase 2 activation faster, safer, and reviewable.



If you are a developer reading this for the first time, \*\*you do not need to engage with this folder to operate JOM\*\*. The platform runs entirely on its Phase 1 code paths. This folder is here for the future.



\---



\## What you'll find here



| File | Purpose | Status |

|------|---------|--------|

| `\_\_init\_\_.py` | Package marker, safety contract | Dormant |

| `sso\_handler.py` | Microsoft Entra ID OAuth handler | Skeleton |

| `user\_allowlist.py` | User access allow-list management | Skeleton |

| `access\_audit.py` | Access event logging | Skeleton |

| `README.md` | This document | Documentation |



\---



\## How the safety model works



Every callable function in this folder begins with:



```python

from config.feature\_flags import is\_enabled



if not is\_enabled("multi\_user.enabled"):

&#x20;   raise RuntimeError(

&#x20;       "multi\_user.enabled is False â€” refusing to run in Phase 1"

&#x20;   )


