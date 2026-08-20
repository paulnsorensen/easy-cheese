from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from easy_cheese_schemas._schema_catalog_compiler import (
    collect as collect_schema_markers,
    render as render_schema_catalog,
)
from easy_cheese_schemas.contracts import (
    MAX_CONTRACT_BYTES,
    MAX_CONTRACT_DEPTH,
    ContractVersion,
    CurdPlan,
    contract,
)
from easy_cheese_schemas.schema_runtime import (
    REGISTERED_CONTRACT_SCHEMA_URIS,
    ContractValidationError,
    canonical_digest,
    normalize_agent_output,
    schema_bytes,
    normalize_agent_value,
    supported_version_for,
    validate_contract,
)

SCHEMA_ROOT = "https://schemas.easy-cheese.dev"
ROOT = Path(__file__).resolve().parents[3]

PLAN_SCHEMA = f"{SCHEMA_ROOT}/curd-plan"


def version(
    schema_uri: str = PLAN_SCHEMA, *, major: str = "1", minor: str = "0"
) -> ContractVersion:
    return ContractVersion(schema_uri=schema_uri, major=major, minor=minor)


def raw_plan(
    *,
    major: object = "1",
    minor: object = "0",
    digest_minor: str = "0",
) -> dict[str, object]:
    raw: dict[str, object] = {
        "contract_version": {
            "schema_uri": PLAN_SCHEMA,
            "major": major,
            "minor": minor,
        },
        "plan_id": "plan-1",
        "revision": 1,
        "objective": "Ship the approved behavior",
        "curds": [
            {
                "curd_id": "curd-1",
                "outcome": "Implement strict validation",
                "scope": {"paths": ["src/runtime.py"]},
                "inputs": [],
                "outputs": ["Validated contract"],
                "dependencies": [],
                "criteria": [
                    {
                        "criterion_id": "criterion-1",
                        "description": "Unknown fields reject",
                        "check": "uv run pytest tests/test_runtime.py",
                    }
                ],
                "lineage": {"identity_action": "new"},
            }
        ],
    }
    unsigned = json.loads(json.dumps(raw))
    unsigned["contract_version"]["minor"] = digest_minor
    unsigned["curds"][0]["scope"]["excluded_paths"] = []
    unsigned["curds"][0]["lineage"]["source_curd_ids"] = []
    unsigned["context"] = None
    unsigned["parent_plan_ref"] = None
    raw["digest"] = canonical_digest(unsigned)
    return raw


def writer_plan() -> dict[str, object]:
    return {
        "kind": "curd_plan",
        "payload": {
            "objective": "Ship the approved behavior",
            "curds": [
                {
                    "key": "runtime",
                    "outcome": "Implement strict validation",
                    "scope": {"paths": ["src/runtime.py"]},
                    "outputs": ["Validated contract"],
                    "criteria": [
                        {
                            "description": "Unknown fields reject",
                            "check": "uv run pytest tests/test_runtime.py",
                        }
                    ],
                }
            ],
        },
    }


def test_marker_authority_rejects_duplicate_slugs() -> None:
    contracts = importlib.import_module("easy_cheese_schemas.contracts")
    original_slug = contracts.CurdPlan.__contract_slug__
    try:
        contracts.CurdPlan.__contract_slug__ = "curd-result"
        with pytest.raises(
            ValueError, match=r"duplicate contract marker 'curd-result'"
        ):
            contracts._registered_contracts()
    finally:
        contracts.CurdPlan.__contract_slug__ = original_slug


@pytest.mark.parametrize("slug", ["", "  ", 7])
def test_contract_rejects_invalid_markers(slug: object) -> None:
    with pytest.raises(
        ValueError, match="contract slug must be a non-empty string"
    ):
        contract(slug)  # type: ignore[arg-type]


@pytest.mark.parametrize("slug", ["", " \t", object()])
def test_marker_authority_rejects_invalid_registered_markers(slug: object) -> None:
    contracts = importlib.import_module("easy_cheese_schemas.contracts")
    original_slug = contracts.CurdPlan.__contract_slug__
    try:
        contracts.CurdPlan.__contract_slug__ = slug
        with pytest.raises(
            ValueError, match="contract slug must be a non-empty string"
        ):
            contracts._registered_contracts()
    finally:
        contracts.CurdPlan.__contract_slug__ = original_slug


def test_runtime_and_compiler_project_one_marker_authority() -> None:
    contracts = importlib.import_module("easy_cheese_schemas.contracts")
    runtime = importlib.import_module("easy_cheese_schemas.schema_runtime")
    entries = contracts._registered_contracts()

    assert entries == tuple(sorted(entries, key=lambda entry: entry[0]))
    assert runtime._MARKED_CONTRACTS == entries
    assert collect_schema_markers(contracts) == tuple(
        (slug, contract_type.__name__) for slug, contract_type in entries
    )


def test_compiler_retains_constant_name_collision_validation() -> None:
    with pytest.raises(
        ValueError, match="contract markers produce duplicate constants"
    ):
        render_schema_catalog((("a-b", "First"), ("a_b", "Second")))


def test_generated_catalog_bytes_match_compiler_projection() -> None:
    contracts = importlib.import_module("easy_cheese_schemas.contracts")
    generated = ROOT / "src" / "easy_cheese_schemas" / "_schema_catalog.py"

    assert generated.read_bytes() == render_schema_catalog(
        collect_schema_markers(contracts)
    ).encode("utf-8")


def test_runtime_schema_resolution_rejects_unmarked_contract_in_clean_import() -> None:
    code = """
import importlib
import sys

sys.path[:0] = ["vendor", "src"]

contracts = importlib.import_module("easy_cheese_schemas.contracts")
catalog = importlib.import_module("easy_cheese_schemas._schema_catalog")
runtime = importlib.import_module("easy_cheese_schemas.schema_runtime")
contract = contracts.CurdPlan
original_slug = contract.__contract_slug__
original_uris = catalog.REGISTERED_CONTRACT_SCHEMA_URIS
try:
    delattr(contract, "__contract_slug__")
    catalog.REGISTERED_CONTRACT_SCHEMA_URIS = frozenset(
        uri
        for uri in original_uris
        if uri != "https://schemas.easy-cheese.dev/curd-plan"
    )
    runtime = importlib.reload(runtime)
    try:
        runtime.schema_bytes(contract)
    except KeyError as exc:
        assert exc.args == ("unregistered contract type CurdPlan",)
    else:
        raise AssertionError("unmarked contract resolved through schema_bytes")
finally:
    contract.__contract_slug__ = original_slug
    catalog.REGISTERED_CONTRACT_SCHEMA_URIS = original_uris
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"isolated marker probe failed:\nstdout={result.stdout}\n"
        f"stderr={result.stderr}"
    )


def test_registered_schemas_are_deterministic_draft_2020_12() -> None:
    assert set(REGISTERED_CONTRACT_SCHEMA_URIS) == {
        f"{SCHEMA_ROOT}/agent-writer-view",
        f"{SCHEMA_ROOT}/curd-plan",
        f"{SCHEMA_ROOT}/curd-result",
        f"{SCHEMA_ROOT}/diagnosis-request",
        f"{SCHEMA_ROOT}/diagnosis-result",
        f"{SCHEMA_ROOT}/phase-contract",
        f"{SCHEMA_ROOT}/planner-request",
        f"{SCHEMA_ROOT}/planner-result",
        f"{SCHEMA_ROOT}/review-request",
        f"{SCHEMA_ROOT}/review-result",
    }
    first = {uri: schema_bytes(uri) for uri in REGISTERED_CONTRACT_SCHEMA_URIS}
    second = {uri: schema_bytes(uri) for uri in reversed(sorted(REGISTERED_CONTRACT_SCHEMA_URIS))}

    assert first == second
    for uri, payload in first.items():
        schema = json.loads(payload)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"] == uri
        assert payload.endswith(b"\n")



    plan_schema = json.loads(first[PLAN_SCHEMA])
    assert plan_schema["$defs"]["ContractVersion"]["properties"]["schema_uri"] == {
        "const": PLAN_SCHEMA,
        "type": "string",
    }
    assert plan_schema["$defs"]["ContractVersion"]["properties"]["major"] == {
        "const": "1",
        "type": "string",
    }
    assert plan_schema["$defs"]["ContractVersion"]["properties"]["minor"] == {
        "const": "0",
        "type": "string",
    }
    assert plan_schema["$defs"]["CurdPlan"]["properties"]["plan_id"]["pattern"]
    assert plan_schema["$defs"]["CurdPlan"]["properties"]["revision"]["minimum"] == 1
    assert plan_schema["$defs"]["CurdPlan"]["properties"]["objective"]["maxLength"] == 8192
    assert plan_schema["$defs"]["CurdPlan"]["properties"]["curds"]["minItems"] == 1
    assert plan_schema["$defs"]["CurdPlan"]["properties"]["curds"]["maxItems"] == 256
    assert plan_schema["$defs"]["CurdPlan"]["properties"]["curds"]["uniqueItems"] is True


@pytest.mark.parametrize("schema_uri", sorted(REGISTERED_CONTRACT_SCHEMA_URIS))
def test_registered_schema_matches_pre_migration_golden(schema_uri: str) -> None:
    golden = Path(__file__).with_name("goldens") / f"{schema_uri.rsplit('/', 1)[-1]}.json"

    assert schema_bytes(schema_uri) == golden.read_bytes()


def test_registered_schema_registry_is_immutable_and_private_authority_is_not_public() -> None:
    assert isinstance(REGISTERED_CONTRACT_SCHEMA_URIS, frozenset)
    with pytest.raises(AttributeError):
        REGISTERED_CONTRACT_SCHEMA_URIS.add(PLAN_SCHEMA)  # type: ignore[attr-defined]
    import easy_cheese_schemas.schema_runtime as runtime
    assert not hasattr(runtime, "REGISTERED_CONTRACTS")
    assert not hasattr(runtime, "SUPPORTED_CONTRACT_VERSIONS")



def test_supported_version_lookup_is_authoritative_for_registered_schema() -> None:
    assert supported_version_for(PLAN_SCHEMA) == version()
    assert supported_version_for(CurdPlan) == version()

def test_validate_contract_strictly_structures_tuple_backed_contracts() -> None:
    raw = raw_plan()
    artifact = validate_contract(raw, PLAN_SCHEMA, version())

    assert artifact.value == CurdPlan(
        contract_version=version(),
        plan_id="plan-1",
        revision=1,
        digest=raw["digest"],
        objective="Ship the approved behavior",
        curds=artifact.value.curds,
    )
    assert artifact.value.curds[0].scope.paths == ("src/runtime.py",)
    assert artifact.value.curds[0].criteria[0].criterion_id == "criterion-1"
    canonical = json.loads(artifact.canonical_bytes)
    assert canonical["curds"][0]["scope"] == {
        "paths": ["src/runtime.py"],
        "excluded_paths": [],
    }
    assert canonical["curds"][0]["lineage"] == {
        "identity_action": "new",
        "source_curd_ids": [],
    }
    assert canonical["context"] is None
    assert canonical["parent_plan_ref"] is None


def test_validate_contract_rejects_unknown_fields_before_domain_execution() -> None:
    raw = raw_plan()
    raw["curds"][0]["scope"]["surprise"] = True

    with pytest.raises(ContractValidationError, match="unknown fields: surprise"):
        validate_contract(raw, PLAN_SCHEMA, version())


@pytest.mark.parametrize(
    ("major", "minor", "message"),
    [
        ("2", "0", "unsupported contract major 2"),
        ("1", "2", "future contract minor 2"),
    ],
)
def test_validate_contract_rejects_unsupported_versions(
    major: str, minor: str, message: str
) -> None:
    with pytest.raises(ContractValidationError, match=message):
        validate_contract(
            raw_plan(major=major, minor=minor),
            PLAN_SCHEMA,
            version(),
        )


def test_validate_contract_rejects_tampered_digest() -> None:
    raw = raw_plan()
    raw["digest"] = "sha256:" + ("0" * 64)

    with pytest.raises(ContractValidationError, match="CurdPlan digest mismatch"):
        validate_contract(raw, PLAN_SCHEMA, version())


def test_validate_contract_rejects_supported_version_for_other_schema() -> None:
    raw = raw_plan()

    with pytest.raises(ContractValidationError, match="supported_version.schema_uri"):
        validate_contract(
            raw,
            PLAN_SCHEMA,
            version(schema_uri="https://schemas.easy-cheese.dev/curd-result"),
        )

def test_validate_contract_rejects_huge_future_minor_as_typed_error() -> None:
    huge_minor = "9" * 5_000

    with pytest.raises(ContractValidationError, match=r"future contract minor 9"):
        validate_contract(
            raw_plan(minor=huge_minor),
            PLAN_SCHEMA,
            version(),
        )


def test_validate_contract_rejects_raw_transport_over_byte_budget() -> None:
    oversized = b"{" + b"x" * MAX_CONTRACT_BYTES + b"}"
    with pytest.raises(ContractValidationError, match="MAX_CONTRACT_BYTES"):
        validate_contract(oversized, PLAN_SCHEMA, version())


def test_validate_contract_checks_text_and_bytearray_budgets_before_parsing() -> None:
    oversized_text = "{" + ("x" * MAX_CONTRACT_BYTES)
    oversized_bytearray = bytearray(b"{" + (b"x" * MAX_CONTRACT_BYTES))

    for raw in (oversized_text, oversized_bytearray):
        with pytest.raises(ContractValidationError, match="MAX_CONTRACT_BYTES"):
            validate_contract(raw, PLAN_SCHEMA, version())


def test_validate_contract_rejects_deep_json_before_parser_recursion() -> None:
    depth = MAX_CONTRACT_DEPTH + 100
    deeply_nested = "[" * depth + "0" + "]" * depth

    with pytest.raises(ContractValidationError, match="MAX_CONTRACT_DEPTH"):
        validate_contract(deeply_nested, PLAN_SCHEMA, version())

def _runtime_accepts(raw: object, schema_uri: str = PLAN_SCHEMA) -> bool:
    try:
        validate_contract(raw, schema_uri, version())
    except ContractValidationError:
        return False
    return True


def test_generated_schema_and_runtime_agree_on_path_and_version_boundaries() -> None:
    generated = json.loads(schema_bytes(PLAN_SCHEMA))
    path_schema = generated["$defs"]["BoundedScope"]["properties"]["paths"]["items"]
    version_schema = generated["$defs"]["ContractVersion"]["properties"]

    assert path_schema["pattern"] == (
        r"^(?!/)(?!\.{1,2}$)(?!.*(?:^|/)\.\.(?:/|$))[\s\S]+$"
    )
    assert version_schema["schema_uri"]["const"] == PLAN_SCHEMA
    assert version_schema["major"]["const"] == "1"
    assert version_schema["minor"]["const"] == "0"

    valid = raw_plan()
    invalid_path = raw_plan()
    invalid_path["curds"][0]["scope"]["paths"] = ["src/../secrets"]
    invalid_major = raw_plan(major="2")

    assert _runtime_accepts(valid)
    assert not _runtime_accepts(invalid_path)
    assert not _runtime_accepts(invalid_major)


def test_nested_contract_version_schema_is_exact_for_each_enclosing_model() -> None:
    result_schema = json.loads(
        schema_bytes(f"{SCHEMA_ROOT}/planner-result")
    )
    version_schema = result_schema["$defs"]["ContractVersion"]["properties"]
    nested_schema = result_schema["$defs"]["CurdPlanContractVersion"]["properties"]

    assert version_schema["schema_uri"]["const"] == f"{SCHEMA_ROOT}/planner-result"
    assert nested_schema["schema_uri"]["const"] == PLAN_SCHEMA
    assert version_schema["major"]["const"] == nested_schema["major"]["const"] == "1"
    assert version_schema["minor"]["const"] == nested_schema["minor"]["const"] == "0"


def test_validate_contract_rejects_decoded_tree_over_depth_budget() -> None:
    root: dict[str, object] = {}
    cursor = root
    for _ in range(MAX_CONTRACT_DEPTH + 1):
        child: dict[str, object] = {}
        cursor["child"] = child
        cursor = child
    with pytest.raises(ContractValidationError, match="MAX_CONTRACT_DEPTH"):
        validate_contract(root, PLAN_SCHEMA, version())


def test_validate_contract_rejects_non_string_version_components() -> None:
    with pytest.raises(
        ContractValidationError,
        match=r"\$\.contract_version\.major must be a string",
    ):
        validate_contract(raw_plan(major=1), PLAN_SCHEMA, version())


def test_validate_contract_rejects_invented_target_minor_without_catalog_support() -> None:
    with pytest.raises(
        ContractValidationError,
        match="supported_version must equal the catalog's current version",
    ):
        validate_contract(
            raw_plan(minor="0", digest_minor="0"),
            PLAN_SCHEMA,
            version(minor="2"),
        )


def test_normalize_agent_output_adds_host_owned_plan_fields_deterministically() -> None:
    invocation = {
        "contract_version": version(),
        "plan_id": "plan-host",
        "revision": 3,
    }

    first = normalize_agent_output(writer_plan(), invocation)
    second = normalize_agent_output(writer_plan(), invocation)
    assert normalize_agent_value(writer_plan(), invocation) == first.value

    assert first == second
    assert isinstance(first.value, CurdPlan)
    assert first.value.plan_id == "plan-host"
    assert first.value.revision == 3
    assert first.value.curds[0].curd_id == "plan-host/curd/1"
    assert (
        first.value.curds[0].criteria[0].criterion_id
        == "plan-host/curd/1/criterion/1"
    )
    assert first.value.curds[0].outcome == "Implement strict validation"
    assert first.value.digest.startswith("sha256:")


def test_normalize_agent_output_rejects_stale_lineage_for_unknown_writer_curd() -> None:
    invocation = {
        "contract_version": version(),
        "plan_id": "plan-host",
        "lineages": {
            "removed-curd": {
                "identity_action": "new",
                "source_curd_ids": [],
            }
        },
    }

    with pytest.raises(
        ContractValidationError,
        match="invocation.lineages has unknown curd keys",
    ):
        normalize_agent_output(writer_plan(), invocation)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("payload", "plan_id"), "agent-plan", "host-owned field 'plan_id'"),
        (
            ("payload", "curds", 0, "curd_id"),
            "agent-curd",
            "host-owned field 'curd_id'",
        ),
        (
            ("payload", "curds", 0, "criteria", 0, "criterion_id"),
            "agent-criterion",
            "host-owned field 'criterion_id'",
        ),
    ],
)
def test_normalize_agent_output_rejects_agent_supplied_host_identity(
    path: tuple[str | int, ...], value: object, message: str
) -> None:
    raw = writer_plan()
    target = raw
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = value

    with pytest.raises(ContractValidationError, match=message):
        normalize_agent_output(
            raw,
            {
                "contract_version": version(),
                "plan_id": "plan-host",
            },
        )


def test_normalize_agent_output_rejects_duplicate_json_fields() -> None:
    raw = '{"kind":"curd_plan","kind":"curd_plan","payload":{}}'

    with pytest.raises(ContractValidationError, match="duplicate field 'kind'"):
        normalize_agent_output(
            raw,
            {
                "contract_version": version(),
                "plan_id": "plan-host",
            },
        )
