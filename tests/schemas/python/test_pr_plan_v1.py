"""PrPlan v1 as the single registered PR-topology contract (AC-1, AC-2, AC-5).

The conformance table in ``test_pr_plan_conformance.py`` pins the load path and
the topology rules (AC-3, AC-4). This module pins the ``validate_contract`` seam
named in the spec's Test Contracts: registration, the strict v1 cut, and the
generated, drift-gated reference JSON.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from easy_cheese_schemas import (
    REGISTERED_CONTRACT_SCHEMA_URIS,
    ContractValidationError,
    PrPlan,
    schema_bytes,
    supported_version_for,
    validate_contract,
)
from schema_conformance import pr_plan

ROOT = Path(__file__).resolve().parents[3]
PR_PLAN_SCHEMA_URI = "https://schemas.easy-cheese.dev/pr-plan"


def test_pr_plan_is_registered_v1_contract() -> None:
    """AC-1: the catalog registers pr-plan at version 1.0 and serves its schema."""
    assert PR_PLAN_SCHEMA_URI in REGISTERED_CONTRACT_SCHEMA_URIS
    version = supported_version_for(PrPlan)
    assert version is not None
    assert (version.schema_uri, version.major, version.minor) == (
        PR_PLAN_SCHEMA_URI,
        "1",
        "0",
    )
    payload = schema_bytes(PR_PLAN_SCHEMA_URI)
    assert payload.endswith(b"\n")
    assert schema_bytes(PrPlan) == payload


def test_pr_plan_accepts_a_valid_v1_document_and_defaults_target_branch() -> None:
    """AC-3: a document without target_branch structures and defaults to main."""
    artifact = validate_contract(pr_plan(), PrPlan, supported_version_for(PrPlan))
    plan = cast(PrPlan, artifact.value)
    assert plan.target_branch == "main"


@pytest.mark.parametrize("field", ["plate_layout", "pr_number", "pr_url", "surprise"])
def test_pr_plan_rejects_forbidden_and_unknown_keys(field: str) -> None:
    """AC-2: the strict cut rejects plate_layout, pr_number, pr_url, unknown keys."""
    raw = pr_plan()
    raw[field] = "x"
    with pytest.raises(ContractValidationError, match=field):
        _ = validate_contract(raw, PrPlan, supported_version_for(PrPlan))


def test_pr_plan_rejects_a_document_without_contract_version() -> None:
    """AC-2: an unversioned document is rejected, naming the missing field."""
    raw = pr_plan()
    del raw["contract_version"]
    with pytest.raises(ContractValidationError, match="contract_version"):
        _ = validate_contract(raw, PrPlan, supported_version_for(PrPlan))


def test_reference_json_is_generated_byte_for_byte_and_drift_gated() -> None:
    """AC-5: the reference JSON is schema_bytes output; --check fails on drift."""
    ref = ROOT / "skills" / "ultracook" / "references" / "pr-plan-schema.json"
    assert ref.read_bytes() == schema_bytes(PrPlan)
    original = ref.read_bytes()
    try:
        _ = ref.write_bytes(original.rstrip(b"\n") + b" \n")
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "render_generated_regions.py"),
                "--check",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, result.stdout + result.stderr
    finally:
        _ = ref.write_bytes(original)
