"""Regression tests for the canonical curd-plan load-and-validate entry point.

A `.curd-plan.json` artifact consumer needs one documented path from decoded
JSON to a validated `CurdPlan`. Passing a decoded mapping to
`validate_curd_plan` raises `TypeError`, so `load_curd_plan` owns the
structure-then-validate step and rejects YAML/Markdown frontmatter.
"""

from __future__ import annotations

import json

import pytest

import easy_cheese_schemas as schemas
from easy_cheese_schemas.contracts import CurdPlan
from easy_cheese_schemas.schema_runtime import load_curd_plan


def raw_plan() -> dict[str, object]:
    version = schemas.supported_version_for(CurdPlan)
    assert version is not None
    unsigned: dict[str, object] = {
        "contract_version": json.loads(schemas.canonical_bytes(version)),
        "plan_id": "plan",
        "revision": 1,
        "objective": "Publish a stable contract package",
        "curds": [
            {
                "curd_id": "plan/curd/1",
                "outcome": "Publish the stable contract package",
                "scope": {
                    "paths": ["src/easy_cheese_schemas/__init__.py"],
                    "excluded_paths": [],
                },
                "inputs": [],
                "outputs": ["easy-cheese-schemas"],
                "dependencies": [],
                "criteria": [
                    {
                        "criterion_id": "plan/curd/1/criterion/1",
                        "description": "The loader returns a validated plan",
                        "check": "pytest tests/schemas/python/test_load_curd_plan.py",
                    }
                ],
                "lineage": {"identity_action": "new", "source_curd_ids": []},
            }
        ],
        "context": None,
        "parent_plan_ref": None,
    }
    return {**unsigned, "digest": schemas.canonical_digest(unsigned)}


def test_decoded_json_mapping_reaches_a_validated_plan() -> None:
    raw = raw_plan()
    # The issue reproduction: a decoded mapping is not a CurdPlan.
    with pytest.raises(TypeError, match="expects CurdPlan, not dict"):
        _ = schemas.validate_curd_plan(raw)

    plan = load_curd_plan(raw)
    assert isinstance(plan, CurdPlan)
    assert plan.plan_id == "plan"
    assert plan == schemas.validate_curd_plan(plan)


def test_raw_json_text_loads() -> None:
    raw = raw_plan()
    plan = load_curd_plan(json.dumps(raw))
    assert isinstance(plan, CurdPlan)
    assert plan == load_curd_plan(raw)


def test_raw_json_bytes_load() -> None:
    raw = raw_plan()
    plan = load_curd_plan(json.dumps(raw).encode())
    assert isinstance(plan, CurdPlan)
    assert plan == load_curd_plan(raw)


def test_yaml_frontmatter_is_rejected_as_wrong_artifact_format() -> None:
    document = "---\nplan_id: plan\nobjective: x\n---\n# body\n"
    with pytest.raises(schemas.ContractValidationError, match="canonical JSON"):
        _ = load_curd_plan(document)


def test_tampered_digest_is_still_rejected() -> None:
    with pytest.raises(schemas.ContractValidationError):
        _ = load_curd_plan({**raw_plan(), "objective": "Tampered"})
