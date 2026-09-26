"""Tests for shared/hallouminate_artifacts.py -- cheese-artifacts corpus setup."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import shutil

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
        assert "removed 0" in change.detail
        text = config_path.read_text(encoding="utf-8")
        assert text.count('name = "cheese-artifacts"') == 1
        assert f'"{repo_a.resolve() / ".cheese"}"' in text
        assert f'"{cheese_b.resolve()}"' in text

    def test_retains_existing_dirs_omitted_by_later_scan(
        self, tmp_path: Path, config_path: Path
    ) -> None:
        repo_a = tmp_path / "repo-a"
        repo_b = tmp_path / "repo-b"
        cheese_a = _write_cheese_md(repo_a)
        cheese_b = _write_cheese_md(repo_b)
        _ = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo_a])

        change = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo_b])

        assert change.action == "replace"
        assert "added 1" in change.detail
        assert "removed 0" in change.detail
        text = config_path.read_text(encoding="utf-8")
        assert f'"{cheese_a.resolve()}"' in text
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

        import shutil

        shutil.rmtree(repo)
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

    def test_removes_block_after_listed_dir_disappears(
        self, tmp_path: Path, config_path: Path
    ) -> None:
        repo = tmp_path / "repo"
        _ = _write_cheese_md(repo)
        _ = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])

        import shutil

        shutil.rmtree(repo)
        empty_root = tmp_path / "empty"
        empty_root.mkdir()
        change = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[empty_root])

        assert change.action == "remove"
        assert "cheese-artifacts" not in config_path.read_text(encoding="utf-8")


class TestPathEscaping:
    def test_round_trips_paths_with_quotes_and_backslashes(
        self, tmp_path: Path, config_path: Path
    ) -> None:
        repo = tmp_path / 'weird"repo'
        cheese = _write_cheese_md(repo)

        _ = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])

        state = artifacts_mod.detect_artifacts_state(config_path)
        assert state.listed == (str(cheese.resolve()),)

    def test_escapes_control_characters_as_toml_basic_string(
        self,
        tmp_path: Path,
        config_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import tomllib

        monkeypatch.setenv("PATH", "")

        repo = tmp_path / "control\nrepo\t\x01"
        cheese = _write_cheese_md(repo)

        _ = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])

        parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert parsed["corpus"][0]["paths"] == [str(cheese.resolve())]


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


    def test_incomplete_scan_reports_error_without_mutating(
        self,
        tmp_path: Path,
        config_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo = tmp_path / "repo"
        _ = _write_cheese_md(repo)
        _ = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])
        before = config_path.read_bytes()
        from easy_cheese.shared.wheypoint.discovery_notes import CheeseDirScan

        def incomplete_scan(_roots: Sequence[Path | str]) -> CheeseDirScan:
            return CheeseDirScan(
                dirs=(), backend="walk", errors=("directory walk timed out",)
            )

        monkeypatch.setattr(artifacts_mod, "find_cheese_dirs", incomplete_scan)

        change = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[tmp_path])

        assert change.action == "error"
        assert "incomplete scan" in change.detail
        assert config_path.read_bytes() == before

    def test_successful_fallback_keeps_mutation_and_reports_warning(
        self,
        tmp_path: Path,
        config_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from easy_cheese.shared.wheypoint.discovery_notes import CheeseDirScan

        repo = tmp_path / "repo"
        cheese = _write_cheese_md(repo)
        warning = "rg failed or timed out; fell back to a directory walk"
        def fallback_scan(_roots: Sequence[Path | str]) -> CheeseDirScan:
            return CheeseDirScan(
                dirs=(cheese.resolve(),), backend="walk", errors=(warning,)
            )

        monkeypatch.setattr(artifacts_mod, "find_cheese_dirs", fallback_scan)

        change = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])

        assert change.action == "create"
        assert warning in change.detail
        assert f'"{cheese.resolve()}"' in config_path.read_text(encoding="utf-8")

    def test_refuses_unmarked_same_name_corpus(
        self, tmp_path: Path, config_path: Path
    ) -> None:
        config_path.parent.mkdir(parents=True)
        original = (
            '[[corpus]]\n'
            "name   =   'cheese-artifacts'\n"
            'paths = ["/opt/old-cheese"]\n'
        )
        _ = config_path.write_text(original, encoding="utf-8")
        repo = tmp_path / "repo"
        _ = _write_cheese_md(repo)

        change = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])

        assert change.action == "error"
        assert "unmarked cheese-artifacts" in change.detail
        assert config_path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize(
    "table_header,name_key",
    [
        ("[[ corpus ]]", 'name = "cheese-artifacts"'),
        ("[[corpus]] # trailing comment", 'name = "cheese-artifacts"'),
        ("[[corpus]]", '"name" = "cheese-artifacts"'),
    ],
)
def test_refuses_valid_toml_duplicate_corpus_forms(
    tmp_path: Path,
    config_path: Path,
    table_header: str,
    name_key: str,
) -> None:
    import tomllib

    config_path.parent.mkdir(parents=True)
    original = (
        f"{table_header}\n"
        f"{name_key}\n"
        'paths = ["/opt/old-cheese"]\n'
    )
    assert tomllib.loads(original)["corpus"][0]["name"] == "cheese-artifacts"
    _ = config_path.write_text(original, encoding="utf-8")
    repo = tmp_path / "repo"
    _ = _write_cheese_md(repo)

    change = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])

    assert change.action == "error"
    assert "unmarked cheese-artifacts" in change.detail
    assert config_path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("use_rg", [False, True])
def test_control_path_apply_state_and_idempotency(
    tmp_path: Path,
    config_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    use_rg: bool,
) -> None:
    if use_rg and shutil.which("rg") is None:
        pytest.skip("rg is not installed")
    if not use_rg:
        monkeypatch.setenv("PATH", "")

    repo = tmp_path / "control\nrepo\t\r\x01"
    cheese = _write_cheese_md(repo)

    first = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])
    assert first.action == "create"
    state = artifacts_mod.detect_artifacts_state(config_path)
    assert state.listed == (str(cheese.resolve()),)

    before_second = config_path.read_bytes()
    second = artifacts_mod.apply_artifacts(config_path, apply=True, roots=[repo])
    assert second.action == "noop"
    assert config_path.read_bytes() == before_second
