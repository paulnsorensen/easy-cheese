from __future__ import annotations

import json
import re
from collections.abc import Generator
from pathlib import Path
from typing import cast

import pytest

from easy_cheese_schemas.artifacts import ArtifactResolutionError, resolve_artifact
from easy_cheese_schemas.contracts import (
    ArtifactRef,
    ContractVersion,
    CurdPlan,
    CurdResult,
    PlannerResult,
    ReviewResult,
    UnsupportedProjection,
)
from easy_cheese_schemas.phase_contracts import (
    COMPILED_TRANSITION_REGISTRY,
    TransitionError,
    validate_transition,
)
from easy_cheese_schemas.projections import project_curd_block
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
    return cast(
        "dict[str, object]", json.loads(FIXTURE_FILES[filename].read_text(encoding="utf-8"))
    )


CONTRACT_DOCUMENT = _load_fixture("contract-cases.json")
NORMALIZATION_DOCUMENT = _load_fixture("normalization-cases.json")
CONTRACT_CASES = cast("list[dict[str, object]]", CONTRACT_DOCUMENT["cases"])
NORMALIZATION_CASES = cast("list[dict[str, object]]", NORMALIZATION_DOCUMENT["cases"])


def _strings(value: object) -> Generator[str, None, None]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in cast("list[object]", value):
            yield from _strings(item)
    elif isinstance(value, dict):
        for item in cast("dict[str, object]", value).values():
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
    raw_cases = cast("list[object]", cases)
    names = [cast("dict[str, object]", case)["name"] for case in raw_cases]
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
        for case in cast("list[dict[str, object]]", document["cases"])
    ]
    assert len(names) == len(set(names))


def test_contract_fixture_case_schema_is_closed() -> None:
    common = {"name", "operation", "input", "expected"}
    operation_fields: dict[str, set[str]] = {
        "validate_contract": {"schema_uri", "supported_version"},
        "normalize_agent_output": set(),
        "resolve_artifact": set(),
        "validate_transition": set(),
        "project_legacy": {"schema_uri", "supported_version", "target"},
    }
    for case in CONTRACT_CASES:
        operation = case["operation"]
        assert isinstance(operation, str)
        assert operation in operation_fields
        assert set(case) == common | operation_fields[operation]
        expected = case["expected"]
        assert isinstance(expected, dict)
        expected = cast("dict[str, object]", expected)
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
        writer_view = case["writer_view"]
        assert isinstance(writer_view, dict)
        writer_view = cast("dict[str, object]", writer_view)
        assert set(writer_view) == {"kind", "payload"}
        assert isinstance(case["host_invocation"], dict)
        assert isinstance(case["expected_canonical_output"], dict)
        assert isinstance(case["stable"], dict)


def _version(case: dict[str, object]) -> ContractVersion:
    supported_version = case["supported_version"]
    assert isinstance(supported_version, dict)
    supported_version = cast("dict[str, str]", supported_version)
    return ContractVersion(
        schema_uri=supported_version["schema_uri"],
        major=supported_version["major"],
        minor=supported_version["minor"],
    )


def _validated_contract_observation(case: dict[str, object]) -> dict[str, object]:
    schema_uri = case["schema_uri"]
    assert isinstance(schema_uri, str)
    value = validate_contract(
        case["input"], schema_uri, supported_version=_version(case)
    ).value
    if schema_uri.endswith("/curd-plan"):
        assert isinstance(value, CurdPlan)
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
    assert isinstance(value, CurdResult)
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
    assert isinstance(invocation, dict)
    invocation = cast("dict[str, object]", invocation)
    value = normalize_agent_output(
        invocation["writer_view"], invocation["host_invocation"]
    ).value
    assert isinstance(value, PlannerResult)
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
    name = case["name"]
    assert isinstance(name, str)
    repository_root = tmp_path / name
    repository_root.mkdir()
    input_ = case["input"]
    assert isinstance(input_, dict)
    input_ = cast("dict[str, object]", input_)
    source = input_.get("source")
    if source:
        assert isinstance(source, dict)
        source = cast("dict[str, object]", source)
        path = source["path"]
        content = source["content"]
        assert isinstance(path, str)
        assert isinstance(content, str)
        source_path = repository_root / path
        source_path.parent.mkdir(parents=True)
        _ = source_path.write_text(content, encoding="utf-8")
    artifact_data = input_["artifact"]
    assert isinstance(artifact_data, dict)
    artifact_data = cast("dict[str, object]", artifact_data)
    artifact_id = artifact_data["artifact_id"]
    role = artifact_data["role"]
    uri = artifact_data["uri"]
    digest = artifact_data["digest"]
    size_bytes = artifact_data["size_bytes"]
    media_type = artifact_data["media_type"]
    schema_uri = artifact_data.get("schema_uri")
    assert isinstance(artifact_id, str)
    assert isinstance(role, str)
    assert isinstance(uri, str)
    assert isinstance(digest, str)
    assert isinstance(size_bytes, int)
    assert isinstance(media_type, str)
    assert schema_uri is None or isinstance(schema_uri, str)
    artifact = ArtifactRef(
        artifact_id=artifact_id,
        role=role,
        uri=uri,
        digest=digest,
        size_bytes=size_bytes,
        media_type=media_type,
        schema_uri=schema_uri,
    )
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
    input_ = case["input"]
    assert isinstance(input_, dict)
    input_ = cast("dict[str, object]", input_)
    source = input_["source"]
    destination = input_["destination"]
    payload_schema_uri = input_.get("payload_schema_uri")
    assert isinstance(source, str)
    assert isinstance(destination, str)
    assert payload_schema_uri is None or isinstance(payload_schema_uri, str)
    transition = validate_transition(
        COMPILED_TRANSITION_REGISTRY, source, destination, payload_schema_uri
    )
    assert transition is not None
    return {
        "type": type(transition).__name__,
        "source": transition.source,
        "destination": transition.destination,
        "payload_schema_uri": transition.payload_schema_uri,
    }


def _projection_observation(case: dict[str, object]) -> dict[str, object]:
    schema_uri = case["schema_uri"]
    assert isinstance(schema_uri, str)
    value = validate_contract(
        case["input"], schema_uri, supported_version=_version(case)
    ).value
    assert isinstance(value, CurdPlan)
    assert case["target"] == "curd_block"
    projected = project_curd_block(value)
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


def _case_id(case: dict[str, object]) -> str:
    name = case["name"]
    assert isinstance(name, str)
    return name


@pytest.mark.parametrize("case", CONTRACT_CASES, ids=_case_id)
def test_contract_case(case: dict[str, object], tmp_path: Path) -> None:
    expected = case["expected"]
    assert isinstance(expected, dict)
    expected = cast("dict[str, object]", expected)
    if expected["status"] == "accept":
        assert _dispatch_contract_case(case, tmp_path) == expected["value"]
        return

    error_type_name = expected["error_type"]
    assert isinstance(error_type_name, str)
    error_type = ERROR_TYPES[error_type_name]
    with pytest.raises(error_type) as error:
        _ = _dispatch_contract_case(case, tmp_path)
    assert str(error.value) == expected["message"]


def _stable_observation(kind: str, value: object) -> dict[str, object]:
    if kind == "curd_plan":
        assert isinstance(value, CurdPlan)
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
        assert isinstance(value, ReviewResult)
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
    assert isinstance(value, CurdResult)
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


@pytest.mark.parametrize("case", NORMALIZATION_CASES, ids=_case_id)
def test_normalization_case_is_byte_exact_and_stable(case: dict[str, object]) -> None:
    normalized = normalize_agent_output(case["writer_view"], case["host_invocation"])
    expected_canonical_output = case["expected_canonical_output"]
    expected_stable = case["stable"]
    assert isinstance(expected_canonical_output, dict)
    assert isinstance(expected_stable, dict)
    expected_bytes = (
        json.dumps(
            expected_canonical_output,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
    assert normalized.canonical_bytes == expected_bytes
    writer_view = case["writer_view"]
    assert isinstance(writer_view, dict)
    writer_view = cast("dict[str, object]", writer_view)
    kind = writer_view["kind"]
    assert isinstance(kind, str)
    assert (
        _stable_observation(kind, normalized.value)
        == expected_stable
    )