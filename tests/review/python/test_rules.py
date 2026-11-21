"""The packaged rule pack: ast-grep tests pass and every rule is well formed (AC-2)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import cast

import pytest
import yaml

from easy_cheese_review.severity import Severity
from easy_cheese_schemas import ReviewDimension

REPO_ROOT = Path(__file__).resolve().parents[3]
RULES = REPO_ROOT / "packages" / "easy-cheese-review" / "src" / "easy_cheese_review" / "rules"
RULE_FILES = sorted((*RULES.glob("python/*.yml"), *RULES.glob("typescript/*.yml")))


def _load(path: Path) -> dict[str, object]:
    return cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))


def _stem(path: Path) -> str:
    return path.stem


def test_pack_has_python_and_typescript_rules() -> None:
    languages = {_load(path)["language"] for path in RULE_FILES}
    assert languages == {"python", "typescript"}


@pytest.mark.parametrize("path", RULE_FILES, ids=_stem)
def test_rule_carries_dimension_and_base(path: Path) -> None:
    rule = _load(path)
    assert rule["id"] == path.stem
    metadata = cast(dict[str, str], rule["metadata"])
    assert set(metadata) == {"dimension", "base"}
    assert ReviewDimension(metadata["dimension"]).value == metadata["dimension"]
    assert Severity.parse(metadata["base"], field="base").name.lower() == metadata["base"]


@pytest.mark.parametrize("path", RULE_FILES, ids=_stem)
def test_rule_has_valid_and_invalid_cases(path: Path) -> None:
    cases = _load(RULES / "tests" / f"{path.stem}-test.yml")
    assert cases["id"] == path.stem
    assert cast(list[str], cases["valid"])
    assert cast(list[str], cases["invalid"])
    assert (RULES / "tests" / "__snapshots__" / f"{path.stem}-snapshot.yml").is_file()


def test_ast_grep_test_passes_every_case(ast_grep_binary: str) -> None:
    result = subprocess.run(
        [ast_grep_binary, "test", "-c", str(RULES / "sgconfig.yml")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"{len(RULE_FILES)} passed; 0 failed" in result.stdout


def test_ast_grep_test_rejects_a_broken_rule(ast_grep_binary: str, tmp_path: Path) -> None:
    """Negative control: the same harness fails when a rule misses its invalid case."""
    broken = tmp_path / "rules"
    _ = subprocess.run(["cp", "-r", str(RULES), str(broken)], check=True)
    rule = broken / "python" / "py-eval-exec.yml"
    _ = rule.write_text(rule.read_text(encoding="utf-8").replace("eval($$$ARGS)", "evaluate($$$ARGS)"))
    result = subprocess.run(
        [ast_grep_binary, "test", "-c", str(broken / "sgconfig.yml")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "FAIL py-eval-exec" in result.stdout
