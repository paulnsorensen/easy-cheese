"""PrPlan v1 as the single registered PR-topology contract (AC-1, AC-2, AC-5).

The conformance table in ``test_pr_plan_conformance.py`` pins the load path and
the topology rules (AC-3, AC-4). This module pins the ``validate_contract`` seam
named in the spec's Test Contracts: registration, the strict v1 cut, and the
generated, drift-gated reference JSON.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
import render_generated_regions

from easy_cheese_schemas import (
    REGISTERED_CONTRACT_SCHEMA_URIS,
    ContractValidationError,
    PrPlan,
    schema_bytes,
    supported_version_for,
    validate_contract,
)
from easy_cheese_schemas.schema_runtime import load_pr_plan
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


def test_pr_plan_refuses_a_document_from_an_unsupported_minor() -> None:
    """AC-2: load_pr_plan gates on the registered version, not just the shape."""
    raw = pr_plan()
    cast(dict[str, object], raw["contract_version"])["minor"] = "1"

    loaded = load_pr_plan(raw)

    assert loaded.value is None
    assert loaded.problems == (
        "PrPlan.contract_version 1.1 for https://schemas.easy-cheese.dev/pr-plan "
        + "is unsupported; expected 1.0 for "
        + "https://schemas.easy-cheese.dev/pr-plan",
    )


@pytest.fixture
def pr_plan_reference() -> Iterator[Path]:
    """Yield the generated reference JSON, restoring its bytes afterwards."""
    ref = ROOT / "skills" / "ultracook" / "references" / "pr-plan-schema.json"
    original = ref.read_bytes()
    try:
        yield ref
    finally:
        _ = ref.write_bytes(original)


def test_reference_json_is_generated_byte_for_byte_and_drift_gated(
    pr_plan_reference: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-5: the reference JSON is schema_bytes output; --check fails on drift."""
    assert pr_plan_reference.read_bytes() == schema_bytes(PrPlan)
    assert render_generated_regions.main(["--check"]) == 0

    _ = pr_plan_reference.write_bytes(schema_bytes(PrPlan).rstrip(b"\n") + b" \n")

    assert render_generated_regions.main(["--check"]) == 1
    assert "pr-plan-schema.json" in capsys.readouterr().err