from __future__ import annotations

from _project_bootstrap import ensure_project_root_on_path
ensure_project_root_on_path()

import runpy


if __name__ == "__main__":
    runpy.run_module("app.registry.site_registry_builder", run_name="__main__")
