from __future__ import annotations

from _project_bootstrap import ensure_project_root_on_path
ensure_project_root_on_path()

from app.runtime.runtime_sources_refresh import main


if __name__ == "__main__":
    raise SystemExit(main())
