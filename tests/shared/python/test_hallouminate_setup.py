"""Tests for shared/scripts/hallouminate_setup.py -- cheese-durable corpus setup."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def corpus_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Pin corpus_home() to a deterministic tmp location, unset on disk."""
    home = tmp_path / "corpus-home"
    monkeypatch.setenv("EASY_CHEESE_HOME", str(home))
    return home


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    return tmp_path / "config" / "hallouminate" / "config.toml"


class TestApplyGlobalIdempotency:
    def test_second_apply_is_byte_identical(
        self, hallouminate_setup: ModuleType, corpus_home: Path, config_path: Path
    ) -> None:
        hallouminate_setup.apply_global(config_path, apply=True)
        first = config_path.read_bytes()
        hallouminate_setup.apply_global(config_path, apply=True)
        second = config_path.read_bytes()
        assert second == first

    def test_second_apply_reports_noop(
        self, hallouminate_setup: ModuleType, corpus_home: Path, config_path: Path
    ) -> None:
        hallouminate_setup.apply_global(config_path, apply=True)
        change = hallouminate_setup.apply_global(config_path, apply=True)
        assert change.action == "noop"


class TestDetectDrift:
    def test_reports_drifted_when_paths0_mismatches_corpus_home(
        self, hallouminate_setup: ModuleType, corpus_home: Path, config_path: Path
    ) -> None:
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            '# >>> easy-cheese:cheese-durable\n'
            '[[corpus]]\n'
            'name = "cheese-durable"\n'
            'paths = ["/somewhere/else"]\n'
            'globs = ["**/*.md"]\n'
            'exclude = ["**/.git/**"]\n'
            '# <<< easy-cheese:cheese-durable\n',
            encoding="utf-8",
        )
        state = hallouminate_setup.detect_state(config_path)
        assert state == {
            "present": True,
            "path": str(config_path),
            "drifted": True,
            "drift_from": "/somewhere/else",
        }

    def test_apply_global_repoints_drifted_block(
        self, hallouminate_setup: ModuleType, corpus_home: Path, config_path: Path
    ) -> None:
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            '# >>> easy-cheese:cheese-durable\n'
            '[[corpus]]\n'
            'name = "cheese-durable"\n'
            'paths = ["/somewhere/else"]\n'
            'globs = ["**/*.md"]\n'
            'exclude = ["**/.git/**"]\n'
            '# <<< easy-cheese:cheese-durable\n',
            encoding="utf-8",
        )
        change = hallouminate_setup.apply_global(config_path, apply=True)
        assert change.action == "replace"
        text = config_path.read_text(encoding="utf-8")
        assert f'paths = ["{corpus_home}"]' in text
        assert text.count('name = "cheese-durable"') == 1


class TestApplyGlobalCreatesCorpusHome:
    def test_mkdir_p_guards_hallouminate_abort_on_missing(
        self, hallouminate_setup: ModuleType, corpus_home: Path, config_path: Path
    ) -> None:
        assert not corpus_home.exists()
        hallouminate_setup.apply_global(config_path, apply=True)
        assert corpus_home.is_dir()


class TestApplyGlobalDuplicateNameSafety:
    def test_replace_never_leaves_two_marked_blocks(
        self, hallouminate_setup: ModuleType, corpus_home: Path, config_path: Path
    ) -> None:
        hallouminate_setup.apply_global(config_path, apply=True)
        hallouminate_setup.apply_global(config_path, apply=True)
        hallouminate_setup.apply_global(config_path, apply=True)
        text = config_path.read_text(encoding="utf-8")
        assert text.count('name = "cheese-durable"') == 1


class TestApplyGlobalRobustness:
    def test_orphan_begin_marker_is_replaced_not_duplicated(
        self, hallouminate_setup: ModuleType, corpus_home: Path, config_path: Path
    ) -> None:
        # A truncated block: BEGIN + a stale paths line, but no closing END
        # (e.g. an interrupted prior write). Must be rewritten in place, not
        # appended-alongside into a duplicate cheese-durable corpus.
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            "[[corpus]]\n"
            'name = "cheez-wiki"\n'
            'paths = ["/opt/wiki"]\n\n'
            f"{hallouminate_setup.BEGIN}\n"
            "[[corpus]]\n"
            'name = "cheese-durable"\n'
            'paths = ["/stale/root"]\n',
            encoding="utf-8",
        )
        change = hallouminate_setup.apply_global(config_path, apply=True)
        assert change.action == "replace"
        text = config_path.read_text(encoding="utf-8")
        assert text.count('name = "cheese-durable"') == 1
        assert text.count(hallouminate_setup.END) == 1
        assert str(corpus_home) in text
        assert "/stale/root" not in text
        # Unrelated corpora are preserved.
        assert 'name = "cheez-wiki"' in text

    def test_write_is_atomic_and_leaves_no_temp_file(
        self, hallouminate_setup: ModuleType, corpus_home: Path, config_path: Path
    ) -> None:
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            "[[corpus]]\nname = \"milknado-wiki\"\npaths = [\"/opt/mn\"]\n",
            encoding="utf-8",
        )
        hallouminate_setup.apply_global(config_path, apply=True)
        # Unrelated corpus survives, and no .ec-tmp sibling is left behind.
        assert 'name = "milknado-wiki"' in config_path.read_text(encoding="utf-8")
        leftovers = list(config_path.parent.glob("*.ec-tmp"))
        assert leftovers == []


class TestApplyGlobalDryRun:
    def test_apply_false_writes_nothing(
        self, hallouminate_setup: ModuleType, corpus_home: Path, config_path: Path
    ) -> None:
        change = hallouminate_setup.apply_global(config_path, apply=False)
        assert change.action == "create"
        assert not config_path.exists()
        assert not corpus_home.exists()


class TestMigrateLegacy:
    def test_removes_unmarked_cheese_global_pointing_at_dot_cheese(
        self, hallouminate_setup: ModuleType, config_path: Path
    ) -> None:
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            '[[corpus]]\n'
            'name = "cheese-global"\n'
            'paths = ["~/.cheese"]\n'
            'globs = ["**/*.md"]\n',
            encoding="utf-8",
        )
        change = hallouminate_setup.migrate_legacy(config_path, apply=True)
        assert change.action == "remove"
        text = config_path.read_text(encoding="utf-8")
        assert "cheese-global" not in text
        assert "~/.cheese" not in text

    def test_leaves_cheese_global_pointing_elsewhere_intact(
        self, hallouminate_setup: ModuleType, config_path: Path
    ) -> None:
        original = (
            '[[corpus]]\n'
            'name = "cheese-global"\n'
            'paths = ["/opt/other-cheese"]\n'
            'globs = ["**/*.md"]\n'
        )
        config_path.parent.mkdir(parents=True)
        config_path.write_text(original, encoding="utf-8")
        change = hallouminate_setup.migrate_legacy(config_path, apply=True)
        assert change.action == "noop"
        assert config_path.read_text(encoding="utf-8") == original

    def test_preserves_trailing_config_after_last_legacy_corpus(
        self, hallouminate_setup: ModuleType, config_path: Path
    ) -> None:
        # The legacy cheese-global block is the LAST [[corpus]], followed by an
        # unrelated [[repository]] section. Removing the corpus must not run to
        # EOF and delete the trailing tenant block.
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            '[[corpus]]\n'
            'name = "cheese-global"\n'
            'paths = ["~/.cheese"]\n'
            'globs = ["**/*.md"]\n'
            '\n'
            '[[repository]]\n'
            'name = "my-repo"\n'
            'path = "/opt/my-repo"\n',
            encoding="utf-8",
        )
        change = hallouminate_setup.migrate_legacy(config_path, apply=True)
        assert change.action == "remove"
        text = config_path.read_text(encoding="utf-8")
        assert "cheese-global" not in text
        assert '[[repository]]' in text
        assert 'name = "my-repo"' in text
        assert 'path = "/opt/my-repo"' in text


class TestApplyLocalMainRoot:
    def test_init_repo_targets_main_root_not_worktree(
        self,
        hallouminate_setup: ModuleType,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        main_root = tmp_path / "main-repo"
        main_root.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=main_root, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "--allow-empty", "-q", "-m", "init"],
            cwd=main_root,
            check=True,
        )
        worktree_root = tmp_path / "worktree-repo"
        subprocess.run(
            ["git", "worktree", "add", "-q", str(worktree_root), "-b", "wt"],
            cwd=main_root,
            check=True,
        )
        (worktree_root / ".cheese").mkdir()

        calls: list[tuple[str, Path]] = []
        monkeypatch.setattr(
            hallouminate_setup, "_run_init_repo", lambda name, path: calls.append((name, path))
        )

        change = hallouminate_setup.apply_local(worktree_root, apply=True)

        assert change.action == "init-repo"
        assert calls == [(main_root.name, main_root)]

    def test_noop_when_already_a_tenant(
        self, hallouminate_setup: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo_root = tmp_path / "repo"
        (repo_root / ".cheese").mkdir(parents=True)
        (repo_root / ".hallouminate").mkdir()
        (repo_root / ".hallouminate" / "config.toml").write_text("", encoding="utf-8")
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_root, check=True)

        calls: list[tuple[str, Path]] = []
        monkeypatch.setattr(
            hallouminate_setup, "_run_init_repo", lambda name, path: calls.append((name, path))
        )

        change = hallouminate_setup.apply_local(repo_root, apply=True)

        assert change.action == "noop"
        assert calls == []

    def test_noop_when_no_dot_cheese_dir(
        self, hallouminate_setup: ModuleType, tmp_path: Path
    ) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_root, check=True)

        change = hallouminate_setup.apply_local(repo_root, apply=True)

        assert change.action == "noop"

    def test_noop_when_cheese_dir_but_not_a_git_repo(
        self, hallouminate_setup: ModuleType, tmp_path: Path
    ) -> None:
        # .cheese/ present but the dir is not inside a git repo -- git rev-parse
        # would raise; the leg must degrade to a clean noop, not a traceback.
        repo_root = tmp_path / "loose"
        (repo_root / ".cheese").mkdir(parents=True)

        change = hallouminate_setup.apply_local(repo_root, apply=True)

        assert change.action == "noop"


class TestApplyGlobalNewlinePreservation:
    def test_crlf_config_stays_crlf_after_write(
        self, hallouminate_setup: ModuleType, corpus_home: Path, config_path: Path
    ) -> None:
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            '[[corpus]]\r\nname = "milknado-wiki"\r\npaths = ["/opt/mn"]\r\n',
            encoding="utf-8",
            newline="",
        )
        hallouminate_setup.apply_global(config_path, apply=True)
        raw = config_path.read_bytes()
        # No lone LF: every LF is part of a CRLF pair.
        assert raw.count(b"\n") == raw.count(b"\r\n")
        assert b'name = "cheese-durable"' in raw


class TestMigrateLegacyNewlinePreservation:
    def test_crlf_config_stays_crlf_after_migrate(
        self, hallouminate_setup: ModuleType, config_path: Path
    ) -> None:
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            '[[corpus]]\r\n'
            'name = "cheese-global"\r\n'
            'paths = ["~/.cheese"]\r\n'
            'globs = ["**/*.md"]\r\n'
            '[[repository]]\r\n'
            'name = "other-repo"\r\n'
            'path = "/opt/other"\r\n',
            encoding="utf-8",
            newline="",
        )
        change = hallouminate_setup.migrate_legacy(config_path, apply=True)
        assert change.action == "remove"
        raw = config_path.read_bytes()
        # No lone LF: every LF is part of a CRLF pair.
        assert raw.count(b"\n") == raw.count(b"\r\n")
        assert b'name = "cheese-global"' not in raw
        assert b'name = "other-repo"' in raw


class TestMigrateLegacyDryRun:
    def test_dry_run_reports_remove_without_writing(
        self, hallouminate_setup: ModuleType, config_path: Path
    ) -> None:
        original = (
            '[[corpus]]\n'
            'name = "cheese-global"\n'
            'paths = ["~/.cheese"]\n'
            'globs = ["**/*.md"]\n'
        )
        config_path.parent.mkdir(parents=True)
        config_path.write_text(original, encoding="utf-8")
        change = hallouminate_setup.migrate_legacy(config_path, apply=False)
        assert change.action == "remove"
        # Dry-run must not touch the shared user config.
        assert config_path.read_text(encoding="utf-8") == original


class TestConfigPathResolution:
    def test_hallouminate_config_override_wins(
        self, hallouminate_setup: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HALLOUMINATE_CONFIG", "/opt/custom/config.toml")
        monkeypatch.setenv("XDG_CONFIG_HOME", "/should/be/ignored")
        assert hallouminate_setup.config_path() == Path("/opt/custom/config.toml")

    def test_xdg_config_home_when_no_override(
        self, hallouminate_setup: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("HALLOUMINATE_CONFIG", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert hallouminate_setup.config_path() == tmp_path / "hallouminate" / "config.toml"


class TestCliDispatch:
    """The `main()` argv-normalizing CLI -- the entry point install.sh invokes
    as `... global --apply`. Guards the production dispatch path."""

    def test_global_apply_writes_marked_block(
        self,
        hallouminate_setup: ModuleType,
        corpus_home: Path,
        config_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("HALLOUMINATE_CONFIG", str(config_path))
        rc = hallouminate_setup.main(["hallouminate_setup.py", "global", "--apply"])
        assert rc == 0
        text = config_path.read_text(encoding="utf-8")
        assert text.count('name = "cheese-durable"') == 1
        assert f'paths = ["{corpus_home}"]' in text

    def test_prog0_leg_dispatch_dry_run_writes_nothing(
        self,
        hallouminate_setup: ModuleType,
        corpus_home: Path,
        config_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # argv[0] is the leg name (symlinked/renamed invocation), no --apply.
        monkeypatch.setenv("HALLOUMINATE_CONFIG", str(config_path))
        rc = hallouminate_setup.main(["global"])
        assert rc == 0
        assert not config_path.exists()

    def test_unknown_leg_returns_usage_error(
        self,
        hallouminate_setup: ModuleType,
        config_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("HALLOUMINATE_CONFIG", str(config_path))
        rc = hallouminate_setup.main(["hallouminate_setup.py"])
        assert rc == 2
        assert not config_path.exists()
