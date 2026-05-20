"""Tests for shared/scripts/paths_cli.py — slugify / validate / existing CLI."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SCRIPTS = REPO_ROOT / "shared" / "scripts"
PATHS_CLI = SHARED_SCRIPTS / "paths_cli.py"


@pytest.fixture(scope="module")
def paths_cli_mod() -> ModuleType:
    # Sibling imports (cli, paths) resolve via sys.path; conftest already inserts it.
    if str(SHARED_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SHARED_SCRIPTS))
    spec = importlib.util.spec_from_file_location("paths_cli", PATHS_CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["paths_cli"] = module
    spec.loader.exec_module(module)
    return module


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PATHS_CLI), *args],
        capture_output=True,
        text=True,
    )


class TestSlugify:
    def test_basic(self) -> None:
        result = _run("slugify", "--text", "Tail trailing newline")
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "tail-trailing-newline"

    def test_punctuation_stripped(self) -> None:
        result = _run("slugify", "--text", "Don't break!!! User-facing API.")
        assert result.returncode == 0
        assert result.stdout.strip() == "dont-break-user-facing-api"

    def test_empty_text_errors(self) -> None:
        result = _run("slugify", "--text", "")
        assert result.returncode == 2
        assert "ERROR:" in result.stderr

    def test_only_stopwords_errors(self) -> None:
        # All-stopword input produces an empty slug → CliError.
        result = _run("slugify", "--text", "the of and")
        assert result.returncode == 2
        assert "ERROR:" in result.stderr

    def test_missing_text_arg_exits_two(self) -> None:
        result = _run("slugify")
        assert result.returncode == 2


class TestValidate:
    @pytest.mark.parametrize(
        "slug", ["a", "fix-auth-retry", "abc-123-def", "x1"]
    )
    def test_accepts_good(self, slug: str) -> None:
        result = _run("validate", "--slug", slug)
        assert result.returncode == 0, result.stderr
        assert result.stdout == ""

    @pytest.mark.parametrize(
        "slug",
        ["bad--slug", "trailing-", "UPPER", "snake_case"],
    )
    def test_rejects_bad(self, slug: str) -> None:
        result = _run("validate", "--slug", slug)
        assert result.returncode == 2
        assert "ERROR:" in result.stderr

    def test_rejects_leading_hyphen(self) -> None:
        # argparse needs `--slug=-leading` to keep the leading dash as a value.
        result = _run("validate", "--slug=-leading")
        assert result.returncode == 2
        assert "ERROR:" in result.stderr

    def test_missing_slug_arg_exits_two(self) -> None:
        result = _run("validate")
        assert result.returncode == 2

    def test_acceptance_bad_double_hyphen(self) -> None:
        # Spec acceptance: validate --slug bad--slug exits 2 with ERROR.
        result = _run("validate", "--slug", "bad--slug")
        assert result.returncode == 2
        assert result.stderr.startswith("ERROR:")


class TestExisting:
    def test_json_returns_list(self, tmp_path: Path) -> None:
        (tmp_path / "age").mkdir()
        target = tmp_path / "age" / "demo.md"
        target.write_text("body", encoding="utf-8")

        result = _run(
            "existing",
            "--slug",
            "demo",
            "--phase",
            "age",
            "--root",
            str(tmp_path),
            "--json",
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload == [str(target)]

    def test_empty_when_missing(self, tmp_path: Path) -> None:
        result = _run(
            "existing",
            "--slug",
            "demo",
            "--phase",
            "age",
            "--root",
            str(tmp_path),
            "--json",
        )
        assert result.returncode == 0
        assert json.loads(result.stdout) == []

    def test_filters_to_requested_phase(self, tmp_path: Path) -> None:
        # Artifact exists under cook but caller asked for age — must come back empty.
        (tmp_path / "cook").mkdir()
        (tmp_path / "cook" / "demo.md").write_text("body", encoding="utf-8")

        result = _run(
            "existing",
            "--slug",
            "demo",
            "--phase",
            "age",
            "--root",
            str(tmp_path),
            "--json",
        )
        assert result.returncode == 0
        assert json.loads(result.stdout) == []

    def test_invalid_slug_errors(self, tmp_path: Path) -> None:
        result = _run(
            "existing",
            "--slug",
            "Bad_Slug",
            "--phase",
            "age",
            "--root",
            str(tmp_path),
        )
        assert result.returncode == 2
        assert "ERROR:" in result.stderr

    def test_unknown_phase_errors(self, tmp_path: Path) -> None:
        result = _run(
            "existing",
            "--slug",
            "demo",
            "--phase",
            "bogus",
            "--root",
            str(tmp_path),
        )
        assert result.returncode == 2
        assert "ERROR:" in result.stderr
        assert "unknown phase" in result.stderr

    def test_missing_required_args_exits_two(self) -> None:
        result = _run("existing")
        assert result.returncode == 2


class TestModuleImport:
    def test_setup_callable_present(self, paths_cli_mod: ModuleType) -> None:
        # Sanity: the module exports the argparse setup hook cli.run consumes.
        assert callable(paths_cli_mod._setup)

    def test_delegates_to_paths_module(self, paths_cli_mod: ModuleType) -> None:
        # paths_cli must use the shared paths module, not redefine the regex/phases.
        assert paths_cli_mod.paths.KEBAB_SLUG is not None
        assert "age" in paths_cli_mod.paths.PHASES
