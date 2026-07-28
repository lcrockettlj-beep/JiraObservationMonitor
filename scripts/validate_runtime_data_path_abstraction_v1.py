from __future__ import annotations
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def fail(msg: str):
    print("FAIL: " + msg)
    raise SystemExit(1)

def main():
    if not (ROOT / "app/runtime/runtime_data_paths.py").exists():
        fail("runtime data path module missing")
    if not (ROOT / "runtime/data").exists():
        fail("runtime/data missing")
    web = (ROOT / "app/web.py").read_text(encoding="utf-8", errors="replace")
    for term in ["runtime_read_json", "runtime_write_json", "/api/runtime/data-path-status"]:
        if term not in web:
            fail(term + " missing from app/web.py")
    bad = []
    jsdir = ROOT / "static/js"
    if jsdir.exists():
        for js in jsdir.glob("*.js"):
            s = js.read_text(encoding="utf-8", errors="replace")
            if "/static/data/" in s:
                bad.append(str(js.relative_to(ROOT)))
    if bad:
        fail("frontend static fetches remain: " + ", ".join(bad))
    print("Runtime data path abstraction validation PASS")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
