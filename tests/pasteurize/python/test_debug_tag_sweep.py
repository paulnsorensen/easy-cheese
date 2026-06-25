"""Tests for skills/pasteurize/scripts/debug-tag-sweep.py.

Confirmation-bias killer for /pasteurize: the script must deliver a deterministic
exit-code verdict on instrumentation cleanup. Cover the contract surface — clean
vs dirty exit codes, --tags override, --json shape, --root scoping, and binary
skipping — against synthetic trees only. No conftest; load the module by path.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import build_pyz  # noqa: E402

BUNDLE = build_pyz.cached_bundle("pasteurize")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BUNDLE), "debug-tag-sweep", *args],
        capture_output=True,
        text=True,
    )


class TestExitCodes:
    def test_clean_tree_exits_zero(self, tmp_path: Path) -> None:
        (tmp_path / "ok.py").write_text("x = 1\n")
        result = _run("--root", str(tmp_path))
        assert result.returncode == 0, result.stderr
        assert "total: 0" in result.stdout

    def test_dirty_tree_exits_one(self, tmp_path: Path) -> None:
        (tmp_path / "bug.py").write_text("x = 1  # DEBUG marker\n")
        result = _run("--root", str(tmp_path))
        assert result.returncode == 1
        assert "bug.py" in result.stdout

    def test_missing_root_exits_two(self) -> None:
        result = _run("--root", "/nonexistent/path/xyz-q-9-z")
        assert result.returncode == 2
        assert "does not exist" in result.stderr

    def test_root_is_file_exits_two(self, tmp_path: Path) -> None:
        f = tmp_path / "not-a-dir.txt"
        f.write_text("hi")
        result = _run("--root", str(f))
        assert result.returncode == 2
        assert "not a directory" in result.stderr


class TestJsonShape:
    def test_clean_tree_json(self, tmp_path: Path) -> None:
        (tmp_path / "ok.py").write_text("x = 1\n")
        result = _run("--root", str(tmp_path), "--json")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload == {"files": [], "total": 0}

    def test_dirty_tree_json_lists_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("# DEBUG one\n# DEBUG two\n")
        (tmp_path / "b.py").write_text("// TEMP\n")
        (tmp_path / "clean.py").write_text("x = 1\n")
        result = _run("--root", str(tmp_path), "--json")
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert set(payload["files"]) == {"a.py", "b.py"}
        # a.py contributes 2 hits (# DEBUG matches twice), b.py contributes 1.
        assert payload["total"] == 3


class TestTagsOverride:
    def test_custom_tag_finds_match(self, tmp_path: Path) -> None:
        (tmp_path / "f.py").write_text("XYZZY-marker here\n")
        result = _run("--root", str(tmp_path), "--tags", "XYZZY-marker", "--json")
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["files"] == ["f.py"]

    def test_custom_tag_ignores_default_tokens(self, tmp_path: Path) -> None:
        # File has a default token (DEBUG:) but custom tags exclude it.
        (tmp_path / "f.py").write_text("DEBUG: something\n")
        result = _run("--root", str(tmp_path), "--tags", "ONLY-CUSTOM", "--json")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload == {"files": [], "total": 0}

    def test_multiple_custom_tags(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("FOO-thing\n")
        (tmp_path / "b.py").write_text("BAR-thing\n")
        result = _run("--root", str(tmp_path), "--tags", "FOO-thing,BAR-thing", "--json")
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert set(payload["files"]) == {"a.py", "b.py"}
        assert payload["total"] == 2


class TestRootScope:
    def test_root_scopes_scan(self, tmp_path: Path) -> None:
        inside = tmp_path / "inside"
        outside = tmp_path / "outside"
        inside.mkdir()
        outside.mkdir()
        (inside / "ok.py").write_text("x = 1\n")
        (outside / "bug.py").write_text("# DEBUG bad\n")
        result = _run("--root", str(inside), "--json")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload == {"files": [], "total": 0}

    def test_skip_dirs_are_ignored(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("# DEBUG inside .git\n")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg.js").write_text("// TEMP\n")
        (tmp_path / "ok.py").write_text("x = 1\n")
        result = _run("--root", str(tmp_path), "--json")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload == {"files": [], "total": 0}


class TestBinaryFiles:
    def test_binary_files_skipped(self, tmp_path: Path) -> None:
        # NUL byte in first 4KB makes the sniffer treat it as binary, even
        # though "DEBUG:" appears later.
        (tmp_path / "blob.bin").write_bytes(b"\x00" * 16 + b"DEBUG: leaked\n")
        result = _run("--root", str(tmp_path), "--json")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
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
        (tmp_path / "f.txt").write_text(line)
        result = _run("--root", str(tmp_path), "--json")
        assert result.returncode == 1, f"default tag missed in: {line!r}"
        payload = json.loads(result.stdout)
        assert payload["files"] == ["f.txt"]
        assert payload["total"] >= 1


class TestSweepFunction:
    def test_sweep_returns_relative_paths(self, debug_tag_sweep: ModuleType, tmp_path: Path) -> None:
        sub = tmp_path / "pkg"
        sub.mkdir()
        (sub / "mod.py").write_text("# DEBUG x\n")
        result = debug_tag_sweep.sweep(tmp_path, ("# DEBUG",))
        assert result["files"] == ["pkg/mod.py"]
        assert result["total"] == 1

    def test_sweep_files_sorted(self, debug_tag_sweep: ModuleType, tmp_path: Path) -> None:
        for name in ("z.py", "a.py", "m.py"):
            (tmp_path / name).write_text("DEBUG: hit\n")
        result = debug_tag_sweep.sweep(tmp_path, ("DEBUG:",))
        assert result["files"] == ["a.py", "m.py", "z.py"]
