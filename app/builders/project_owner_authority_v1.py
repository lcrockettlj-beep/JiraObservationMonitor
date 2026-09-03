from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_LEAD_AUTHORITY = Path("runtime/data/project_lead_authority_v1.json")
OUTPUT = Path("runtime/data/project_owner_authority_v1.json")
AUTHORIZED_ROLE = "Organisation administrator"


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def read_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise SystemExit(f"STOP: required authority missing: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"STOP: required authority is unreadable: {path}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise SystemExit(f"STOP: required authority root is not an object: {path}")
    return payload


def write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    lead_authority = read_contract(PROJECT_LEAD_AUTHORITY)
    lead_status = lead_authority.get("status")
    lead_summary = (
        lead_authority.get("summary")
        if isinstance(lead_authority.get("summary"), dict)
        else {}
    )
    lead_gate = (
        lead_authority.get("authority")
        if isinstance(lead_authority.get("authority"), dict)
        else {}
    )
    lead_privacy = (
        lead_authority.get("privacy")
        if isinstance(lead_authority.get("privacy"), dict)
        else {}
    )
    lead_projects = (
        lead_authority.get("projects")
        if isinstance(lead_authority.get("projects"), list)
        else []
    )

    source_gates = {
        "schema_valid": lead_authority.get("schema")
        == "jom-project-lead-authority-v1",
        "status_publishable": lead_status in {"ok", "partial"},
        "safe_to_serve": lead_gate.get("safe_to_serve") is True,
        "project_owner_not_claimed_by_source": lead_gate.get(
            "project_owner_semantics_proven"
        )
        is False,
        "project_population_present": lead_summary.get("projects", 0) > 0,
        "project_rows_reconcile": lead_summary.get("projects")
        == len(lead_projects),
        "source_privacy_safe": lead_privacy.get("account_ids_stored") is False
        and lead_privacy.get("email_stored") is False
        and lead_privacy.get("raw_responses_stored") is False,
    }
    if not all(source_gates.values()):
        raise SystemExit(
            "STOP: Project Lead Authority did not pass all Project Owner "
            "derivation gates: " + json.dumps(source_gates, sort_keys=True)
        )

    projects: list[dict[str, Any]] = []
    owner_names: set[str] = set()
    projects_with_owner = 0

    for project in lead_projects:
        if not isinstance(project, dict):
            raise SystemExit("STOP: Project Lead Authority contains a non-object row")

        source_leads = (
            project.get("leads") if isinstance(project.get("leads"), list) else []
        )
        owners: list[dict[str, Any]] = []
        for lead in source_leads:
            if not isinstance(lead, dict):
                continue
            display_name = str(lead.get("display_name") or "").strip()
            if not display_name:
                continue
            owner = {
                "display_name": display_name,
                "account_status": lead.get("account_status"),
                "owner_type": "governance_defined_space_owner",
                "owner_source": "project_lead_authority_v1",
            }
            if owner not in owners:
                owners.append(owner)
                owner_names.add(display_name)

        owners.sort(key=lambda row: row["display_name"].casefold())
        owner_available = bool(owners)
        projects_with_owner += int(owner_available)
        projects.append(
            {
                "site_key": str(project.get("site_key") or ""),
                "project_key": str(project.get("project_key") or ""),
                "project_name": str(project.get("project_name") or ""),
                "owner_state": (
                    "governance_defined_space_owner_available"
                    if owner_available
                    else "no_supported_project_lead_owner_published"
                ),
                "supported_owner_count": len(owners),
                "owners": owners,
            }
        )

    total_projects = len(projects)
    projects_without_owner = total_projects - projects_with_owner
    coverage = (
        round(projects_with_owner * 100.0 / total_projects, 1)
        if total_projects
        else 0.0
    )
    status = "ok" if projects_without_owner == 0 else "partial"

    payload = {
        "schema": "jom-project-owner-authority-v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "definition": {
            "owner_type": "governance_defined_space_owner",
            "owner_source": "project_lead_authority_v1",
            "governance_rule": "Project Lead is the owner of the project space.",
            "native_jira_owner_field_present": False,
            "native_jira_owner_authority_available": False,
            "authority_class": "derived_governance_authority",
        },
        "source": {
            "contract": str(PROJECT_LEAD_AUTHORITY).replace("\\", "/"),
            "schema": lead_authority.get("schema"),
            "status": lead_status,
            "generated_at_utc": lead_authority.get("generated_at_utc"),
            "gates": source_gates,
        },
        "summary": {
            "projects": total_projects,
            "projects_with_governance_defined_owner": projects_with_owner,
            "projects_without_governance_defined_owner_published": (
                projects_without_owner
            ),
            "owner_coverage_percent": coverage,
            "distinct_governance_defined_owners": len(owner_names),
        },
        "authority": {
            "safe_to_serve": total_projects > 0,
            "governance_owner_semantics_proven": True,
            "native_jira_owner_semantics_proven": False,
            "reason": (
                "GLI defines the Project Lead as the owner of the project space. "
                "Owner rows are derived only from the publishable Project Lead "
                "Authority; missing lead evidence remains unavailable."
            ),
        },
        "privacy": {
            "display_name_only": True,
            "account_ids_stored": False,
            "email_stored": False,
            "raw_responses_stored": False,
            "export_allowed": False,
            "download_allowed": False,
            "bulk_copy_allowed": False,
        },
        "access": {
            "authorized_role": AUTHORIZED_ROLE,
            "phase1_mode": "trusted_local_operator",
            "deny_by_default": True,
        },
        "limitations": [
            "This is a GLI governance-defined space-owner authority, not a Jira-native owner field.",
            "No supported Project Lead publication means the governance-defined owner is unavailable, not zero.",
            "Project lifecycle changes require a refreshed Project Inventory and Project Lead Authority before this authority is derived again.",
        ],
        "projects": projects,
    }

    if not payload["authority"]["safe_to_serve"]:
        raise SystemExit("STOP: no Project Owner rows were reconciled")

    write_atomic(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": str(OUTPUT),
                "summary": payload["summary"],
                "owner_type": payload["definition"]["owner_type"],
                "native_jira_owner_field_present": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
