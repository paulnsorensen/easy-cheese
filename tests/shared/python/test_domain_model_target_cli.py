"""Behavioral tests for the explicit domain-model target command contract."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Protocol, cast

import pytest


class _CommandSurface(Protocol):
    def main(self, argv: list[str]) -> int: ...


REPO_ROOT = Path(__file__).resolve().parents[3]
PATHS_CLI = REPO_ROOT / "src" / "easy_cheese" / "shared" / "paths.py"


def _run_paths(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PATHS_CLI), "domain-model-target", *args],
        capture_output=True,
        text=True,
    )


def _payload(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    return cast(dict[str, object], json.loads(result.stdout))


@pytest.fixture
def resolver_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "corpus-home"
    monkeypatch.setenv("EASY_CHEESE_HOME", str(home))
    monkeypatch.setenv("EASY_CHEESE_PROJECT", "owner-repo")
    return tmp_path / "repo", home / "owner-repo"


class TestPathsCommand:
    def test_unavailable_probe_uses_file_fallback_and_false_reachability(
        self, resolver_env: tuple[Path, Path]
    ) -> None:
        repo, corpus_root = resolver_env
        result = _run_paths(
            "--probe",
            "unavailable",
            "--repo-root",
            str(repo),
        )

        assert _payload(result) == {
            "backend": "file",
            "location": str(corpus_root / "domain-model.md"),
            "wiki_reachable": False,
        }

    def test_successful_probe_without_matching_corpus_is_reachable(
        self, resolver_env: tuple[Path, Path]
    ) -> None:
        repo, corpus_root = resolver_env
        result = _run_paths(
            "--probe",
            "no-match",
            "--repo-root",
            str(repo),
        )

        assert _payload(result) == {
            "backend": "file",
            "location": str(corpus_root / "domain-model.md"),
            "wiki_reachable": True,
        }

    def test_matching_present_model_uses_hallouminate(
        self, resolver_env: tuple[Path, Path]
    ) -> None:
        repo, _ = resolver_env
        result = _run_paths(
            "--probe",
            "match",
            "--corpus",
            "repo:consumer:wiki",
            "--model",
            "present",
            "--repo-root",
            str(repo),
        )

        assert _payload(result) == {
            "backend": "hallouminate",
            "location": "repo:consumer:wiki",
            "wiki_reachable": True,
        }

    def test_matching_present_model_overrides_existing_file(
        self, resolver_env: tuple[Path, Path]
    ) -> None:
        repo, _ = resolver_env
        file_model = repo / "docs" / "domain-model.md"
        file_model.parent.mkdir(parents=True)
        _ = file_model.write_text("**Term** — definition.\n", encoding="utf-8")

        result = _run_paths(
            "--probe",
            "match",
            "--corpus",
            "repo:consumer:wiki",
            "--model",
            "present",
            "--repo-root",
            str(repo),
        )

        assert _payload(result) == {
            "backend": "hallouminate",
            "location": "repo:consumer:wiki",
            "wiki_reachable": True,
        }

    @pytest.mark.parametrize("model", ["absent", "unknown"])
    def test_matching_nonpresent_model_uses_wiki_for_first_write(
        self, resolver_env: tuple[Path, Path], model: str
    ) -> None:
        repo, _ = resolver_env
        result = _run_paths(
            "--probe",
            "match",
            "--corpus",
            "repo:consumer:wiki",
            "--model",
            model,
            "--repo-root",
            str(repo),
        )

        assert _payload(result) == {
            "backend": "hallouminate",
            "location": "repo:consumer:wiki",
            "wiki_reachable": True,
        }

    @pytest.mark.parametrize("model", ["absent", "unknown"])
    def test_matching_nonpresent_model_preserves_file_precedence(
        self,
        resolver_env: tuple[Path, Path],
        model: str,
    ) -> None:
        repo, _ = resolver_env
        file_model = repo / "docs" / "domain-model.md"
        file_model.parent.mkdir(parents=True)
        _ = file_model.write_text("**Term** — definition.\n", encoding="utf-8")

        result = _run_paths(
            "--probe",
            "match",
            "--corpus",
            "repo:consumer:wiki",
            "--model",
            model,
            "--repo-root",
            str(repo),
        )

        assert _payload(result) == {
            "backend": "file",
            "location": str(file_model),
            "wiki_reachable": True,
        }

    @pytest.mark.parametrize(
        ("model", "expected"),
        [("present", True), ("absent", False), ("unknown", None)],
    )
    def test_model_state_reaches_resolver_without_collapsing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        model: str,
        expected: bool | None,
    ) -> None:
        from easy_cheese.shared import paths

        captured: dict[str, object] = {}

        def capture_target(**kwargs: object) -> paths.DomainModelTarget:
            captured.update(kwargs)
            return paths.DomainModelTarget("hallouminate", "repo:consumer:wiki", True)

        monkeypatch.setattr(paths, "domain_model_target", capture_target)
        assert (
            paths.main(
                [
                    "domain-model-target",
                    "--probe",
                    "match",
                    "--corpus",
                    "repo:consumer:wiki",
                    "--model",
                    model,
                ]
            )
            == 0
        )
        _ = capsys.readouterr()

        predicate = captured["wiki_has_model"]
        if expected is None:
            assert predicate is None
        else:
            assert callable(predicate)
            assert predicate("repo:consumer:wiki") is expected

    @pytest.mark.parametrize(
        ("args", "message"),
        [
            (("--probe", "unavailable", "--corpus", "repo:x:wiki"), "require"),
            (("--probe", "no-match", "--model", "present"), "require"),
            (("--probe", "match", "--corpus", "repo:x:wiki"), "--model"),
            (("--probe", "match", "--model", "present"), "--corpus"),
        ],
    )
    def test_invalid_probe_combinations_fail_before_resolution(
        self,
        resolver_env: tuple[Path, Path],
        args: tuple[str, ...],
        message: str,
    ) -> None:
        repo, _ = resolver_env
        result = _run_paths(*args, "--repo-root", str(repo))

        assert result.returncode == 2
        assert result.stdout == ""
        error_payload = cast("dict[str, object]", json.loads(result.stderr))
        assert message in str(error_payload["error"])

    def test_invalid_corpus_shape_is_rejected(
        self, resolver_env: tuple[Path, Path]
    ) -> None:
        repo, _ = resolver_env
        result = _run_paths(
            "--probe",
            "match",
            "--corpus",
            "not-a-wiki-corpus",
            "--model",
            "unknown",
            "--repo-root",
            str(repo),
        )

        assert result.returncode == 2
        assert result.stdout == ""
        assert json.loads(result.stderr)["error"] == "--corpus must match repo:<name>:wiki"


@pytest.mark.parametrize(
    "module_name",
    ["easy_cheese.skills.mold.commands", "easy_cheese.skills.cure.commands"],
)
def test_both_bundle_surfaces_dispatch_domain_target(
    module_name: str,
    resolver_env: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, _ = resolver_env
    module = cast(_CommandSurface, cast(object, importlib.import_module(module_name)))
    code = module.main(
        [
            "domain-model-target",
            "--probe",
            "match",
            "--corpus",
            "repo:consumer:wiki",
            "--model",
            "present",
            "--repo-root",
            str(repo),
        ]
    )

    assert code == 0
    assert json.loads(capsys.readouterr().out) == {
        "backend": "hallouminate",
        "location": "repo:consumer:wiki",
        "wiki_reachable": True,
    }
