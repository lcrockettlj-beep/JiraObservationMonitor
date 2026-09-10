from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def read_text(relative_path: str) -> str:
    path = ROOT / relative_path
    require(path.is_file(), f"owner exists: {relative_path}")
    return path.read_text(encoding="utf-8-sig")


def read_json(relative_path: str) -> dict:
    path = ROOT / relative_path
    require(path.is_file(), f"contract exists: {relative_path}")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    require(isinstance(value, dict), f"contract is a JSON object: {relative_path}")
    return value


def step_key(row: object) -> str:
    if not isinstance(row, dict):
        return ""
    return str(row.get("key") or row.get("name") or row.get("step") or "")


def main() -> int:
    outer_source = read_text("app/runtime/runtime_sources_refresh.py")
    inner_source = read_text("app/runtime/admin_enriched_chain.py")

    collection_markers = ["site_registry", "product_access", "admin_enriched_chain"]
    collection_positions = [outer_source.index(marker) for marker in collection_markers]
    require(
        collection_positions == sorted(collection_positions),
        "Canonical collection owner preserves Site Registry, Product Access, Admin chain order",
    )

    freshness_markers = [
        marker for marker in ("source_freshness_final", "source_freshness")
        if marker in outer_source
    ]
    reliability_markers = [
        marker for marker in ("source_reliability_final", "source_reliability")
        if marker in outer_source
    ]
    require(bool(freshness_markers), "Runtime owner contains a final Freshness assessment")
    require(bool(reliability_markers), "Runtime owner contains a final Reliability assessment")
    freshness_position = max(outer_source.index(marker) for marker in freshness_markers)
    reliability_position = max(outer_source.index(marker) for marker in reliability_markers)
    require(
        collection_positions[-1] < freshness_position < reliability_position,
        "Final health assessments follow canonical collection in Freshness then Reliability order",
    )

    finish_markers = [
        marker for marker in ("finished_at_utc", "canonical_collection_finished_at_utc")
        if marker in outer_source
    ]
    require(bool(finish_markers), "Runtime owner records canonical completion evidence")
    require(
        any(outer_source.index(marker) < freshness_position for marker in finish_markers),
        "Canonical completion evidence is written before final Freshness assessment",
    )

    require(
        outer_source.count("admin_enriched_chain") >= 1,
        "Admin refresh has one canonical collection owner reference",
    )
    require(
        "estate_monitored_product_authority" in inner_source,
        "Monitored Product Authority remains integrated in the Admin chain",
    )
    require(
        "estate_resource_authority" in inner_source,
        "Monitored Product Authority dependency owner remains present",
    )

    runtime = read_json("runtime/data/runtime_refresh_status.json")
    admin = read_json("runtime/data/admin_enriched_refresh_status.json")
    freshness = read_json("runtime/data/source_freshness_audit.json")
    reliability = read_json("runtime/data/source_reliability_status.json")
    monitored_products = read_json("runtime/data/estate_monitored_product_authority_v1.json")

    require(runtime.get("overall_status") == "ok", "Canonical runtime status is finalized as ok")
    require(runtime.get("running") is False, "Canonical runtime status is not running")
    require(bool(runtime.get("finished_at_utc")), "Canonical runtime status includes a finish timestamp")

    outer_steps = runtime.get("steps") if isinstance(runtime.get("steps"), list) else runtime.get("outer_steps")
    require(isinstance(outer_steps, list), "Canonical runtime contract exposes collection steps")
    outer_keys = [step_key(row) for row in outer_steps]
    require(
        outer_keys == collection_markers,
        "Runtime contract exposes exactly the three canonical collection steps in order",
    )
    require(
        all(
            isinstance(row, dict)
            and str(row.get("status") or "").lower() == "ok"
            for row in outer_steps
        ),
        "All canonical collection steps completed successfully",
    )

    inner_steps = admin.get("steps") if isinstance(admin.get("steps"), list) else admin.get("inner_steps")
    require(isinstance(inner_steps, list), "Admin refresh contract exposes inner steps")
    inner_keys = [step_key(row) for row in inner_steps]
    require(len(inner_steps) >= 17, "Admin refresh contract exposes at least seventeen inner steps")
    require(
        "estate_monitored_product_authority" in inner_keys,
        "Monitored Product Authority executed in the Admin refresh",
    )
    require(
        all(
            isinstance(row, dict)
            and str(row.get("status") or "").lower()
            not in {"failed", "blocked", "missing", "exception"}
            for row in inner_steps
        ),
        "Admin refresh has no failed, blocked, missing, or exception step",
    )

    runtime_execution_id = runtime.get("execution_id")
    admin_execution_id = admin.get("execution_id")
    admin_parent_execution_id = admin.get("parent_execution_id")
    require(bool(runtime_execution_id), "Canonical runtime execution ID is present")
    require(bool(admin_execution_id), "Canonical Admin child execution ID is present")
    require(
        runtime.get("execution_scope") == "canonical_runtime_refresh",
        "Runtime execution scope is canonical_runtime_refresh",
    )
    require(
        admin.get("execution_scope") == "canonical_runtime_refresh_child",
        "Admin execution scope is canonical_runtime_refresh_child",
    )
    require(
        admin_execution_id == runtime_execution_id,
        "Admin child execution ID matches the canonical runtime execution ID",
    )
    require(
        runtime.get("parent_execution_id") is None,
        "Canonical runtime execution has no parent execution ID",
    )
    require(
        admin_parent_execution_id == runtime_execution_id,
        "Admin child parent execution ID matches the canonical runtime execution ID",
    )

    freshness_summary = freshness.get("summary") if isinstance(freshness.get("summary"), dict) else {}
    require(
        freshness_summary.get("unknown_timestamp_count", 0) == 0,
        "Freshness has no unknown timestamp result after finalization",
    )
    require(
        freshness_summary.get("in_progress_count", 0) == 0,
        "Freshness has no in-progress result after finalization",
    )

    freshness_state = str(
        freshness.get("overall_state")
        or freshness.get("status")
        or freshness_summary.get("overall_state")
        or ""
    ).lower()
    reliability_state = str(reliability.get("overall_status") or reliability.get("status") or "").lower()
    require(
        freshness_state in {"ok", "review", "attention", "partial"},
        "Freshness publishes an accepted finalized state",
    )
    if freshness_state in {"review", "attention", "partial"}:
        require(
            reliability_state != "ok",
            "Reliability does not suppress a non-healthy Freshness result",
        )
    else:
        require(
            reliability_state in {"ok", "review", "attention", "partial"},
            "Reliability publishes an accepted finalized state",
        )

    monitored_authority = (
        monitored_products.get("authority")
        if isinstance(monitored_products.get("authority"), dict)
        else {}
    )
    monitored_scope = (
        monitored_products.get("scope")
        if isinstance(monitored_products.get("scope"), dict)
        else {}
    )
    require(
        monitored_authority.get("safe_to_publish") is True
        or monitored_products.get("status") in {"ok", "review"},
        "Monitored Product Authority is publishable or honestly marked for review",
    )
    require(
        monitored_authority.get("fabricated_products") is False,
        "Monitored Product Authority contains no fabricated products",
    )
    require(
        monitored_scope.get("commercial_licensing_included") is False,
        "Monitored Product Authority does not claim commercial licensing authority",
    )

    print(
        "PASS: Runtime Truth Chain validator aligned to separate canonical runtime and standalone Admin executions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
