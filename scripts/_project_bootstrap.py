from __future__ import annotations

import sys
from pathlib import Path


def ensure_project_root_on_path() -> str:
    """Ensure the JiraObservationMonitor project root is available on sys.path.

    Scripts inside ./scripts are often executed directly, which makes Python put
    ./scripts first on sys.path and can hide root-level modules such as
    jira_client.py, auth.py, data_collector.py, etc.
    """
    root = Path(__file__).resolve().parents[1]
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    return root_text
