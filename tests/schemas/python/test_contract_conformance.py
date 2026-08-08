from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from easy_cheese_schemas.artifacts import ArtifactResolutionError, resolve_artifact
from easy_cheese_schemas.contracts import ArtifactRef, ContractVersion
from easy_cheese_schemas.phase_contracts import (
    COMPILED_TRANSITION_REGISTRY,
    TransitionError,
    validate_transition,
)
from easy_cheese_schemas.projections import UnsupportedProjection, project_curd_block
from easy_cheese_schemas.schema_runtime import (
    ContractValidationError,
    normalize_agent_output,
    validate_contract,
)

ROOT = Path(__file__).parents[3]
FIXTURE_ROOT = ROOT / "src/easy_cheese_schemas/conformance/v1"
FIXTURE_FILES = {
    "contract-cases.json": FIXTURE_ROOT / "contract-cases.json",
    "normalization-cases.json": FIXTURE_ROOT / "normalization-cases.json",
}
NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
ERROR_TYPES = {
    "ArtifactResolutionError": ArtifactResolutionError,
    "ContractValidationError": ContractValidationError,
    "TransitionError": TransitionError,
}


def _load_fixture(filename: str) -> dict[str, object]:
    return json.loads(FIXTURE_FILES[filename].read_text(encoding="utf-8"))


CONTRACT_DOCUMENT = _load_fixture("contract-cases.json")
NORMALIZATION_DOCUMENT = _load_fixture("normalization-cases.json")
CONTRACT_CASES = CONTRACT_DOCUMENT["cases"]
NORMALIZATION_CASES = NORMALIZATION_DOCUMENT["cases"]


def _strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)


def _assert_fixture_document(filename: str, document: dict[str, object]) -> None:
    assert set(document) == {"$schema", "fixture_version", "cases"}
    stem = filename.removesuffix(".json")
    assert document["$schema"] == (
        f"https://schemas.easy-cheese.dev/conformance/v1/{stem}"
    )
    assert document["fixture_version"] == "1.0"
    cases = document["cases"]
    assert isinstance(cases, list) and cases
    names = [case["name"] for case in cases]
    assert all(isinstance(name, str) and NAME_PATTERN.fullmatch(name) for name in names)
    assert len(names) == len(set(names))
    assert all(not value.startswith(("/", "file://")) for value in _strings(document))


@pytest.mark.parametrize(
    ("filename", "document"),
    [(filename, _load_fixture(filename)) for filename in FIXTURE_FILES],
)
def test_fixture_documents_have_versioned_consumer_neutral_schema(
    filename: str, document: dict[str, object]
) -> None:
    _assert_fixture_document(filename, document)


def test_fixture_names_are_unique_across_the_package() -> None:
    names = [
        case["name"]
        for document in (CONTRACT_DOCUMENT, NORMALIZATION_DOCUMENT)
        for case in document["cases"]
    ]
    assert len(names) == len(set(names))


def test_contract_fixture_case_schema_is_closed() -> None:
    common = {"name", "operation", "input", "expected"}
    operation_fields = {
        "validate_contract": {"schema_uri", "supported_version"},
        "normalize_agent_output": set(),
        "resolve_artifact": set(),
        "validate_transition": set(),
        "project_legacy": {"schema_uri", "supported_version", "target"},
    }
    for case in CONTRACT_CASES:
        operation = case["operation"]
        assert operation in operation_fields
        assert set(case) == common | operation_fields[operation]
        expected = case["expected"]
        assert expected["status"] in {"accept", "reject"}
        if expected["status"] == "accept":
            assert set(expected) == {"status", "value"}
        else:
            assert set(expected) == {"status", "error_type", "message"}
            assert expected["error_type"] in ERROR_TYPES


def test_normalization_fixture_case_schema_is_closed() -> None:
    expected_fields = {
        "name",
        "operation",
        "writer_view",
        "host_invocation",
        "expected_canonical_output",
        "stable",
    }
    for case in NORMALIZATION_CASES:
        assert set(case) == expected_fields
        assert case["operation"] == "normalize_agent_output"
        assert set(case["writer_view"]) == {"kind", "payload"}
        assert isinstance(case["host_invocation"], dict)
        assert isinstance(case["expected_canonical_output"], dict)
        assert isinstance(case["stable"], dict)


def _version(case: dict[str, object]) -> ContractVersion:
    return ContractVersion(**case["supported_version"])


def _validated_contract_observation(case: dict[str, object]) -> dict[str, object]:
    value = validate_contract(
        case["input"], case["schema_uri"], supported_version=_version(case)
    ).value
    if case["schema_uri"].endswith("/curd-plan"):
        return {
            "type": type(value).__name__,
            "plan_id": value.plan_id,
            "revision": value.revision,
            "curd_ids": [curd.curd_id for curd in value.curds],
            "criterion_ids": [
                criterion.criterion_id
                for curd in value.curds
                for criterion in curd.criteria
            ],
        }
    return {
        "type": type(value).__name__,
        "result_id": value.result_id,
        "disposition": value.disposition.value,
        "expected_criterion_ids": list(value.expected_criterion_ids),
        "criterion_result_ids": [
            result.criterion_id for result in value.criterion_results
        ],
    }


def _normalized_contract_observation(case: dict[str, object]) -> dict[str, object]:
    invocation = case["input"]
    value = normalize_agent_output(
        invocation["writer_view"], invocation["host_invocation"]
    ).value
    return {
        "type": type(value).__name__,
        "disposition": value.disposition.value,
        "request_id": value.request_id,
        "plan_id": value.plan.plan_id if value.plan else None,
        "curd_ids": [curd.curd_id for curd in value.plan.curds] if value.plan else [],
        "uncertainty_scopes": [item.scope.value for item in value.unresolved_work],
    }


def _resolved_artifact_observation(
    case: dict[str, object], tmp_path: Path
) -> dict[str, object]:
    repository_root = tmp_path / case["name"]
    repository_root.mkdir()
    if source := case["input"].get("source"):
        source_path = repository_root / source["path"]
        source_path.parent.mkdir(parents=True)
        source_path.write_text(source["content"], encoding="utf-8")
    artifact = ArtifactRef(**case["input"]["artifact"])
    resolved = resolve_artifact(
        artifact,
        repository_root=repository_root,
        artifact_directory=tmp_path / "retained",
    )
    return {
        "type": type(resolved).__name__,
        "role": resolved.role,
        "media_type": resolved.media_type,
        "content": Path(resolved.path).read_text(encoding="utf-8"),
    }


def _transition_observation(case: dict[str, object]) -> dict[str, object]:
    transition = validate_transition(COMPILED_TRANSITION_REGISTRY, **case["input"])
    return {
        "type": type(transition).__name__,
        "source": transition.source,
        "destination": transition.destination,
        "payload_schema_uri": transition.payload_schema_uri,
    }


def _projection_observation(case: dict[str, object]) -> dict[str, object]:
    plan = validate_contract(
        case["input"], case["schema_uri"], supported_version=_version(case)
    ).value
    assert case["target"] == "curd_block"
    projected = project_curd_block(plan)
    assert isinstance(projected, UnsupportedProjection)
    return {
        "type": type(projected).__name__,
        "target": projected.target,
        "curd_id": projected.curd_id,
        "field": projected.field,
        "reason": projected.reason,
    }


def _dispatch_contract_case(
    case: dict[str, object], tmp_path: Path
) -> dict[str, object]:
    operation = case["operation"]
    if operation == "validate_contract":
        return _validated_contract_observation(case)
    if operation == "normalize_agent_output":
        return _normalized_contract_observation(case)
    if operation == "resolve_artifact":
        return _resolved_artifact_observation(case, tmp_path)
    if operation == "validate_transition":
        return _transition_observation(case)
    if operation == "project_legacy":
        return _projection_observation(case)
    raise AssertionError(f"unhandled fixture operation: {operation}")


@pytest.mark.parametrize("case", CONTRACT_CASES, ids=lambda case: case["name"])
def test_contract_case(case: dict[str, object], tmp_path: Path) -> None:
    expected = case["expected"]
    if expected["status"] == "accept":
        assert _dispatch_contract_case(case, tmp_path) == expected["value"]
        return

    error_type = ERROR_TYPES[expected["error_type"]]
    with pytest.raises(error_type) as error:
        _dispatch_contract_case(case, tmp_path)
    assert str(error.value) == expected["message"]


def _stable_observation(kind: str, value: object) -> dict[str, object]:
    if kind == "curd_plan":
        return {
            "digest": value.digest,
            "identity": {
                "plan_id": value.plan_id,
                "revision": value.revision,
                "curd_ids": [curd.curd_id for curd in value.curds],
                "criterion_ids": [
                    criterion.criterion_id
                    for curd in value.curds
                    for criterion in curd.criteria
                ],
            },
            "provenance": {
                "input_artifact_ids": [
                    artifact.artifact_id
                    for curd in value.curds
                    for artifact in curd.inputs
                ]
            },
        }
    if kind == "review_result":
        return {
            "identity": {
                "review_id": value.review_id,
                "finding_ids": [finding.finding_id for finding in value.findings],
            },
            "provenance": {
                "finding_evidence_ids": [
                    evidence.evidence_id
                    for finding in value.findings
                    for evidence in finding.evidence
                ],
                "location_artifact_ids": [
                    finding.location.artifact_id
                    for finding in value.findings
                    if finding.location
                ],
            },
            "coverage": {
                "targets": [row.target for row in value.coverage],
                "dispositions": [row.disposition.value for row in value.coverage],
            },
        }
    return {
        "identity": {
            "result_id": value.result_id,
            "source_plan_id": value.source_plan_ref.plan_id,
            "source_curd_id": value.source_curd_ref.curd_id,
        },
        "provenance": {
            "criterion_evidence_ids": [
                evidence.evidence_id
                for result in value.criterion_results
                for evidence in result.evidence
            ],
            "deliverable_artifact_ids": [
                artifact.artifact_id for artifact in value.deliverables
            ],
            "runtime_refs": list(value.runtime_refs),
        },
        "coverage": {
            "expected_criterion_ids": list(value.expected_criterion_ids),
            "criterion_result_ids": [
                result.criterion_id for result in value.criterion_results
            ],
            "dispositions": [
                result.disposition.value for result in value.criterion_results
            ],
        },
    }


@pytest.mark.parametrize("case", NORMALIZATION_CASES, ids=lambda case: case["name"])
def test_normalization_case_is_byte_exact_and_stable(case: dict[str, object]) -> None:
    normalized = normalize_agent_output(case["writer_view"], case["host_invocation"])
    expected_bytes = (
        json.dumps(
            case["expected_canonical_output"],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
    assert normalized.canonical_bytes == expected_bytes
    assert (
        _stable_observation(case["writer_view"]["kind"], normalized.value)
        == case["stable"]
    )
