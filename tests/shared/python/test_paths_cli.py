"""Tests for shared/scripts/paths_cli.py — slugify / validate / existing CLI."""

from __future__ import annotations

import os

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


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PATHS_CLI), *args],
        capture_output=True,
        text=True,
        env=env,
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

    def test_finds_durable_spec_without_explicit_root(self, tmp_path: Path) -> None:
        # Regression for #249: default routing must reach the XDG durable corpus
        # for durable phases (specs), not just ".cheese/" like transient phases.
        home = tmp_path / "corpus-home"
        spec = home / "owner-repo" / "specs" / "demo.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("body", encoding="utf-8")
        env = dict(os.environ)
        env["EASY_CHEESE_HOME"] = str(home)
        env["EASY_CHEESE_PROJECT"] = "owner-repo"

        result = _run("existing", "--slug", "demo", "--phase", "specs", "--json", env=env)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == [str(spec)]

    def test_explicit_root_still_overrides_durable_routing(self, tmp_path: Path) -> None:
        # An explicit --root pins the lookup there even for a durable phase,
        # preserving the override contract callers rely on.
        home = tmp_path / "corpus-home"
        corpus_spec = home / "owner-repo" / "specs" / "demo.md"
        corpus_spec.parent.mkdir(parents=True)
        corpus_spec.write_text("body", encoding="utf-8")
        override_root = tmp_path / "custom-root"
        override_spec = override_root / "specs" / "demo.md"
        override_spec.parent.mkdir(parents=True)
        override_spec.write_text("body", encoding="utf-8")
        env = dict(os.environ)
        env["EASY_CHEESE_HOME"] = str(home)
        env["EASY_CHEESE_PROJECT"] = "owner-repo"

        result = _run(
            "existing",
            "--slug",
            "demo",
            "--phase",
            "specs",
            "--root",
            str(override_root),
            "--json",
            env=env,
        )
        assert result.returncode == 0, result.stderr
        # Only the explicit-root path is returned, never the XDG corpus one.
        assert json.loads(result.stdout) == [str(override_spec)]


class TestList:
    def test_durable_phase_returns_xdg_corpus_slugs(self, tmp_path: Path) -> None:
        # Durable phases (specs) list from the XDG corpus, not .cheese/.
        home = tmp_path / "corpus-home"
        spec = home / "owner-repo" / "specs" / "demo.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("body", encoding="utf-8")
        env = dict(os.environ)
        env["EASY_CHEESE_HOME"] = str(home)
        env["EASY_CHEESE_PROJECT"] = "owner-repo"

        result = _run("list", "--phase", "specs", "--json", env=env)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == [{"slug": "demo", "path": str(spec)}]

    def test_transient_phase_anchors_under_dot_cheese(self, tmp_path: Path) -> None:
        art = tmp_path / ".cheese" / "cook" / "demo.md"
        art.parent.mkdir(parents=True)
        art.write_text("body", encoding="utf-8")

        result = _run("list", "--phase", "cook", "--repo-root", str(tmp_path), "--json")
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == [{"slug": "demo", "path": str(art)}]

    def test_json_mode_honors_limit(self, tmp_path: Path) -> None:
        # --limit must cap JSON output too, not only plain mode; --full
        # overrides it. Programmatic callers rely on --json + --limit.
        for name in ("alpha", "bravo", "charlie"):
            art = tmp_path / ".cheese" / "cook" / f"{name}.md"
            art.parent.mkdir(parents=True, exist_ok=True)
            art.write_text("body", encoding="utf-8")

        capped = _run(
            "list", "--phase", "cook", "--repo-root", str(tmp_path),
            "--json", "--limit", "2",
        )
        assert capped.returncode == 0, capped.stderr
        assert len(json.loads(capped.stdout)) == 2

        full = _run(
            "list", "--phase", "cook", "--repo-root", str(tmp_path),
            "--json", "--limit", "2", "--full",
        )
        assert full.returncode == 0, full.stderr
        assert len(json.loads(full.stdout)) == 3

    def test_plain_mode_emits_slugs_only(self, tmp_path: Path) -> None:
        art = tmp_path / ".cheese" / "cook" / "demo.md"
        art.parent.mkdir(parents=True)
        art.write_text("body", encoding="utf-8")

        result = _run("list", "--phase", "cook", "--repo-root", str(tmp_path))
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "demo"

    def test_empty_when_missing(self, tmp_path: Path) -> None:
        result = _run("list", "--phase", "cook", "--repo-root", str(tmp_path), "--json")
        assert result.returncode == 0
        assert json.loads(result.stdout) == []

    def test_unknown_phase_errors(self, tmp_path: Path) -> None:
        result = _run("list", "--phase", "bogus", "--repo-root", str(tmp_path))
        assert result.returncode == 2
        assert "ERROR:" in result.stderr
        assert "unknown phase" in result.stderr

    def test_missing_required_args_exits_two(self) -> None:
        result = _run("list")
        assert result.returncode == 2


class TestResolve:
    def test_hit_emits_contract_keys(self, tmp_path: Path) -> None:
        art = tmp_path / ".cheese" / "cook" / "demo.md"
        art.parent.mkdir(parents=True)
        art.write_text("body", encoding="utf-8")
        result = _run("resolve", "--slug", "demo", "--repo-root", str(tmp_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["fallback_roots"] == []
        assert payload["matches"] == [
            {
                "abs_path": str(art),
                "phase": "cook",
                "skill": "/cook",
                "confidence": 1.0,
            }
        ]

    def test_fallback_emits_searched_roots(self, tmp_path: Path) -> None:
        result = _run("resolve", "--slug", "nowhere", "--repo-root", str(tmp_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["matches"] == []
        assert str(tmp_path / ".cheese" / "cook") in payload["fallback_roots"]

    def test_invalid_slug_exits_two(self, tmp_path: Path) -> None:
        result = _run("resolve", "--slug", "Bad_Slug", "--repo-root", str(tmp_path))
        assert result.returncode == 2
        assert "ERROR:" in result.stderr

    def test_unknown_phase_exits_two(self, tmp_path: Path) -> None:
        result = _run(
            "resolve", "--slug", "demo", "--phase", "bogus", "--repo-root", str(tmp_path)
        )
        assert result.returncode == 2
        assert "ERROR: unknown phase 'bogus'" in result.stderr


class TestModuleImport:
    def test_setup_callable_present(self, paths_cli_mod: ModuleType) -> None:
        # Sanity: the module exports the argparse setup hook cli.run consumes.
        assert callable(paths_cli_mod._setup)

    def test_delegates_to_paths_module(self, paths_cli_mod: ModuleType) -> None:
        # paths_cli must use the shared paths module, not redefine the regex/phases.
        assert paths_cli_mod.paths.KEBAB_SLUG is not None
        assert "age" in paths_cli_mod.paths.PHASES
