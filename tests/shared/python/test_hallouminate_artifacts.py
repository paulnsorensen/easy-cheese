"""Tests for shared/hallouminate_artifacts.py -- cheese-artifacts corpus setup."""

from __future__ import annotations

from pathlib import Path

import pytest

from easy_cheese.shared import hallouminate_artifacts as artifacts_mod


@pytest.fixture(autouse=True)
def isolated_search_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Never scan the real `~` -- machine-scope discovery defaults there.

    Points the default search root at an unused sibling dir, not `tmp_path`
    itself, so each test's explicit `roots=[...]` argument is what actually
    controls what gets discovered.
    """
    monkeypatch.setenv("EASY_CHEESE_SEARCH_ROOTS", str(tmp_path / "unused-default-root"))


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    return tmp_path / "config" / "hallouminate" / "config.toml"


def _write_cheese_md(repo: Path, name: str = "a.md") -> Path:
    note = repo / ".cheese" / "notes" / name
    note.parent.mkdir(parents=True, exist_ok=True)
    _ = note.write_text("content\n", encoding="utf-8")
    return repo / ".cheese"


class TestApplyArtifactsCreate:
    def test_creates_block_with_discovered_dirs(
        self, tmp_path: Path, config_path: Path
    ) -> None:
        repo_a = tmp_path / "repo-a"
        repo_b = tmp_path / "repo-b"
        cheese_a = _write_cheese_md(repo_a)
        cheese_b = _write_cheese_md(repo_b)

        change = artifacts_mod.apply_artifacts(
            config_path, apply=True, roots=[repo_a, repo_b]
        )

        assert change.action == "create"
        text = config_path.read_text(encoding="utf-8")
        assert text.count('name = "cheese-artifacts"') == 1
        assert f'"{cheese_a.resolve()}"' in text
        assert f'"{cheese_b.resolve()}"' in text
        assert 'globs = ["**/*.md"]' in text
        assert 'exclude = ["**/.git/**"]' in text

    def test_dry_run_writes_nothing(self, tmp_path: Path, config_path: Path) -> None:
        repo = tmp_path / "repo"
        _ = _write_cheese_md(repo)

        change = artifacts_mod.apply_artifacts(config_path, apply=False, roots=[repo])

        assert change.action == "create"
        assert not config_path.exists()


class TestApplyArtifactsIdempotency:
    def test_second_apply_is_byte_identical(
        self, tmp_path: Path, config_path: Path
    ) -> None:
        repo = tmp_path / "repo"
        _ = _write_cheese_md(repo)

        _ = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])
        first = config_path.read_bytes()
        _ = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])
        second = config_path.read_bytes()

        assert second == first

    def test_second_apply_reports_noop(self, tmp_path: Path, config_path: Path) -> None:
        repo = tmp_path / "repo"
        _ = _write_cheese_md(repo)

        _ = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])
        change = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])

        assert change.action == "noop"


class TestApplyArtifactsReplace:
    def test_replace_updates_added_and_removed_dirs(
        self, tmp_path: Path, config_path: Path
    ) -> None:
        repo_a = tmp_path / "repo-a"
        repo_b = tmp_path / "repo-b"
        _ = _write_cheese_md(repo_a)
        _ = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo_a])

        cheese_b = _write_cheese_md(repo_b)
        change = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo_b])

        assert change.action == "replace"
        assert "added 1" in change.detail
        assert "removed 1" in change.detail
        text = config_path.read_text(encoding="utf-8")
        assert text.count('name = "cheese-artifacts"') == 1
        assert str(repo_a.resolve()) not in text
        assert f'"{cheese_b.resolve()}"' in text

    def test_preserves_unrelated_corpora(self, tmp_path: Path, config_path: Path) -> None:
        config_path.parent.mkdir(parents=True)
        _ = config_path.write_text(
            '[[corpus]]\nname = "other-corpus"\npaths = ["/opt/other"]\n',
            encoding="utf-8",
        )
        repo = tmp_path / "repo"
        _ = _write_cheese_md(repo)

        _ = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])

        text = config_path.read_text(encoding="utf-8")
        assert 'name = "other-corpus"' in text
        assert 'name = "cheese-artifacts"' in text


class TestApplyArtifactsRemove:
    def test_removes_block_when_nothing_discovered(
        self, tmp_path: Path, config_path: Path
    ) -> None:
        repo = tmp_path / "repo"
        _ = _write_cheese_md(repo)
        _ = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])

        empty_root = tmp_path / "empty"
        empty_root.mkdir()
        change = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[empty_root])

        assert change.action == "remove"
        text = config_path.read_text(encoding="utf-8")
        assert "cheese-artifacts" not in text

    def test_noop_when_nothing_discovered_and_no_block(
        self, tmp_path: Path, config_path: Path
    ) -> None:
        empty_root = tmp_path / "empty"
        empty_root.mkdir()

        change = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[empty_root])

        assert change.action == "noop"
        assert not config_path.exists()


class TestPathEscaping:
    def test_round_trips_paths_with_quotes_and_backslashes(
        self, tmp_path: Path, config_path: Path
    ) -> None:
        repo = tmp_path / 'weird"repo'
        cheese = _write_cheese_md(repo)

        _ = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])

        state = artifacts_mod.detect_artifacts_state(config_path)
        assert state.listed == (str(cheese.resolve()),)


class TestDetectArtifactsState:
    def test_reports_missing_paths_as_drift(
        self, tmp_path: Path, config_path: Path
    ) -> None:
        repo = tmp_path / "repo"
        _ = _write_cheese_md(repo)
        _ = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])

        import shutil

        shutil.rmtree(repo)

        state = artifacts_mod.detect_artifacts_state(config_path)

        assert state.missing == state.listed

    def test_no_drift_when_all_paths_exist(self, tmp_path: Path, config_path: Path) -> None:
        repo = tmp_path / "repo"
        _ = _write_cheese_md(repo)
        _ = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])

        state = artifacts_mod.detect_artifacts_state(config_path)

        assert state.missing == ()

    def test_empty_state_when_no_config(self, config_path: Path) -> None:
        state = artifacts_mod.detect_artifacts_state(config_path)

        assert state == artifacts_mod.ArtifactsState(listed=(), missing=())


class TestRunLeg:
    def test_dry_run_reports_create_without_writing(
        self, tmp_path: Path, config_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HALLOUMINATE_CONFIG", str(config_path))
        repo = tmp_path / "repo"
        _ = _write_cheese_md(repo)

        lines = artifacts_mod.run_leg(apply=False, roots=[str(repo)])

        assert any("[artifacts] create:" in line for line in lines)
        assert not config_path.exists()
        assert not any("daemon restart" in line for line in lines)

    def test_apply_reports_restart_follow_up_only_when_file_changed(
        self, tmp_path: Path, config_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HALLOUMINATE_CONFIG", str(config_path))
        repo = tmp_path / "repo"
        _ = _write_cheese_md(repo)

        first_lines = artifacts_mod.run_leg(apply=True, roots=[str(repo)])
        assert any("daemon restart" in line for line in first_lines)

        second_lines = artifacts_mod.run_leg(apply=True, roots=[str(repo)])
        assert not any("daemon restart" in line for line in second_lines)

    def test_reports_drift_for_missing_listed_paths(
        self, tmp_path: Path, config_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HALLOUMINATE_CONFIG", str(config_path))
        repo = tmp_path / "repo"
        _ = _write_cheese_md(repo)
        _ = artifacts_mod.run_leg(apply=True, roots=[str(repo)])

        import shutil

        shutil.rmtree(repo)

        empty_root = tmp_path / "empty"
        empty_root.mkdir()
        lines = artifacts_mod.run_leg(apply=False, roots=[str(empty_root)])

        assert any("drift" in line for line in lines)
