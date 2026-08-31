from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import venv
from importlib.util import find_spec
from pathlib import Path
from typing import cast

import pytest

from easy_cheese_schemas.contracts import CurdPlan
import easy_cheese_schemas as schemas

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_NAMES = ("contract-cases.json", "normalization-cases.json")

def _plan() -> CurdPlan:
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
                        "description": "The installed wheel exposes the contract API",
                        "check": (
                            "pytest "
                            "tests/schemas/python/test_contract_package_api.py"
                        ),
                    }
                ],
                "lineage": {
                    "identity_action": "new",
                    "source_curd_ids": [],
                },
            }
        ],
        "context": None,
        "parent_plan_ref": None,
    }
    raw: dict[str, object] = {**unsigned, "digest": schemas.canonical_digest(unsigned)}
    artifact = schemas.validate_contract(
        raw,
        CurdPlan,
        version,
    )
    return cast(CurdPlan, artifact.value)


def test_top_level_package_exposes_stable_contract_api() -> None:
    expected = {
        "AgentWriterView",
        "ArtifactRef",
        "BenchmarkReport",
        "CurdPlan",
        "CurdResult",
        "CureDiagnosisBinding",
        "DiagnosisResult",
        "PhaseContract",
        "PlannerRequest",
        "PlannerResult",
        "ReviewResult",
        "SemanticCurd",
        "SourceCurdRef",
        "SourcePlanRef",
        "WriterBudgetExceeded",
        "WriterCheckpoint",
        "benchmark_contracts",
        "canonical_bytes",
        "canonical_digest",
        "cook",
        "cure",
        "list_conformance_fixtures",
        "load_conformance_fixture",
        "materialize_planner_result",
        "curd_plan_digest",
        "normalize_agent_value",
        "validate_curd_plan",
        "normalize_agent_output",
        "plan",
        "project_curd_block",
        "read_conformance_fixture",
        "resolve_artifact",
        "run_workflow",
        "schema_bytes",
        "supported_version_for",
        "validate_contract",
        "validate_transition",
    }
    assert expected <= set(schemas.__all__)
    assert all(hasattr(schemas, name) for name in expected)
    assert "REGISTERED_CONTRACTS" not in schemas.__all__
    assert "SUPPORTED_CONTRACT_VERSIONS" not in schemas.__all__
    assert not hasattr(schemas, "REGISTERED_CONTRACTS")
    assert not hasattr(schemas, "SUPPORTED_CONTRACT_VERSIONS")
    assert schemas.__version__ == "1.1.0"


def test_canonical_plan_digest_is_verified_by_strict_runtime() -> None:
    plan = _plan()
    raw = schemas.canonical_bytes(plan)
    validated = schemas.validate_contract(
        raw,
        schemas.CurdPlan,
        schemas.supported_version_for(schemas.CurdPlan),
    )
    assert validated.value == plan
    assert schemas.curd_plan_digest(plan) == plan.digest
    assert schemas.canonical_digest(plan) == (
        f"sha256:{hashlib.sha256(raw).hexdigest()}"
    )

    tampered = cast("dict[str, object]", json.loads(raw))
    tampered["objective"] = "Tampered objective"
    with pytest.raises(schemas.ContractValidationError, match="CurdPlan digest mismatch"):
        _ = schemas.validate_contract(
            tampered,
            schemas.CurdPlan,
            schemas.supported_version_for(schemas.CurdPlan),
        )


def test_conformance_resource_api_is_bounded_and_returns_fresh_values() -> None:
    assert schemas.list_conformance_fixtures() == FIXTURE_NAMES
    for name in FIXTURE_NAMES:
        raw = schemas.read_conformance_fixture(name)
        assert raw == (
            REPO_ROOT / "src/easy_cheese_schemas/conformance/v1" / name
        ).read_bytes()
        first = schemas.load_conformance_fixture(name)
        second = schemas.load_conformance_fixture(name)
        assert first == second
        assert first is not second

    for invalid in ("../contract-cases.json", "/tmp/contract-cases.json", "unknown.json"):
        with pytest.raises(ValueError, match="unknown conformance fixture"):
            _ = schemas.read_conformance_fixture(invalid)


def test_installed_wheel_exposes_exact_bundled_fixtures(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "dist"
    _ = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--wheel-dir",
            str(wheel_dir),
            str(REPO_ROOT),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(wheel_dir.glob("easy_cheese_schemas-1.1.0-*.whl"))
    environment = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    site_packages = next((environment / "lib").glob("python*/site-packages"))
    dependency_roots: set[str] = set()
    for dependency in ("attrs", "cattrs"):
        spec = find_spec(dependency)
        assert spec is not None and spec.origin is not None
        dependency_roots.add(str(Path(spec.origin).resolve().parent.parent))
    _ = (site_packages / "_easy_cheese_runtime_dependencies.pth").write_text(
        "\n".join(sorted(dependency_roots)) + "\n"
    )
    _ = subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", str(wheel)],
        check=True,
        capture_output=True,
        text=True,
    )

    expected = {
        name: hashlib.sha256(
            (REPO_ROOT / "src/easy_cheese_schemas/conformance/v1" / name).read_bytes()
        ).hexdigest()
        for name in FIXTURE_NAMES
    }
    script = """
import hashlib
import json
from importlib import metadata
from pathlib import Path
import easy_cheese_schemas as schemas

assert schemas.__version__ == "1.1.0"
assert metadata.version("easy-cheese-schemas") == "1.1.0"
assert Path(schemas.__file__).resolve().is_relative_to(Path(__import__("sys").prefix))
actual = {
    name: hashlib.sha256(schemas.read_conformance_fixture(name)).hexdigest()
    for name in schemas.list_conformance_fixtures()
}
assert actual == json.loads(__import__("os").environ["EXPECTED_FIXTURES"])
"""
    child_env = os.environ.copy()
    child_env["EXPECTED_FIXTURES"] = json.dumps(expected, sort_keys=True)
    child_env["PYTHONNOUSERSITE"] = "1"
    _ = child_env.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [str(python), "-c", script],
        cwd=tmp_path,
        env=child_env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
