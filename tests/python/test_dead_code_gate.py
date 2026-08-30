"""Regression tests for the Vulture dead-code gate."""

from __future__ import annotations

import ast

import importlib.util
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts" / "check_dead_code.py"
needs_just = pytest.mark.skipif(
    shutil.which("just") is None, reason="just is not installed"
)


@dataclass(frozen=True, slots=True)
class _FindingLike:
    path: Path
    first_line: int
    name: str
    typ: str
    report: str


@dataclass(frozen=True, slots=True)
class _UnusedItemStub:
    filename: str
    first_lineno: int
    name: str
    typ: str

    def get_report(self) -> str:
        return ""


class _Checker(Protocol):
    _Finding: type[_FindingLike]

    def _import_map(self, module: ast.Module) -> dict[str, str]: ...
    def _findings(self, items: Sequence[_UnusedItemStub]) -> tuple[_FindingLike, ...]: ...
    def _accepted_reason(
        self, finding: _FindingLike, module: ast.Module, imports: dict[str, str]
    ) -> str | None: ...
    def _has_definition_noqa(
        self, finding: _FindingLike, module: ast.Module, source_path: Path
    ) -> bool: ...


def _stub_make_config(_args: object) -> dict[str, object]:
    return {}


def _checker_module() -> _Checker:
    spec = importlib.util.spec_from_file_location("check_dead_code", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    previous: dict[str, ModuleType | None] = {
        name: sys.modules.get(name) for name in ("vulture", "vulture.config", "vulture.core", spec.name)
    }
    vulture = ModuleType("vulture")
    setattr(vulture, "Vulture", type("Vulture", (), {}))
    config = ModuleType("vulture.config")
    setattr(config, "InputError", type("InputError", (Exception,), {}))
    setattr(config, "make_config", _stub_make_config)
    core = ModuleType("vulture.core")
    setattr(core, "ExitCode", type("ExitCode", (), {}))
    sys.modules.update({"vulture": vulture, "vulture.config": config, "vulture.core": core, spec.name: module})
    try:
        spec.loader.exec_module(module)
    finally:
        for name, old in previous.items():
            if old is None:
                _ = sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
    return cast(_Checker, cast(object, module))


def _import_map(checker: _Checker, module: ast.Module) -> dict[str, str]:
    return checker._import_map(module)  # pyright: ignore[reportPrivateUsage]


def _findings(checker: _Checker, items: Sequence[_UnusedItemStub]) -> tuple[_FindingLike, ...]:
    return checker._findings(items)  # pyright: ignore[reportPrivateUsage]


def _make_finding(
    checker: _Checker, path: Path, first_line: int, name: str, typ: str, report: str
) -> _FindingLike:
    return checker._Finding(path, first_line, name, typ, report)  # pyright: ignore[reportPrivateUsage]


def _accepted_reason(
    checker: _Checker, finding: _FindingLike, module: ast.Module, imports: dict[str, str]
) -> str | None:
    return checker._accepted_reason(finding, module, imports)  # pyright: ignore[reportPrivateUsage]


def _has_definition_noqa(
    checker: _Checker, finding: _FindingLike, module: ast.Module, source_path: Path
) -> bool:
    return checker._has_definition_noqa(finding, module, source_path)  # pyright: ignore[reportPrivateUsage]


@needs_just
def test_clean_tree_exits_zero() -> None:
    """The repository has no unclassified dead-code findings."""
    result = subprocess.run(
        ["just", "lint-py-dead-code"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@needs_just
def test_probe_fails_at_sixty_percent(tmp_path: Path) -> None:
    """A genuine unused local remains a gate failure."""
    probe = tmp_path / "probe.py"
    _ = probe.write_text(
        "def probe():\n    unused_var = 1\n    return 2\n\nprobe()\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["just", "lint-py-dead-code", str(tmp_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 3
    assert f"{probe}:2: unused variable 'unused_var' (60% confidence)" in output


@needs_just
def test_orphaned_function_fails_the_gate(tmp_path: Path) -> None:
    """A newly-orphaned top-level function is reported, not silently accepted."""
    probe = tmp_path / "probe.py"
    _ = probe.write_text(
        "def orphaned_function():\n    return 1\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["just", "lint-py-dead-code", str(tmp_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 3
    assert f"{probe}:1: unused function 'orphaned_function' (60% confidence)" in output


@needs_just
def test_decorator_registered_function_does_not_fail_the_gate(tmp_path: Path) -> None:
    """A function registered through a data-driven `ignore_decorators` entry is
    invoked only via a compiled dispatcher, so the gate must not report it dead.
    """
    probe = tmp_path / "probe.py"
    lines = (
        "def bundle_command(func):",
        "    return func",
        "",
        "",
        "@bundle_command",
        "def registered_entry_point():",
        "    return 1",
        "",
    )
    _ = probe.write_text("\n".join(lines), encoding="utf-8")
    result = subprocess.run(
        ["just", "lint-py-dead-code", str(tmp_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output


def test_pyproject_declares_decorator_registered_entry_points() -> None:
    """Decorator-registered entry points are allowlisted through pyproject's
    data-driven `[tool.vulture]` config, not inline `# noqa` comments at each
    call site.
    """
    config = _as_dict(cast(object, tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))))
    tool = _as_dict(config["tool"])
    vulture = _as_dict(tool["vulture"])
    ignore_decorators = _as_list(vulture["ignore_decorators"])
    assert "@bundle_command" in ignore_decorators
    assert "@contract" in ignore_decorators
    assert "@document_contract" in ignore_decorators


def test_schema_enum_and_attrs_fields_accept_absolute_vulture_filenames() -> None:
    """Schema-owned generated fields are dynamic API, not dead code."""
    checker = _checker_module()
    source = "from enum import Enum\nimport attrs\n\nclass E(Enum):\n    MEMBER = 'member'\n\n@attrs.define\nclass C:\n    field: int = 1\n"
    tree = ast.parse(source)
    imports = _import_map(checker, tree)
    enum_item = _UnusedItemStub(
        filename=str(ROOT / "src" / "easy_cheese_schemas" / "sample.py"),
        first_lineno=5,
        name="MEMBER",
        typ="variable",
    )
    attrs_item = _UnusedItemStub(
        filename=str(ROOT / "src" / "easy_cheese_schemas" / "sample.py"),
        first_lineno=9,
        name="field",
        typ="variable",
    )
    findings = _findings(checker, [enum_item, attrs_item])
    assert all(not finding.path.is_absolute() for finding in findings)
    assert _accepted_reason(checker, findings[0], tree, imports)
    assert _accepted_reason(checker, findings[1], tree, imports)


def test_typed_dict_field_is_not_dead_code() -> None:
    """TypedDict fields are accessed via string subscript, never as bare names."""
    checker = _checker_module()
    source = "from typing import NotRequired, TypedDict\n\nclass _D(TypedDict):\n    field: NotRequired[str]\n"
    tree = ast.parse(source)
    imports = _import_map(checker, tree)
    finding = _make_finding(checker, Path("src/other/sample.py"), 4, "field", "variable", "")
    assert _accepted_reason(checker, finding, tree, imports) == "TypedDict field declaration"


def test_typed_dict_lookalike_is_still_dead_code() -> None:
    """A locally defined TypedDict that is not the typing one must not launder fields."""
    checker = _checker_module()
    source = "class TypedDict: pass\nclass _D(TypedDict):\n    field: str\n"
    tree = ast.parse(source)
    imports = _import_map(checker, tree)
    finding = _make_finding(checker, Path("src/other/sample.py"), 3, "field", "variable", "")
    assert _accepted_reason(checker, finding, tree, imports) is None


def test_protocol_member_and_parameter_are_not_dead_code() -> None:
    """Protocol attributes and method parameters are structural interface, not dead code."""
    checker = _checker_module()
    source = (
        "from typing import Protocol\n"
        "\n"
        "class _P(Protocol):\n"
        "    attr: str\n"
        "\n"
        "    def method(self, amt: int) -> None: ...\n"
    )
    tree = ast.parse(source)
    imports = _import_map(checker, tree)
    attr_finding = _make_finding(checker, Path("src/other/sample.py"), 4, "attr", "variable", "")
    param_finding = _make_finding(checker, Path("src/other/sample.py"), 6, "amt", "variable", "")
    assert _accepted_reason(checker, attr_finding, tree, imports)
    assert _accepted_reason(checker, param_finding, tree, imports)


def test_protocol_lookalike_is_still_dead_code() -> None:
    """A locally defined Protocol that is not the typing one must not launder members or params."""
    checker = _checker_module()
    source = (
        "class Protocol: pass\n"
        "class _P(Protocol):\n"
        "    attr: str\n"
        "\n"
        "    def method(self, amt: int) -> None: ...\n"
    )
    tree = ast.parse(source)
    imports = _import_map(checker, tree)
    attr_finding = _make_finding(checker, Path("src/other/sample.py"), 3, "attr", "variable", "")
    param_finding = _make_finding(checker, Path("src/other/sample.py"), 5, "amt", "variable", "")
    assert _accepted_reason(checker, attr_finding, tree, imports) is None
    assert _accepted_reason(checker, param_finding, tree, imports) is None


def test_override_decorated_method_is_not_dead_code() -> None:
    """@override methods implement a framework contract vulture cannot see dispatch for."""
    checker = _checker_module()
    source = (
        "from typing import override\n"
        "from html.parser import HTMLParser\n"
        "\n"
        "class _P(HTMLParser):\n"
        "    @override\n"
        "    def handle_data(self, data: str) -> None: ...\n"
    )
    tree = ast.parse(source)
    imports = _import_map(checker, tree)
    finding = _make_finding(checker, Path("src/other/sample.py"), 5, "handle_data", "method", "")
    assert _accepted_reason(checker, finding, tree, imports) == "@override framework hook"


def test_override_lookalike_is_still_dead_code() -> None:
    """A locally defined @override that is not typing.override must not launder the method."""
    checker = _checker_module()
    source = (
        "def override(f):\n"
        "    return f\n"
        "\n"
        "class _P:\n"
        "    @override\n"
        "    def unused(self) -> None: ...\n"
    )
    tree = ast.parse(source)
    imports = _import_map(checker, tree)
    finding = _make_finding(checker, Path("src/other/sample.py"), 6, "unused", "method", "")
    assert _accepted_reason(checker, finding, tree, imports) is None


def test_undecorated_method_is_still_dead_code() -> None:
    """A plain unused method without @override stays classified as dead."""
    checker = _checker_module()
    source = "class _C:\n    def unused(self) -> None: ...\n"
    tree = ast.parse(source)
    imports = _import_map(checker, tree)
    finding = _make_finding(checker, Path("src/other/sample.py"), 2, "unused", "method", "")
    assert _accepted_reason(checker, finding, tree, imports) is None


def test_ordinary_class_variable_is_still_dead_code() -> None:
    """A genuinely unused class-body variable outside TypedDict/Protocol stays classified as dead."""
    checker = _checker_module()
    source = "class _C:\n    unused = 1\n"
    tree = ast.parse(source)
    imports = _import_map(checker, tree)
    finding = _make_finding(checker, Path("src/other/sample.py"), 2, "unused", "variable", "")
    assert _accepted_reason(checker, finding, tree, imports) is None



def test_classifier_requires_exact_import_identities() -> None:
    checker = _checker_module()
    cases = [
        ("from enum import Enum\nclass E(Enum):\n    MEMBER = 1\n", "MEMBER", "variable", True),
        ("class Enum: pass\nclass E(Enum):\n    MEMBER = 1\n", "MEMBER", "variable", False),
        ("import attrs\n@attrs.define\nclass C:\n    field = 1\n", "field", "variable", True),
        ("class attrs: pass\n@attrs.define\nclass C:\n    field = 1\n", "field", "variable", False),
        ("import pytest\n@pytest.fixture(autouse=True)\ndef fix():\n    return None\n", "fix", "function", True),
        ("class pytest: pass\n@pytest.fixture(autouse=True)\ndef fix():\n    return None\n", "fix", "function", False),
    ]
    for source, name, typ, expected in cases:
        tree = ast.parse(source)
        imports = _import_map(checker, tree)
        if typ == "function":
            func_node = next(
                node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == name
            )
            line = func_node.decorator_list[0].lineno
        else:
            assign_node = next(
                node for node in ast.walk(tree)
                if isinstance(node, ast.Assign)
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == name
            )
            line = assign_node.lineno
        finding = _make_finding(checker, Path("src/easy_cheese_schemas/sample.py"), line, name, typ, "")
        assert bool(_accepted_reason(checker, finding, tree, imports)) is expected



def test_callback_identity_is_exact() -> None:
    checker = _checker_module()
    for source, expected in [
        ("from urllib.request import HTTPRedirectHandler\nclass H(HTTPRedirectHandler):\n    def redirect_request(self, req, fp, code, msg, headers, newurl):\n        return None\n", True),
        ("import evilurllib\nclass H(evilurllib.request.HTTPRedirectHandler):\n    def redirect_request(self, req, fp, code, msg, headers, newurl):\n        return None\n", False),
    ]:
        tree = ast.parse(source)
        imports = _import_map(checker, tree)
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
        finding = _make_finding(checker, Path("src/other.py"), method.lineno, method.name, "method", "")
        assert bool(_accepted_reason(checker, finding, tree, imports)) is expected

def _as_dict(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _as_list(value: object) -> list[object]:
    assert isinstance(value, list)
    return cast(list[object], value)


def test_lint_job_runs_recipe() -> None:
    """The CI lint job invokes the same dead-code recipe as local checks."""
    workflow = _as_dict(cast(object, yaml.safe_load(
        (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    )))
    jobs = _as_dict(workflow["jobs"])
    lint_job = _as_dict(jobs["lint"])
    steps = _as_list(lint_job["steps"])
    assert any(_as_dict(step).get("run") == "just lint-py-dead-code" for step in steps)


def test_import_shadowing_is_position_aware() -> None:
    checker = _checker_module()
    before = ast.parse("from enum import Enum\nclass Enum: pass\nclass E(Enum):\n    MEMBER = 1\n")
    after = ast.parse("from enum import Enum\nclass E(Enum):\n    MEMBER = 1\nclass Enum: pass\n")
    for tree, expected in [(before, False), (after, True)]:
        imports = _import_map(checker, tree)
        member = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign))
        finding = _make_finding(checker, Path("src/easy_cheese_schemas/sample.py"), member.lineno, "MEMBER", "variable", "")
        assert bool(_accepted_reason(checker, finding, tree, imports)) is expected


def test_destructuring_shadowing_is_position_aware() -> None:
    checker = _checker_module()
    before = ast.parse("from enum import Enum\n(Marker, Enum) = (1, object())\nclass E(Enum):\n    MEMBER = 1\n")
    after = ast.parse("from enum import Enum\nclass E(Enum):\n    MEMBER = 1\n(Marker, Enum) = (1, object())\n")
    for tree, expected in [(before, False), (after, True)]:
        imports = _import_map(checker, tree)
        member = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "MEMBER" for target in n.targets)
        )
        finding = _make_finding(checker, Path("src/easy_cheese_schemas/sample.py"), member.lineno, "MEMBER", "variable", "")
        assert bool(_accepted_reason(checker, finding, tree, imports)) is expected


def test_walrus_shadowing_is_position_aware() -> None:
    checker = _checker_module()
    before = ast.parse("from enum import Enum\nif (Enum := object()):\n    pass\nclass E(Enum):\n    MEMBER = 1\n")
    after = ast.parse("from enum import Enum\nclass E(Enum):\n    MEMBER = 1\nif (Enum := object()):\n    pass\n")
    for tree, expected in [(before, False), (after, True)]:
        imports = _import_map(checker, tree)
        member = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "MEMBER" for target in n.targets)
        )
        finding = _make_finding(checker, Path("src/easy_cheese_schemas/sample.py"), member.lineno, "MEMBER", "variable", "")
        assert bool(_accepted_reason(checker, finding, tree, imports)) is expected


def test_lambda_local_walrus_does_not_shadow_import() -> None:
    checker = _checker_module()
    tree = ast.parse("from enum import Enum\nmaker = lambda: (Enum := object())\nclass E(Enum):\n    MEMBER = 1\n")
    imports = _import_map(checker, tree)
    member = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "MEMBER" for target in n.targets)
    )
    finding = _make_finding(checker, Path("src/easy_cheese_schemas/sample.py"), member.lineno, "MEMBER", "variable", "")
    assert _accepted_reason(checker, finding, tree, imports) == "enum member or attrs field owned by easy_cheese_schemas"


def test_definition_noqa_requires_exact_header_comment(tmp_path: Path) -> None:
    checker = _checker_module()
    cases = [
        ("def generated():  # noqa: V103\n    pass\n", True),
        ("def generated():  # noqa: V103 extra\n    pass\n", False),
        ("value = '# noqa: V103'\ndef generated():\n    pass\n", False),
        ("# noqa: V103\ndef generated():\n    pass\n", False),
        ("def generated():\n    # noqa: V103\n    pass\n", False),
    ]
    for text, expected in cases:
        source = tmp_path / "generated.py"
        _ = source.write_text(text, encoding="utf-8")
        tree = ast.parse(text)
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        finding = _make_finding(checker, source, node.lineno, node.name, "function", "")
        assert _has_definition_noqa(checker, finding, tree, source) is expected