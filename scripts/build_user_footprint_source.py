from __future__ import annotations

from _project_bootstrap import ensure_project_root_on_path
ensure_project_root_on_path()

from app.access.user_footprint_source import main


if __name__ == "__main__":
    raise SystemExit(main())
