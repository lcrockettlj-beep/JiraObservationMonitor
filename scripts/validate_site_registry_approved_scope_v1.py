from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.registry.site_registry_runtime import (
    APPROVED_OPERATIONAL_SITES,
    KNOWN_RESOURCE_OVERRIDES,
    approved_config,
    reset_to_approved_scope,
)

EXPECTED_SITE_KEYS = {
    "gli-delivery-tm",
    "gli-global-technology",
    "gli-it-project",
    "gli-tracker",
}

TRACKER_CLOUD_ID = "5e39f28e-6ff4-44ff-82b7-d0746cee8db5"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


approved_rows = APPROVED_OPERATIONAL_SITES
approved_keys = {
    str(row.get("site_key") or "").strip()
    for row in approved_rows
    if isinstance(row, dict)
}

if len(approved_rows) != 4:
    fail(f"expected 4 approved operational rows, found {len(approved_rows)}")

if approved_keys != EXPECTED_SITE_KEYS:
    fail(
        "approved site keys differ: "
        f"expected={sorted(EXPECTED_SITE_KEYS)} "
        f"actual={sorted(approved_keys)}"
    )

tracker_rows = [
    row for row in approved_rows
    if isinstance(row, dict) and row.get("site_key") == "gli-tracker"
]

if len(tracker_rows) != 1:
    fail(f"expected exactly one approved gli-tracker row, found {len(tracker_rows)}")

tracker = tracker_rows[0]

if tracker.get("status") != "monitored":
    fail("gli-tracker approved row is not monitored")

if tracker.get("site_url") != "https://gli-tracker.atlassian.net":
    fail("gli-tracker approved row has an unexpected site URL")

override = KNOWN_RESOURCE_OVERRIDES.get(TRACKER_CLOUD_ID)

if not isinstance(override, dict):
    fail("gli-tracker Cloud ID identity mapping is missing")

if override.get("site_key") != "gli-tracker":
    fail("gli-tracker Cloud ID does not map to the correct site key")

if "classification" in override:
    fail("identity override still assigns lifecycle classification")

override_text = json.dumps(override, ensure_ascii=False).lower()

for obsolete_phrase in (
    "not part of monitored operational estate",
    "until approved",
):
    if obsolete_phrase in override_text:
        fail(f"identity override contains obsolete phrase: {obsolete_phrase}")

config = approved_config()
config_rows = config.get("site_registry")

if not isinstance(config_rows, list):
    fail("approved_config site_registry is not a list")

config_keys = {
    str(row.get("site_key") or "").strip()
    for row in config_rows
    if isinstance(row, dict)
}

if config_keys != EXPECTED_SITE_KEYS:
    fail(
        "approved_config differs from approved authority: "
        f"expected={sorted(EXPECTED_SITE_KEYS)} "
        f"actual={sorted(config_keys)}"
    )

if len(config_rows) != 4:
    fail(f"approved_config contains {len(config_rows)} rows, expected 4")

with tempfile.TemporaryDirectory(prefix="jom_site_registry_validation_") as temp:
    temp_root = Path(temp)
    result = reset_to_approved_scope(temp_root)

    output_path = temp_root / "runtime" / "data" / "site_registry.json"

    if not output_path.exists():
        fail("reset validation did not create its isolated registry output")

    written = json.loads(output_path.read_text(encoding="utf-8"))
    written_rows = written.get("site_registry")

    if not isinstance(written_rows, list):
        fail("isolated reset output site_registry is not a list")

    written_keys = {
        str(row.get("site_key") or "").strip()
        for row in written_rows
        if isinstance(row, dict)
    }

    if written_keys != EXPECTED_SITE_KEYS:
        fail(
            "isolated reset output differs: "
            f"expected={sorted(EXPECTED_SITE_KEYS)} "
            f"actual={sorted(written_keys)}"
        )

    if result != written:
        fail("reset return value differs from isolated file output")

print(
    "PASS: site registry recovery authority contains exactly four approved "
    "operational sites; gli-tracker approval is retained and its Cloud ID "
    "override is identity-only."
)
