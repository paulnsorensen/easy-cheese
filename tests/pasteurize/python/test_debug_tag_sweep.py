"""Tests for skills/pasteurize/scripts/debug-tag-sweep.py.

Confirmation-bias killer for /pasteurize: the script must deliver a deterministic
exit-code verdict on instrumentation cleanup. Cover the contract surface — clean
vs dirty exit codes, --tags override, --json shape, --root scoping, and binary
skipping — against synthetic trees only. No conftest; load the module by path.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Iterable, Sequence
from io import StringIO
from pathlib import Path
from typing import Protocol, TextIO, TypedDict, cast

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
BUNDLE = Path(__file__).resolve().parents[3] / "skills/pasteurize/scripts/pasteurize.pyz"


class _CliNamespace(Protocol):
    def run(
        self,
        setup: Callable[[argparse.ArgumentParser], None],
        *,
        argv: Sequence[str] | None = ...,
        stdout: TextIO | None = ...,
    ) -> int: ...


class _SweepResult(TypedDict):
    files: list[str]
    total: int


class _DebugTagSweepModule(Protocol):
    cli: _CliNamespace

    def _setup(self, parser: argparse.ArgumentParser) -> None: ...
    def main(self, argv: list[str] | None = None) -> int: ...
    def session_tags(self, sessions: Iterable[str]) -> tuple[str, ...]: ...
    def changed_files(self, root: Path) -> list[Path]: ...
    def sweep(
        self,
        root: Path,
        tags: tuple[str, ...],
        *,
        files: Sequence[Path] | None = None,
    ) -> _SweepResult: ...


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BUNDLE), "debug-tag-sweep", *args],
        capture_output=True,
        text=True,
    )


class TestExitCodes:
    def test_clean_tree_exits_zero(self, tmp_path: Path) -> None:
        _ = (tmp_path / "ok.py").write_text("x = 1\n")
        result = _run("--root", str(tmp_path))
        assert result.returncode == 0, result.stderr
        assert "total: 0" in result.stdout

    def test_dirty_tree_exits_one(self, tmp_path: Path) -> None:
        _ = (tmp_path / "bug.py").write_text("x = 1  # DEBUG marker\n")
        result = _run("--root", str(tmp_path))
        assert result.returncode == 1
        assert "bug.py" in result.stdout

    def test_in_process_returns_status_and_injected_output(
        self, debug_tag_sweep: _DebugTagSweepModule, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _ = (tmp_path / "bug.py").write_text("needle\n")
        output = StringIO()
        status = debug_tag_sweep.cli.run(
            debug_tag_sweep._setup,  # pyright: ignore[reportPrivateUsage]
            argv=("--root", str(tmp_path), "--tags", "needle"),
            stdout=output,
        )
        assert status == 1
        assert output.getvalue() == "bug.py\ntotal: 1\n"
        assert capsys.readouterr().out == ""

    def test_missing_root_exits_two(self) -> None:
        result = _run("--root", "/nonexistent/path/xyz-q-9-z")
        assert result.returncode == 2
        assert "does not exist" in result.stderr

    def test_root_is_file_exits_two(self, tmp_path: Path) -> None:
        f = tmp_path / "not-a-dir.txt"
        _ = f.write_text("hi")
        result = _run("--root", str(f))
        assert result.returncode == 2
        assert "not a directory" in result.stderr


class TestJsonShape:
    def test_clean_tree_json(self, tmp_path: Path) -> None:
        _ = (tmp_path / "ok.py").write_text("x = 1\n")
        result = _run("--root", str(tmp_path), "--json")
        assert result.returncode == 0
        payload = cast(dict[str, object], json.loads(result.stdout))
        assert payload == {"files": [], "total": 0}

    def test_dirty_tree_json_lists_files(self, tmp_path: Path) -> None:
        _ = (tmp_path / "a.py").write_text("# DEBUG one\n# DEBUG two\n")
        _ = (tmp_path / "b.py").write_text("// TEMP\n")
        _ = (tmp_path / "clean.py").write_text("x = 1\n")
        result = _run("--root", str(tmp_path), "--json")
        assert result.returncode == 1
        payload = cast(dict[str, object], json.loads(result.stdout))
        assert set(cast("list[str]", payload["files"])) == {"a.py", "b.py"}
        # a.py contributes 2 hits (# DEBUG matches twice), b.py contributes 1.
        assert payload["total"] == 3


class TestTagsOverride:
    def test_custom_tag_finds_match(self, tmp_path: Path) -> None:
        _ = (tmp_path / "f.py").write_text("XYZZY-marker here\n")
        result = _run("--root", str(tmp_path), "--tags", "XYZZY-marker", "--json")
        assert result.returncode == 1
        payload = cast(dict[str, object], json.loads(result.stdout))
        assert payload["files"] == ["f.py"]

    def test_custom_tag_ignores_default_tokens(self, tmp_path: Path) -> None:
        # File has a default token (DEBUG:) but custom tags exclude it.
        _ = (tmp_path / "f.py").write_text("DEBUG: something\n")
        result = _run("--root", str(tmp_path), "--tags", "ONLY-CUSTOM", "--json")
        assert result.returncode == 0
        payload = cast(dict[str, object], json.loads(result.stdout))
        assert payload == {"files": [], "total": 0}

    def test_multiple_custom_tags(self, tmp_path: Path) -> None:
        _ = (tmp_path / "a.py").write_text("FOO-thing\n")
        _ = (tmp_path / "b.py").write_text("BAR-thing\n")
        result = _run("--root", str(tmp_path), "--tags", "FOO-thing,BAR-thing", "--json")
        assert result.returncode == 1
        payload = cast(dict[str, object], json.loads(result.stdout))
        assert set(cast("list[str]", payload["files"])) == {"a.py", "b.py"}
        assert payload["total"] == 2


class TestRootScope:
    def test_root_scopes_scan(self, tmp_path: Path) -> None:
        inside = tmp_path / "inside"
        outside = tmp_path / "outside"
        inside.mkdir()
        outside.mkdir()
        _ = (inside / "ok.py").write_text("x = 1\n")
        _ = (outside / "bug.py").write_text("# DEBUG bad\n")
        result = _run("--root", str(inside), "--json")
        assert result.returncode == 0
        payload = cast(dict[str, object], json.loads(result.stdout))
        assert payload == {"files": [], "total": 0}

    def test_skip_dirs_are_ignored(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        _ = (tmp_path / ".git" / "config").write_text("# DEBUG inside .git\n")
        (tmp_path / "node_modules").mkdir()
        _ = (tmp_path / "node_modules" / "pkg.js").write_text("// TEMP\n")
        _ = (tmp_path / "ok.py").write_text("x = 1\n")
        result = _run("--root", str(tmp_path), "--json")
        assert result.returncode == 0
        payload = cast(dict[str, object], json.loads(result.stdout))
        assert payload == {"files": [], "total": 0}


class TestBinaryFiles:
    def test_binary_files_skipped(self, tmp_path: Path) -> None:
        # NUL byte in first 4KB makes the sniffer treat it as binary, even
        # though "DEBUG:" appears later.
        _ = (tmp_path / "blob.bin").write_bytes(b"\x00" * 16 + b"DEBUG: leaked\n")
        result = _run("--root", str(tmp_path), "--json")
        assert result.returncode == 0
        payload = cast(dict[str, object], json.loads(result.stdout))
        assert payload == {"files": [], "total": 0}


class TestDefaultTags:
    @pytest.mark.parametrize(
        "line",
        [
            "DEBUG: trace\n",
            "TEMP: remove later\n",
            "TODO-pasteurize: fix\n",
            "x = 1  # DEBUG note\n",
            "let y = 2;  // TEMP note\n",
            "<p><!-- TODO-pasteurize copy --></p>\n",
        ],
    )
    def test_each_default_tag_triggers(self, tmp_path: Path, line: str) -> None:
        _ = (tmp_path / "f.txt").write_text(line)
        result = _run("--root", str(tmp_path), "--json")
        assert result.returncode == 1, f"default tag missed in: {line!r}"
        payload = cast(dict[str, object], json.loads(result.stdout))
        assert payload["files"] == ["f.txt"]
        assert cast(int, payload["total"]) >= 1


class TestSweepFunction:
    def test_sweep_returns_relative_paths(self, debug_tag_sweep: _DebugTagSweepModule, tmp_path: Path) -> None:
        sub = tmp_path / "pkg"
        sub.mkdir()
        _ = (sub / "mod.py").write_text("# DEBUG x\n")
        result = debug_tag_sweep.sweep(tmp_path, ("# DEBUG",))
        assert result["files"] == ["pkg/mod.py"]
        assert result["total"] == 1

    def test_sweep_files_sorted(self, debug_tag_sweep: _DebugTagSweepModule, tmp_path: Path) -> None:
        for name in ("z.py", "a.py", "m.py"):
            _ = (tmp_path / name).write_text("DEBUG: hit\n")
        result = debug_tag_sweep.sweep(tmp_path, ("DEBUG:",))
        assert result["files"] == ["a.py", "m.py", "z.py"]


class TestSessionTags:
    """Regression: the sweep must match the exact session token, not a prefix.

    `.cheese/notes/r014-megamerge/review-pasteurize.md` records a root probe
    that reported four files and 398 matches, all of them the scanner's own
    examples, constants, and tests.
    """

    def test_session_tag_builds_the_exact_token(
        self, debug_tag_sweep: _DebugTagSweepModule
    ) -> None:
        assert debug_tag_sweep.session_tags(["a4f2"]) == ("[DEBUG-a4f2]",)
        assert debug_tag_sweep.session_tags(["a4f2", "b7c1"]) == (
            "[DEBUG-a4f2]",
            "[DEBUG-b7c1]",
        )

    @pytest.mark.parametrize("session", ["a4f2 b7", "a/b", "x" * 33, ""])
    def test_unusable_session_tag_is_rejected(
        self, debug_tag_sweep: _DebugTagSweepModule, session: str
    ) -> None:
        with pytest.raises(ValueError):
            _ = debug_tag_sweep.session_tags([session])

    def test_another_session_tag_is_not_a_hit(
        self, debug_tag_sweep: _DebugTagSweepModule, tmp_path: Path
    ) -> None:
        _ = (tmp_path / "mine.py").write_text('print("[DEBUG-a4f2] here")\n')
        _ = (tmp_path / "theirs.py").write_text('print("[DEBUG-b7c1] here")\n')
        result = debug_tag_sweep.sweep(
            tmp_path, debug_tag_sweep.session_tags(["a4f2"])
        )
        assert result["files"] == ["mine.py"]
        assert result["total"] == 1

    def test_prefix_documentation_is_not_a_hit(
        self, debug_tag_sweep: _DebugTagSweepModule, tmp_path: Path
    ) -> None:
        # The skill and this scanner both name the bare `[DEBUG-` prefix.
        _ = (tmp_path / "SKILL.md").write_text("Use a tag such as `[DEBUG-\n")
        result = debug_tag_sweep.sweep(
            tmp_path, debug_tag_sweep.session_tags(["a4f2"])
        )
        assert result == {"files": [], "total": 0}

    def test_cli_rejects_session_tag_with_tags(
        self,
        debug_tag_sweep: _DebugTagSweepModule,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        status = debug_tag_sweep.main(
            ["--root", str(tmp_path), "--session-tag", "a4f2", "--tags", "X"]
        )
        assert status == 2
        assert "not both" in capsys.readouterr().err

    def test_cli_session_tag_scopes_the_verdict(
        self,
        debug_tag_sweep: _DebugTagSweepModule,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _ = (tmp_path / "noise.py").write_text("# DEBUG unrelated note\n")
        status = debug_tag_sweep.main(
            ["--root", str(tmp_path), "--session-tag", "a4f2", "--json"]
        )
        assert status == 0
        assert json.loads(capsys.readouterr().out) == {"files": [], "total": 0}


class TestToolArtifactExclusion:
    """Regression: run logs and tool output are not surviving instrumentation."""

    @pytest.mark.parametrize("directory", [".cheese", ".milknado", ".claude"])
    def test_tool_directory_is_skipped(
        self, debug_tag_sweep: _DebugTagSweepModule, tmp_path: Path, directory: str
    ) -> None:
        (tmp_path / directory).mkdir()
        _ = (tmp_path / directory / "note.md").write_text("[DEBUG-a4f2] logged\n")
        result = debug_tag_sweep.sweep(
            tmp_path, debug_tag_sweep.session_tags(["a4f2"])
        )
        assert result == {"files": [], "total": 0}

    def test_log_file_is_skipped(
        self, debug_tag_sweep: _DebugTagSweepModule, tmp_path: Path
    ) -> None:
        _ = (tmp_path / "run.log").write_text("[DEBUG-a4f2] logged\n")
        result = debug_tag_sweep.sweep(
            tmp_path, debug_tag_sweep.session_tags(["a4f2"])
        )
        assert result == {"files": [], "total": 0}

    def test_explicit_file_list_still_skips_a_tool_path(
        self, debug_tag_sweep: _DebugTagSweepModule, tmp_path: Path
    ) -> None:
        (tmp_path / ".cheese").mkdir()
        logged = tmp_path / ".cheese" / "note.md"
        _ = logged.write_text("[DEBUG-a4f2] logged\n")
        result = debug_tag_sweep.sweep(
            tmp_path, debug_tag_sweep.session_tags(["a4f2"]), files=[logged]
        )
        assert result == {"files": [], "total": 0}


class TestChangedOnly:
    """Regression: the sweep scopes to the files that this worktree changed."""

    @staticmethod
    def _git(root: Path, *args: str) -> None:
        _ = subprocess.run(
            ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
        )

    def _repository(self, root: Path) -> None:
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "sweep@example.test")
        self._git(root, "config", "user.name", "Sweep Test")
        _ = (root / "old.py").write_text("[DEBUG-a4f2] committed earlier\n")
        self._git(root, "add", "-A")
        self._git(root, "commit", "-q", "-m", "seed")

    def test_changed_files_lists_edits_and_new_files(
        self, debug_tag_sweep: _DebugTagSweepModule, tmp_path: Path
    ) -> None:
        self._repository(tmp_path)
        _ = (tmp_path / "new.py").write_text("x = 1\n")
        _ = (tmp_path / "old.py").write_text("[DEBUG-a4f2] still here\n# edit\n")
        names = {path.name for path in debug_tag_sweep.changed_files(tmp_path)}
        assert names == {"new.py", "old.py"}

    def test_changed_only_ignores_an_untouched_file(
        self,
        debug_tag_sweep: _DebugTagSweepModule,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._repository(tmp_path)
        _ = (tmp_path / "new.py").write_text("x = 1\n")
        status = debug_tag_sweep.main(
            [
                "--root", str(tmp_path),
                "--session-tag", "a4f2",
                "--changed-only",
                "--json",
            ]
        )
        assert status == 0, "the committed file is outside this session's scope"
        assert json.loads(capsys.readouterr().out) == {"files": [], "total": 0}

    def test_changed_only_reports_a_changed_file(
        self,
        debug_tag_sweep: _DebugTagSweepModule,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._repository(tmp_path)
        _ = (tmp_path / "new.py").write_text("[DEBUG-a4f2] left behind\n")
        status = debug_tag_sweep.main(
            [
                "--root", str(tmp_path),
                "--session-tag", "a4f2",
                "--changed-only",
                "--json",
            ]
        )
        assert status == 1
        assert json.loads(capsys.readouterr().out) == {
            "files": ["new.py"],
            "total": 1,
        }

    def test_changed_only_without_a_repository_exits_two(
        self,
        debug_tag_sweep: _DebugTagSweepModule,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        status = debug_tag_sweep.main(
            ["--root", str(tmp_path), "--session-tag", "a4f2", "--changed-only"]
        )
        assert status == 2
        assert "Git worktree" in capsys.readouterr().err
