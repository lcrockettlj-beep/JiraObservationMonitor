from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def read_json(path: Path) -> dict:
    require(path.is_file(), f"contract exists: {path.relative_to(ROOT)}")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    require(isinstance(value, dict), f"contract is an object: {path.relative_to(ROOT)}")
    return value


def main() -> int:
    from app.web import app

    client = app.test_client()

    runtime_response = client.get("/api/system/runtime-dashboard")
    require(runtime_response.status_code == 200, "Runtime dashboard returns HTTP 200")
    runtime = runtime_response.get_json(silent=True)
    require(isinstance(runtime, dict), "Runtime dashboard returns a JSON object")
    require(runtime.get("schema") == "jom-runtime-operational-dashboard-v1", "Runtime dashboard schema is current")
    require(runtime.get("status") == "ok", "Runtime dashboard status is ok")

    summary = runtime.get("summary") if isinstance(runtime.get("summary"), dict) else {}
    outer_steps = runtime.get("outer_steps") if isinstance(runtime.get("outer_steps"), list) else []
    inner_steps = runtime.get("inner_steps") if isinstance(runtime.get("inner_steps"), list) else []

    require(len(outer_steps) == 3, "Canonical collection exposes exactly three outer collection steps")
    require(len(inner_steps) >= 17, "Admin authority chain exposes at least seventeen inner steps")
    require(summary.get("outer_steps") == len(outer_steps), "Outer-step summary reconciles with returned rows")
    require(summary.get("inner_steps") == len(inner_steps), "Inner-step summary reconciles with returned rows")
    require(summary.get("failed_steps") == 0, "Runtime dashboard reports zero failed steps")
    require(summary.get("blocked_steps") == 0, "Runtime dashboard reports zero blocked steps")
    require(summary.get("running") is False, "Canonical runtime refresh is not running")
    require(summary.get("outer_status") == "ok", "Canonical outer collection status is ok")
    require(summary.get("inner_status") == "ok", "Admin child-chain status is ok")

    outer_keys = [str(row.get("key") or "") for row in outer_steps if isinstance(row, dict)]
    require(outer_keys == ["site_registry", "product_access", "admin_enriched_chain"], "Canonical outer collection order is correct")

    inner_keys = {str(row.get("key") or "") for row in inner_steps if isinstance(row, dict)}
    require("estate_monitored_product_authority" in inner_keys, "Monitored Product Authority is present in the inner chain")

    source_response = client.get("/api/system/source-health-dashboard")
    require(source_response.status_code == 200, "Source Health dashboard returns HTTP 200")
    source = source_response.get_json(silent=True)
    require(isinstance(source, dict), "Source Health dashboard returns a JSON object")
    require(source.get("schema") == "jom-source-health-operational-dashboard-v1", "Source Health dashboard schema is current")

    freshness = read_json(ROOT / "runtime" / "data" / "source_freshness_audit.json")
    reliability = read_json(ROOT / "runtime" / "data" / "source_reliability_status.json")
    canonical = read_json(ROOT / "runtime" / "data" / "runtime_refresh_status.json")

    require(canonical.get("overall_status") == "ok", "Canonical runtime contract is finalized as ok")
    require(canonical.get("running") is False, "Canonical runtime contract is finalized and not running")
    require(bool(canonical.get("finished_at_utc")), "Canonical runtime contract includes a finish timestamp")

    freshness_summary = freshness.get("summary") if isinstance(freshness.get("summary"), dict) else {}
    require(freshness_summary.get("unknown_timestamp_count", 0) == 0, "Freshness has no unknown timestamp result")
    require(freshness_summary.get("in_progress_count", 0) == 0, "Freshness has no in-progress result after finalization")

    reliability_status = reliability.get("overall_status") or reliability.get("status")
    freshness_status = freshness.get("overall_state") or freshness.get("status")
    if str(freshness_status).lower() in {"attention", "review", "partial", "failed", "error", "unavailable"}:
        require(str(reliability_status).lower() != "ok", "Reliability does not suppress a non-healthy Freshness state")
    else:
        require(str(reliability_status).lower() in {"ok", "review", "attention", "partial"}, "Reliability publishes an accepted operational state")

    web_source = (ROOT / "app" / "web.py").read_text(encoding="utf-8-sig")
    js_source = (ROOT / "static" / "js" / "jom_system_truth_v1.js").read_text(encoding="utf-8-sig")
    template_sources = "\n".join(
        (ROOT / "templates" / name).read_text(encoding="utf-8-sig")
        for name in ("runtime_status.html", "source_health.html")
    )
    require("/api/system/runtime-dashboard" in web_source, "Runtime dashboard endpoint remains owned by app/web.py")
    require("/api/system/source-health-dashboard" in web_source, "Source Health endpoint remains owned by app/web.py")
    require("jom_system_truth_v1.js" in template_sources, "Runtime and Source Health templates retain the shared consumer")
    require("innerHTML" not in js_source, "Shared System Truth consumer does not use innerHTML")
    require("OAuth-backed" not in template_sources, "Legacy OAuth-backed placeholder wording remains removed")

    print("PASS: Runtime Status and Source Health UX validator aligned to the finalized three-step canonical collection architecture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
