"""Protected outer oracle for decorator markers, graph wiring, CLI I/O, and Vulture."""

from __future__ import annotations

import ast
import importlib
import json
import importlib.util
import io
import subprocess
import sys
import zipfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]

AC1 = "with `@contract` removed from `CurdPlan`, the generated catalog omits the `curd-plan` URI and `REGISTERED_CONTRACT_SCHEMA_URIS` holds 9 entries, not 10"
AC2 = "a contract class whose marker is absent is unresolvable through `_registered`, raising instead of returning a `_RegisteredContract`"
AC4 = "a manifest containing the cycle `W1 -> W2 -> W1` yields `the dependency graph has cycle W1 -> W2 -> W1` through both callers; today fanout returns `wiring DAG has cycle: ...` instead"
AC5 = '`cli.run(setup, argv=["--json"], stdout=StringIO())` returns an int; against the current `def run(setup) -> NoReturn` it raises `TypeError` for the unexpected keyword argument `argv`'
AC6 = "a function body containing a statement after an unconditional `return` is reported and the recipe exits non-zero"
AC7 = "`_model_constraints` still resolves as an attribute, or a `__schema_constraints__` assignment exists at any line other than `contracts.py:309` and `:345`"
AC8 = '`cli.emit({"a": 1}, stdout=StringIO())` raises `TypeError` for the unexpected keyword argument `stdout`, since `cli.py:56` accepts only `limit`, `full`, and `json_mode`; once accepted, the buffer must hold the emitted text rather than the process stdout'
AC9 = 'the assertion pairs "`src/easy_cheese_schemas/_schema_catalog_compiler.py` exists in source" with "it is absent from every built bundle and the wheel"; today the first half fails because the module does not exist, and once it does, `PACKAGE_TREES` copytree ships it into six bundles until `build_pyz.py:431` excludes it'
AC10 = "importing `compute_waves` from `easy_cheese_schemas.wiring_graph` raises `ImportError`, since it exists only at `fanout/wiring_topo_sort.py:32` today"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_ac1_catalog_is_compiled_from_contract_markers() -> None:
    contracts = importlib.import_module("easy_cheese_schemas.contracts")
    catalog = importlib.import_module("easy_cheese_schemas._schema_catalog")
    try:
        compiler = importlib.import_module(
            "easy_cheese_schemas._schema_catalog_compiler"
        )
        marker = contracts.CurdPlan.__contract_slug__
    except (AttributeError, ModuleNotFoundError):
        assert False, AC1
    del contracts.CurdPlan.__contract_slug__
    try:
        namespace: dict[str, Any] = {}
        exec(compiler.render(compiler.collect(contracts)), namespace)
    finally:
        contracts.CurdPlan.__contract_slug__ = marker
    assert namespace["REGISTERED_CONTRACT_SCHEMA_URIS"] == (
        catalog.REGISTERED_CONTRACT_SCHEMA_URIS - {catalog.CURD_PLAN_SCHEMA_URI}
    ), AC1


def test_ac2_runtime_registry_is_marker_derived() -> None:
    contracts = importlib.import_module("easy_cheese_schemas.contracts")
    runtime = importlib.import_module("easy_cheese_schemas.schema_runtime")
    marked = {
        value
        for value in vars(contracts).values()
        if isinstance(value, type) and getattr(value, "__contract_slug__", None)
    }
    registered = {entry.contract for entry in runtime._REGISTERED_CONTRACTS}
    assert registered == marked, AC2


def test_ac4_manifest_and_fanout_share_cycle_wording() -> None:
    manifest = importlib.import_module("easy_cheese_schemas.manifest")
    sys.path[:0] = [str(ROOT / "shared" / "scripts"), str(ROOT / "src" / "fanout")]
    try:
        wiring = _load("cut_oracle_wiring", ROOT / "src" / "fanout" / "wiring.py")
    finally:
        del sys.path[:2]
    rows = [
        manifest.WiringRow("W1", "config_entry", "a", ["W2"], "pending"),
        manifest.WiringRow("W2", "config_entry", "b", ["W1"], "pending"),
    ]
    with pytest.raises(ValueError) as raised:
        manifest.reject_unschedulable_wiring(None, SimpleNamespace(name="wiring"), rows)
    expected = "the dependency graph has cycle W1 -> W2 -> W1"
    fanout_errors = wiring.graph_errors(
        [{"id": "W1", "depends_on": ["W2"]}, {"id": "W2", "depends_on": ["W1"]}]
    )
    assert str(raised.value) == f"wiring must be schedulable: {expected}", AC4
    assert fanout_errors == [expected], AC4


def test_ac5_cli_run_accepts_injected_argv_and_stdout() -> None:
    cli = _load("cut_oracle_cli_run", ROOT / "shared" / "scripts" / "cli.py")
    output = io.StringIO()

    def setup(parser: Any) -> None:
        parser.set_defaults(
            func=lambda args: cli.emit(
                {"ok": True}, json_mode=args.json_mode, stdout=args.stdout
            )
        )

    try:
        status = cli.run(setup, argv=["--json"], stdout=output)
    except TypeError:
        assert False, AC5
    assert status == 0 and json.loads(output.getvalue()) == {"ok": True}, AC5


def test_ac6_vulture_recipe_reports_unreachable_code() -> None:
    probe = ROOT / "src" / "_vulture_gate_probe.py"
    probe.write_text(
        "def probe():\n    return 1\n    print('unreachable')\n\nprobe()\n",
        encoding="utf-8",
    )
    try:
        result = subprocess.run(
            ["just", "lint-dead"], cwd=ROOT, text=True, capture_output=True, check=False
        )
    finally:
        probe.unlink(missing_ok=True)
    output = result.stdout + result.stderr
    expected = (
        "src/_vulture_gate_probe.py:3: unreachable code after "
        "'return' (100% confidence)"
    )
    assert result.returncode == 3 and expected in output, AC6


def test_ac7_only_dynamic_constraint_assignments_remain() -> None:
    contracts = importlib.import_module("easy_cheese_schemas.contracts")
    runtime = importlib.import_module("easy_cheese_schemas.schema_runtime")
    source = ROOT / "src" / "easy_cheese_schemas" / "contracts.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    assignments = []
    for statement in tree.body:
        scope = statement.name if isinstance(statement, ast.FunctionDef) else None
        for node in ast.walk(statement):
            if not isinstance(node, ast.Assign):
                continue
            assignments.extend(
                (scope, target.value.id)
                for target in node.targets
                if isinstance(target, ast.Attribute)
                and target.attr == "__schema_constraints__"
                and isinstance(target.value, ast.Name)
            )

    assert not hasattr(runtime, "_model_constraints"), AC7
    assert assignments == [
        ("_list_of", "validate"),
        ("_string_list", "validate"),
    ], AC7
    assert contracts._list_of(str, non_empty=True, limit=3).__schema_constraints__ == {
        "maxItems": 3,
        "minItems": 1,
    }, AC7
    assert contracts._string_list(non_empty=True, limit=4).__schema_constraints__ == {
        "maxItems": 4,
        "uniqueItems": True,
        "minItems": 1,
    }, AC7


def test_ac8_cli_emit_writes_only_to_injected_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load("cut_oracle_cli_emit", ROOT / "shared" / "scripts" / "cli.py")
    output = io.StringIO()
    try:
        cli.emit({"a": 1}, stdout=output)
    except TypeError:
        assert False, AC8
    assert (
        json.loads(output.getvalue()) == {"a": 1} and capsys.readouterr().out == ""
    ), AC8


def test_ac9_catalog_compiler_is_absent_from_runtime_artifacts(tmp_path: Path) -> None:
    compiler = ROOT / "src" / "easy_cheese_schemas" / "_schema_catalog_compiler.py"
    assert compiler.is_file(), AC9
    bundles = tmp_path / "bundles"
    build = subprocess.run(
        [sys.executable, "scripts/build_pyz.py", "--out-dir", str(bundles)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert build.returncode == 0, AC9
    leaked = [
        archive.name
        for archive in bundles.glob("*.pyz")
        if any(
            name.endswith("/_schema_catalog_compiler.py")
            or name == "_schema_catalog_compiler.py"
            for name in zipfile.ZipFile(archive).namelist()
        )
    ]
    wheel_dir = tmp_path / "wheel"
    wheel = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(wheel_dir)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert wheel.returncode == 0, AC9
    wheel_path = next(wheel_dir.glob("*.whl"))
    wheel_names = zipfile.ZipFile(wheel_path).namelist()
    assert not leaked and not any(
        name.endswith("/_schema_catalog_compiler.py") for name in wheel_names
    ), AC9


def test_ac10_compute_waves_is_shared_and_preserves_behavior() -> None:
    try:
        graph = importlib.import_module("easy_cheese_schemas.wiring_graph")
    except ModuleNotFoundError:
        assert False, AC10
    assert graph.compute_waves(
        [("W1", []), ("W2", ["W1"]), ("W3", ["W1"]), ("W4", ["W2", "W3"])]
    ) == [["W1"], ["W2", "W3"], ["W4"]], AC10
