from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Protocol, cast

import pytest
import yaml

from easy_cheese_schemas._phase_registry_compiler import (
    compile_phase_declarations,
    parse_phase_yaml,
)
from easy_cheese_schemas.phase_contracts import (
    COMPILED_TRANSITION_REGISTRY,
    CURD_PLAN_SCHEMA_URI,
    CURD_RESULT_SCHEMA_URI,
    PHASE_CONTRACT_SCHEMA_URI,
    PLANNER_REQUEST_SCHEMA_URI,
    TransitionError,
    validate_transition,
)

if TYPE_CHECKING:
    from easy_cheese_schemas.phase_contracts import CompiledTransition, TransitionRegistry

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SCRIPTS = REPO_ROOT / "src" / "easy_cheese" / "shared"
WRITER_PATH = SHARED_SCRIPTS / "write_handoff_artifact.py"
DECLARATIONS = (
    REPO_ROOT / "skills" / "age" / "phase-contract.yaml",
    REPO_ROOT / "skills" / "cook" / "phase-contract.yaml",
    REPO_ROOT / "skills" / "cure" / "phase-contract.yaml",
    REPO_ROOT / "skills" / "mold" / "phase-contract.yaml",
    REPO_ROOT / "skills" / "press" / "phase-contract.yaml",
)


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _CliModule(Protocol):
    CliError: type[Exception]


class _WriterModule(Protocol):
    cli: _CliModule
    COMPILED_TRANSITION_REGISTRY: TransitionRegistry

    def validate_transition(
        self,
        registry: TransitionRegistry,
        source: str,
        destination: str,
        payload_schema_uri: str | None = None,
    ) -> CompiledTransition | None: ...

    def write_artifact(
        self,
        *,
        slug: str,
        status: str,
        next_skill: str,
        artifact: str,
        orientation: str,
        body: str | None,
        root: Path,
        phase: str,
        payload_schema_uri: str | None = None,
        taste_test: str | None = None,
        durable_flags: str | None = None,
        baseline: str | None = None,
    ) -> Path: ...


class _BuildPyzModule(Protocol):
    REPO_ROOT: Path
    SCHEMA_CONTRACT_SOURCE: Path

    def _compiled_phase_registry_source(self) -> str: ...

    def _checked_in_generated_file_bytes(
        self, expected_source: str, source: Path, *, artifact_name: str
    ) -> bytes: ...

    def _compiled_schema_catalog_source(self) -> str: ...

    def build_bundle(self, skill: str, target: Path) -> Path: ...


@pytest.fixture(scope="module")
def writer() -> _WriterModule:
    if str(SHARED_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SHARED_SCRIPTS))
    _ = _load("cli", SHARED_SCRIPTS / "cli.py")
    _ = _load("handoff", SHARED_SCRIPTS / "handoff.py")
    return cast(_WriterModule, cast(object, _load("phase_contract_writer", WRITER_PATH)))


def as_dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value)


def as_list(value: object) -> list[object]:
    return cast(list[object], value)


def _declarations() -> list[dict[str, object]]:
    return [
        cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
        for path in DECLARATIONS
    ]


def test_phase_declarations_compile_to_embedded_registry_deterministically() -> None:
    declarations = _declarations()

    forward = compile_phase_declarations(declarations)
    reverse = compile_phase_declarations(reversed(declarations))
    assert forward.to_json() == reverse.to_json() == COMPILED_TRANSITION_REGISTRY.to_json()


def test_phase_declarations_use_canonical_registered_schema_ids() -> None:
    declarations = _declarations()
    canonical = "https://schemas.easy-cheese.dev/"
    mold = next(item for item in declarations if item["source"] == "mold")
    assert as_dict(mold["contract_version"])["schema_uri"] == PHASE_CONTRACT_SCHEMA_URI
    assert mold["input_schema_uris"] == [PLANNER_REQUEST_SCHEMA_URI]
    for declaration in declarations:
        assert (
            as_dict(declaration["contract_version"])["schema_uri"]
            == PHASE_CONTRACT_SCHEMA_URI
        )
        assert all(
            cast(str, uri).startswith(canonical)
            for uri in as_list(declaration["input_schema_uris"])
        )
        assert all(
            cast(str, as_dict(route)["payload_schema_uri"]).startswith(canonical)
            for route in as_list(declaration["outputs"])
        )

    mold["input_schema_uris"] = ["urn:easy-cheese:schema:planner-request:1.0"]
    with pytest.raises(ValueError, match="schema URI"):
        _ = compile_phase_declarations([mold])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "schema_uri",
            "https://schemas.easy-cheese.dev/phase-contract:1.0",
            "canonical PhaseContract",
        ),
        ("major", "2", "unsupported phase contract major"),
        ("minor", "1", "future phase contract minor"),
    ],
)
def test_compile_rejects_unsupported_phase_contract_version(
    field: str, value: str, message: str
) -> None:
    declaration = _declarations()[0]
    as_dict(declaration["contract_version"])[field] = value
    with pytest.raises(ValueError, match=message):
        _ = compile_phase_declarations([declaration])


def test_compile_rejects_unregistered_payload_schema() -> None:
    declaration = _declarations()[0]
    as_dict(as_list(declaration["outputs"])[0])["payload_schema_uri"] = (
        "https://schemas.easy-cheese.dev/not-registered"
    )
    with pytest.raises(ValueError, match="registered canonical schema URI"):
        _ = compile_phase_declarations([declaration])


def test_compile_rejects_route_not_declared_by_registered_destination() -> None:
    declaration = _declarations()[0]
    as_dict(as_list(declaration["outputs"])[0])["payload_schema_uri"] = CURD_RESULT_SCHEMA_URI
    with pytest.raises(ValueError, match="destination input"):
        _ = compile_phase_declarations([declaration, *_declarations()[1:]])


def test_writer_uses_the_compiled_registry_projection(writer: _WriterModule) -> None:
    from easy_cheese_schemas import phase_contracts

    assert not hasattr(writer, "_TRANSITION_REGISTRY")
    assert not hasattr(writer, "resolve_compiled_transition")
    assert writer.validate_transition(
        writer.COMPILED_TRANSITION_REGISTRY,
        "mold",
        "cook",
        CURD_PLAN_SCHEMA_URI,
    ) == phase_contracts.validate_transition(
        phase_contracts.COMPILED_TRANSITION_REGISTRY,
        "mold",
        "cook",
        CURD_PLAN_SCHEMA_URI,
    )


def test_generated_registry_projection_matches_declarations() -> None:
    from easy_cheese_schemas import _compiled_phase_registry as generated
    from easy_cheese_schemas import phase_contracts

    compiled = compile_phase_declarations(_declarations())
    assert generated.PHASE_REGISTRY_JSON == compiled.to_json()
    assert phase_contracts.COMPILED_TRANSITION_REGISTRY.to_json() == compiled.to_json()
    assert not hasattr(generated, "validate_transition")


def test_checked_in_registry_projection_matches_build_generator() -> None:
    scripts = REPO_ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    build_pyz: _BuildPyzModule = cast(
        _BuildPyzModule, cast(object, _load("phase_contract_build_pyz", scripts / "build_pyz.py"))
    )

    assert (
        REPO_ROOT / "src" / "easy_cheese_schemas" / "_compiled_phase_registry.py"
    ).read_text(encoding="utf-8") == build_pyz._compiled_phase_registry_source()



def _write_phase_yaml(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        "\n".join(
            [
                "contract_version:",
                "  schema_uri: https://schemas.easy-cheese.dev/phase-contract",
                '  major: "1"',
                '  minor: "0"',
                f"source: {source}",
                "input_schema_uris:",
                "  - https://schemas.easy-cheese.dev/planner-request",
                "outputs:",
                "  - destination: age",
                "    payload_schema_uri: https://schemas.easy-cheese.dev/curd-result",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_build_compiler_is_clean_bootstrap_safe_and_fresh_per_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts = REPO_ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    build_pyz: _BuildPyzModule = cast(
        _BuildPyzModule,
        cast(object, _load("phase_contract_build_bootstrap", scripts / "build_pyz.py")),
    )
    monkeypatch.setattr(build_pyz, "REPO_ROOT", tmp_path)
    declaration = tmp_path / "skills" / "smoke" / "phase-contract.yaml"
    _write_phase_yaml(declaration, "smoke")

    first = build_pyz._compiled_phase_registry_source()
    _ = declaration.write_text(
        declaration.read_text(encoding="utf-8").replace("source: smoke", "source: fresh"),
        encoding="utf-8",
    )
    second = build_pyz._compiled_phase_registry_source()

    assert "source\": \"smoke\"" in first
    assert "source\": \"fresh\"" in second
    assert first != second


@pytest.mark.parametrize(
    ("source_name", "artifact_name"),
    [
        ("_schema_catalog.py", "schema catalog"),
        ("_compiled_phase_registry.py", "phase registry"),
    ],
)
def test_checked_in_generated_file_bytes_covers_missing_stale_and_matching(
    tmp_path: Path,
    source_name: str,
    artifact_name: str,
) -> None:
    scripts = REPO_ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    build_pyz: _BuildPyzModule = cast(
        _BuildPyzModule,
        cast(
            object,
            _load(
                f"generated_file_validator_{artifact_name.replace(' ', '_')}",
                scripts / "build_pyz.py",
            ),
        ),
    )
    generated = tmp_path / source_name
    validate = build_pyz._checked_in_generated_file_bytes

    with pytest.raises(RuntimeError) as missing:
        _ = validate(
            "current",
            generated,
            artifact_name=artifact_name,
        )
    assert str(missing.value) == f"checked-in {artifact_name} is missing: {generated}"

    _ = generated.write_bytes(b"stale")
    with pytest.raises(RuntimeError) as stale:
        _ = validate(
            "current",
            generated,
            artifact_name=artifact_name,
        )
    assert (
        str(stale.value)
        == f"checked-in {artifact_name} is stale; regenerate {generated}"
    )

    expected = b"current"
    _ = generated.write_bytes(expected)
    assert (
        validate(
            "current",
            generated,
            artifact_name=artifact_name,
        )
        == expected
    )


def test_checked_in_catalog_projection_matches_build_generator() -> None:
    scripts = REPO_ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    build_pyz: _BuildPyzModule = cast(
        _BuildPyzModule, cast(object, _load("schema_catalog_build_pyz", scripts / "build_pyz.py"))
    )

    assert (
        REPO_ROOT / "src" / "easy_cheese_schemas" / "_schema_catalog.py"
    ).read_text(encoding="utf-8") == build_pyz._compiled_schema_catalog_source()


def test_schema_catalog_compilation_is_fresh_per_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts = REPO_ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    build_pyz: _BuildPyzModule = cast(
        _BuildPyzModule,
        cast(object, _load("schema_catalog_build_fresh", scripts / "build_pyz.py")),
    )
    source = REPO_ROOT / "src" / "easy_cheese_schemas" / "contracts.py"
    staged = tmp_path / "contracts.py"
    _ = staged.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(build_pyz, "SCHEMA_CONTRACT_SOURCE", staged)

    first = build_pyz._compiled_schema_catalog_source()
    _ = staged.write_text(
        staged.read_text(encoding="utf-8").replace(
            '@contract("curd-plan")', '@contract("fresh-plan")', 1
        ),
        encoding="utf-8",
    )
    second = build_pyz._compiled_schema_catalog_source()

    assert "curd-plan" in first
    assert "fresh-plan" in second
    assert first != second


def test_bundle_build_rejects_stale_checked_in_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts = REPO_ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    build_pyz: _BuildPyzModule = cast(
        _BuildPyzModule,
        cast(object, _load("schema_catalog_build_stale", scripts / "build_pyz.py")),
    )
    source = REPO_ROOT / "src" / "easy_cheese_schemas" / "contracts.py"
    staged = tmp_path / "contracts.py"
    _ = staged.write_text(
        source.read_text(encoding="utf-8").replace(
            '@contract("curd-plan")', '@contract("fresh-plan")', 1
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(build_pyz, "SCHEMA_CONTRACT_SOURCE", staged)
    target = tmp_path / "cook.pyz"

    with pytest.raises(RuntimeError, match="checked-in schema catalog is stale"):
        _ = build_pyz.build_bundle("cook", target)

    assert not target.exists()


def test_compile_rejects_duplicate_source() -> None:
    declaration = _declarations()[0]

    with pytest.raises(
        ValueError,
        match=f"duplicate phase source {declaration['source']!r}",
    ):
        _ = compile_phase_declarations([declaration, declaration])


def test_compile_rejects_duplicate_output_route() -> None:
    declaration = _declarations()[0]
    as_list(declaration["outputs"]).append(dict(as_dict(as_list(declaration["outputs"])[0])))

    with pytest.raises(ValueError, match="duplicate output transitions"):
        _ = compile_phase_declarations([declaration])

def test_parse_phase_yaml_rejects_duplicate_authority_fields() -> None:
    with pytest.raises(ValueError, match=r"duplicate field 'major'"):
        _ = parse_phase_yaml(
            "\n".join(
                [
                    "contract_version:",
                    "  schema_uri: https://schemas.easy-cheese.dev/phase-contract",
                    '  major: "1"',
                    '  major: "2"',
                    '  minor: "0"',
                    "source: smoke",
                    "input_schema_uris:",
                    "  - https://schemas.easy-cheese.dev/planner-request",
                    "outputs:",
                    "  - destination: age",
                    "    payload_schema_uri: https://schemas.easy-cheese.dev/curd-result",
                ]
            )
        )


@pytest.mark.parametrize("component", [1, "01", "١"])
def test_compile_requires_canonical_decimal_version_components(
    component: object,
) -> None:
    declaration = _declarations()[0]
    as_dict(declaration["contract_version"])["major"] = component

    with pytest.raises(ValueError, match="major must be a canonical decimal string"):
        _ = compile_phase_declarations([declaration])


def test_compile_rejects_non_uri_schema_reference() -> None:
    declaration = _declarations()[0]
    declaration["input_schema_uris"] = ["not-a-uri"]

    with pytest.raises(
        ValueError, match=r"input_schema_uris\[0\] must be a schema URI"
    ):
        _ = compile_phase_declarations([declaration])


def test_registry_runtime_does_not_import_yaml() -> None:
    code = (
        "import sys;"
        "sys.path[:0] = sys.argv[1:];"
        "sys.modules['yaml'] = None;"
        "from easy_cheese_schemas.phase_contracts import "
        "COMPILED_TRANSITION_REGISTRY as registry;"
        "print(','.join(registry.sources))"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(REPO_ROOT / "src"),
            str(REPO_ROOT / "vendor"),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout == "age,cook,cure,mold,press\n"


def test_validate_transition_returns_the_declared_route() -> None:
    route = validate_transition(
        COMPILED_TRANSITION_REGISTRY,
        source="mold",
        destination="cook",
        payload_schema_uri=CURD_PLAN_SCHEMA_URI,
    )

    assert route is not None
    assert route.source == "mold"
    assert route.destination == "cook"
    assert route.payload_schema_uri == CURD_PLAN_SCHEMA_URI


@pytest.mark.parametrize(
    ("source", "destination", "payload_schema_uri", "message"),
    [
        ("unknown", "cook", CURD_PLAN_SCHEMA_URI, "unknown source phase 'unknown'"),
        ("mold", "cure", CURD_PLAN_SCHEMA_URI, "mold -> cure is not declared"),
        ("mold", "cook", CURD_RESULT_SCHEMA_URI, "payload schema .* is not declared"),
    ],
)
def test_validate_transition_rejects_each_invalid_dimension(
    source: str,
    destination: str,
    payload_schema_uri: str,
    message: str,
) -> None:
    with pytest.raises(TransitionError, match=message):
        _ = validate_transition(
            COMPILED_TRANSITION_REGISTRY,
            source=source,
            destination=destination,
            payload_schema_uri=payload_schema_uri,
        )


def test_writer_validates_registered_transition_and_preserves_phase_path(
    writer: _WriterModule, tmp_path: Path
) -> None:
    target = writer.write_artifact(
        slug="approved-plan",
        status="ok",
        phase="mold",
        next_skill="cook",
        payload_schema_uri=CURD_PLAN_SCHEMA_URI,
        artifact="",
        orientation="mold produced a curd plan",
        body=None,
        root=tmp_path,
    )

    assert target == tmp_path / ".cheese" / "mold" / "approved-plan.md"
    assert target.read_text(encoding="utf-8").splitlines()[:4] == [
        "status: ok",
        "next: cook",
        "artifact: ",
        "mold produced a curd plan",
    ]


def test_writer_rejects_invalid_transition_before_creating_directories(
    writer: _WriterModule, tmp_path: Path
) -> None:
    with pytest.raises(writer.cli.CliError, match="mold -> cure is not declared"):
        _ = writer.write_artifact(
            slug="bad-route",
            status="ok",
            phase="mold",
            next_skill="cure",
            payload_schema_uri=CURD_PLAN_SCHEMA_URI,
            artifact="",
            orientation="must not be written",
            body=None,
            root=tmp_path,
        )

    assert not (tmp_path / ".cheese").exists()


def test_writer_rejects_wrong_schema_before_creating_directories(
    writer: _WriterModule, tmp_path: Path
) -> None:
    with pytest.raises(writer.cli.CliError, match="payload schema .* not declared"):
        _ = writer.write_artifact(
            slug="wrong-schema",
            status="ok",
            phase="mold",
            next_skill="cook",
            payload_schema_uri="urn:easy-cheese:schema:curd-plan:1.0",
            artifact="",
            orientation="must not be written",
            body=None,
            root=tmp_path,
        )

    assert not (tmp_path / ".cheese").exists()


def test_writer_rejects_missing_phase_before_creating_directories(
    writer: _WriterModule, tmp_path: Path
) -> None:
    with pytest.raises(writer.cli.CliError, match="--phase must be non-empty"):
        _ = writer.write_artifact(
            slug="missing-phase",
            status="ok",
            phase="",
            next_skill="done",
            artifact="",
            orientation="must not be written",
            body=None,
            root=tmp_path,
        )

    assert not (tmp_path / ".cheese").exists()


def test_writer_rejects_unknown_phase_before_creating_directories(
    writer: _WriterModule, tmp_path: Path
) -> None:
    with pytest.raises(writer.cli.CliError, match="unknown source phase 'unknown'"):
        _ = writer.write_artifact(
            slug="unknown-phase",
            status="ok",
            phase="unknown",
            next_skill="done",
            artifact="",
            orientation="must not be written",
            body=None,
            root=tmp_path,
        )

    assert not (tmp_path / ".cheese").exists()


def test_writer_never_follows_preplaced_predictable_tmp_symlink(
    writer: _WriterModule, tmp_path: Path
) -> None:
    target_dir = tmp_path / ".cheese" / "press"
    target_dir.mkdir(parents=True)
    sentinel = tmp_path / "sentinel"
    _ = sentinel.write_text("untouched", encoding="utf-8")
    predictable_tmp = target_dir / "safe.md.tmp"
    predictable_tmp.symlink_to(sentinel)

    target = writer.write_artifact(
        slug="safe",
        status="ok",
        phase="press",
        next_skill="age",
        artifact="",
        orientation="press completed",
        body=None,
        root=tmp_path,
    )

    assert target.exists()
    assert sentinel.read_text(encoding="utf-8") == "untouched"
    assert predictable_tmp.is_symlink()

def test_unregistered_legacy_age_route_preserves_phase_path(
    writer: _WriterModule, tmp_path: Path
) -> None:
    target = writer.write_artifact(
        slug="legacy-age-route",
        status="ok",
        phase="age",
        next_skill="cure",
        artifact="",
        orientation="legacy age handoff",
        body=None,
        root=tmp_path,
    )

    assert target == tmp_path / ".cheese" / "age" / "legacy-age-route.md"


def test_registered_writer_route_can_infer_its_only_payload_schema(
    writer: _WriterModule, tmp_path: Path
) -> None:
    target = writer.write_artifact(
        slug="legacy-cook-call",
        status="ok",
        phase="cook",
        next_skill="press",
        artifact="",
        orientation="cook completed its curds",
        body=None,
        root=tmp_path,
    )

    assert target == tmp_path / ".cheese" / "cook" / "legacy-cook-call.md"


def test_terminal_outcome_preserves_registered_phase_path(
    writer: _WriterModule, tmp_path: Path
) -> None:
    target = writer.write_artifact(
        slug="terminal-cure",
        status="ok",
        phase="cure",
        next_skill="done",
        artifact="",
        orientation="cure completed the review cycle",
        body=None,
        root=tmp_path,
    )

    assert target == tmp_path / ".cheese" / "cure" / "terminal-cure.md"
