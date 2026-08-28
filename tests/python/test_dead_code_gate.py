"""Regression tests for the Vulture dead-code gate."""

from __future__ import annotations

import ast

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts" / "check_dead_code.py"
needs_just = pytest.mark.skipif(
    shutil.which("just") is None, reason="just is not installed"
)
def _checker_module():
    spec = importlib.util.spec_from_file_location("check_dead_code", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    previous = {name: sys.modules.get(name) for name in ("vulture", "vulture.config", "vulture.core", spec.name)}
    vulture = ModuleType("vulture")
    vulture.Vulture = type("Vulture", (), {})
    config = ModuleType("vulture.config")
    config.InputError = type("InputError", (Exception,), {})
    config.make_config = lambda _args: {}
    core = ModuleType("vulture.core")
    core.ExitCode = type("ExitCode", (), {})
    sys.modules.update({"vulture": vulture, "vulture.config": config, "vulture.core": core, spec.name: module})
    try:
        spec.loader.exec_module(module)
    finally:
        for name, old in previous.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
    return module


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
    probe.write_text(
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


def test_schema_enum_and_attrs_fields_accept_absolute_vulture_filenames() -> None:
    """Schema-owned generated fields are dynamic API, not dead code."""
    checker = _checker_module()
    source = "from enum import Enum\nimport attrs\n\nclass E(Enum):\n    MEMBER = 'member'\n\n@attrs.define\nclass C:\n    field: int = 1\n"
    tree = ast.parse(source)
    imports = checker._import_map(tree)
    enum_item = SimpleNamespace(
        filename=str(ROOT / "src" / "easy_cheese_schemas" / "sample.py"),
        first_lineno=5,
        name="MEMBER",
        typ="variable",
        get_report=lambda: "",
    )
    attrs_item = SimpleNamespace(
        filename=str(ROOT / "src" / "easy_cheese_schemas" / "sample.py"),
        first_lineno=9,
        name="field",
        typ="variable",
        get_report=lambda: "",
    )
    findings = checker._findings([enum_item, attrs_item])
    assert all(not finding.path.is_absolute() for finding in findings)
    assert checker._accepted_reason(findings[0], tree, imports)
    assert checker._accepted_reason(findings[1], tree, imports)



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
        imports = checker._import_map(tree)
        node = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name) if typ == "function" else next(node for node in ast.walk(tree) if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name)
        line = node.decorator_list[0].lineno if typ == "function" else node.lineno
        finding = checker._Finding(Path("src/easy_cheese_schemas/sample.py"), line, name, typ, "")
        assert bool(checker._accepted_reason(finding, tree, imports)) is expected



def test_callback_identity_is_exact() -> None:
    checker = _checker_module()
    for source, expected in [
        ("from urllib.request import HTTPRedirectHandler\nclass H(HTTPRedirectHandler):\n    def redirect_request(self, req, fp, code, msg, headers, newurl):\n        return None\n", True),
        ("import evilurllib\nclass H(evilurllib.request.HTTPRedirectHandler):\n    def redirect_request(self, req, fp, code, msg, headers, newurl):\n        return None\n", False),
    ]:
        tree = ast.parse(source)
        imports = checker._import_map(tree)
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
        finding = checker._Finding(Path("src/other.py"), method.lineno, method.name, "method", "")
        assert bool(checker._accepted_reason(finding, tree, imports)) is expected

def test_lint_job_runs_recipe() -> None:
    """The CI lint job invokes the same dead-code recipe as local checks."""
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    )
    assert any(
        step.get("run") == "just lint-py-dead-code"
        for step in workflow["jobs"]["lint"]["steps"]
    )


def test_import_shadowing_is_position_aware() -> None:
    checker = _checker_module()
    before = ast.parse("from enum import Enum\nclass Enum: pass\nclass E(Enum):\n    MEMBER = 1\n")
    after = ast.parse("from enum import Enum\nclass E(Enum):\n    MEMBER = 1\nclass Enum: pass\n")
    for tree, expected in [(before, False), (after, True)]:
        imports = checker._import_map(tree)
        member = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign))
        finding = checker._Finding(Path("src/easy_cheese_schemas/sample.py"), member.lineno, "MEMBER", "variable", "")
        assert bool(checker._accepted_reason(finding, tree, imports)) is expected


def test_destructuring_shadowing_is_position_aware() -> None:
    checker = _checker_module()
    before = ast.parse("from enum import Enum\n(Marker, Enum) = (1, object())\nclass E(Enum):\n    MEMBER = 1\n")
    after = ast.parse("from enum import Enum\nclass E(Enum):\n    MEMBER = 1\n(Marker, Enum) = (1, object())\n")
    for tree, expected in [(before, False), (after, True)]:
        imports = checker._import_map(tree)
        member = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "MEMBER" for target in n.targets)
        )
        finding = checker._Finding(Path("src/easy_cheese_schemas/sample.py"), member.lineno, "MEMBER", "variable", "")
        assert bool(checker._accepted_reason(finding, tree, imports)) is expected


def test_walrus_shadowing_is_position_aware() -> None:
    checker = _checker_module()
    before = ast.parse("from enum import Enum\nif (Enum := object()):\n    pass\nclass E(Enum):\n    MEMBER = 1\n")
    after = ast.parse("from enum import Enum\nclass E(Enum):\n    MEMBER = 1\nif (Enum := object()):\n    pass\n")
    for tree, expected in [(before, False), (after, True)]:
        imports = checker._import_map(tree)
        member = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "MEMBER" for target in n.targets)
        )
        finding = checker._Finding(Path("src/easy_cheese_schemas/sample.py"), member.lineno, "MEMBER", "variable", "")
        assert bool(checker._accepted_reason(finding, tree, imports)) is expected


def test_lambda_local_walrus_does_not_shadow_import() -> None:
    checker = _checker_module()
    tree = ast.parse("from enum import Enum\nmaker = lambda: (Enum := object())\nclass E(Enum):\n    MEMBER = 1\n")
    imports = checker._import_map(tree)
    member = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "MEMBER" for target in n.targets)
    )
    finding = checker._Finding(Path("src/easy_cheese_schemas/sample.py"), member.lineno, "MEMBER", "variable", "")
    assert checker._accepted_reason(finding, tree, imports)


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
        source.write_text(text, encoding="utf-8")
        tree = ast.parse(text)
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        finding = checker._Finding(source, node.lineno, node.name, "function", "")
        assert checker._has_definition_noqa(finding, tree, source) is expected