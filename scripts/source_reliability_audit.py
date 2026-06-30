from __future__ import annotations

from _project_bootstrap import ensure_project_root_on_path
ensure_project_root_on_path()

from app.audits.source_reliability import main
from app.audits.source_reliability_advisory import align_source_reliability


if __name__ == "__main__":
    result = main()
    align_source_reliability()
    raise SystemExit(result if isinstance(result, int) else 0)
