"""Tests for shared/scripts/slugify.py — task→slug+path CLI."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED = REPO_ROOT / "shared" / "scripts"
SLUGIFY_CLI = SHARED / "slugify.py"


@pytest.fixture(scope="module")
def slugify_mod() -> ModuleType:
    # Preload cli + paths so slugify's top-level `import cli` / `import paths` resolve.
    if str(SHARED) not in sys.path:
        sys.path.insert(0, str(SHARED))
    for name in ("cli", "paths", "slugify"):
        spec = importlib.util.spec_from_file_location(name, SHARED / f"{name}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules["slugify"]


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SLUGIFY_CLI), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd is not None else None,
    )


class TestHelp:
    def test_help_exits_zero(self) -> None:
        result = _run("--help")
        assert result.returncode == 0
        assert "from-task" in result.stdout

    def test_subcommand_help_exits_zero(self) -> None:
        result = _run("from-task", "--help")
        assert result.returncode == 0
        assert "--task" in result.stdout


class TestHappyPathJson:
    def test_simple_phrase(self, tmp_path: Path) -> None:
        result = _run(
            "from-task", "--task", "Tail trailing newline",
            "--root", str(tmp_path),
            "--json",
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["slug"] == "tail-trailing-newline"
        assert payload["path"].endswith("/specs/tail-trailing-newline.md")

    def test_default_root_path_shape(self, tmp_path: Path) -> None:
        # Use a clean cwd so .cheese/specs/<slug>.md cannot exist.
        result = _run(
            "from-task", "--task", "Tail trailing newline", "--json",
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload == {
            "slug": "tail-trailing-newline",
            "path": ".cheese/specs/tail-trailing-newline.md",
        }


class TestKebabCasing:
    def test_lowercases_and_drops_punctuation(self, tmp_path: Path) -> None:
        result = _run(
            "from-task", "--task", "Don't Stop, Believin'!",
            "--root", str(tmp_path),
            "--json",
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        # Apostrophes drop ("Don't"->"dont"), commas/exclamation drop.
        assert payload["slug"] == "dont-stop-believin"

    def test_drops_stopwords(self, tmp_path: Path) -> None:
        result = _run(
            "from-task", "--task", "The quick brown fox jumps",
            "--root", str(tmp_path),
            "--json",
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        # "The" is a stopword and is dropped.
        assert payload["slug"] == "quick-brown-fox-jumps"

    def test_collapses_internal_whitespace(self, tmp_path: Path) -> None:
        result = _run(
            "from-task", "--task", "  multiple   spaces   here  ",
            "--root", str(tmp_path),
            "--json",
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["slug"] == "multiple-spaces-here"


class TestFiveWordCap:
    def test_caps_at_five_words(self, tmp_path: Path) -> None:
        result = _run(
            "from-task",
            "--task", "one two three four five six seven",
            "--root", str(tmp_path),
            "--json",
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["slug"] == "one-two-three-four-five"
        # Sanity: exactly 5 hyphen-separated tokens.
        assert payload["slug"].count("-") == 4

    def test_stopword_does_not_consume_cap_slot(self, tmp_path: Path) -> None:
        # 'the' (stopword) is dropped before the 5-word cap is applied.
        result = _run(
            "from-task",
            "--task", "the alpha beta gamma delta epsilon",
            "--root", str(tmp_path),
            "--json",
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["slug"] == "alpha-beta-gamma-delta-epsilon"


class TestCollision:
    def test_collision_exits_two_with_error_prefix(self, tmp_path: Path) -> None:
        # Pre-create .cheese/specs/<slug>.md under tmp_path.
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir(parents=True)
        (specs_dir / "tail-trailing-newline.md").write_text("preexisting\n")

        result = _run(
            "from-task", "--task", "Tail trailing newline",
            "--root", str(tmp_path),
            "--json",
        )
        assert result.returncode == 2
        assert result.stderr.startswith("ERROR:"), result.stderr
        assert "already exists" in result.stderr
        # Hint guides recovery without referencing a flag the CLI does not define.
        assert "--suffix" not in result.stderr
        assert "rephrase --task" in result.stderr or "remove the existing" in result.stderr
        # No stdout on error.
        assert result.stdout == ""

    def test_no_collision_when_file_missing(self, tmp_path: Path) -> None:
        # Sibling specs/ dir empty: should succeed.
        (tmp_path / "specs").mkdir()
        result = _run(
            "from-task", "--task", "Tail trailing newline",
            "--root", str(tmp_path),
            "--json",
        )
        assert result.returncode == 0, result.stderr


class TestEmptySlugRejected:
    def test_stopword_only_task_errors(self, tmp_path: Path) -> None:
        # All stopwords → empty slug → CliError.
        result = _run(
            "from-task", "--task", "the a an of",
            "--root", str(tmp_path),
            "--json",
        )
        assert result.returncode == 2
        assert result.stderr.startswith("ERROR:")


class TestModuleApi:
    def test_module_loads(self, slugify_mod: ModuleType) -> None:
        # Smoke test: module exposes _from_task + _setup, and importing did not blow up.
        assert hasattr(slugify_mod, "_from_task")
        assert hasattr(slugify_mod, "_setup")
