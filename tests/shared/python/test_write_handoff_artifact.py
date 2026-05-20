"""Tests for shared/scripts/write_handoff_artifact.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SCRIPTS = REPO_ROOT / "shared" / "scripts"
WRITER_CLI = SHARED_SCRIPTS / "write_handoff_artifact.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def writer() -> ModuleType:
    # cli + handoff first so write_handoff_artifact's `import cli` / `import handoff` resolve.
    if str(SHARED_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SHARED_SCRIPTS))
    _load("cli", SHARED_SCRIPTS / "cli.py")
    _load("handoff", SHARED_SCRIPTS / "handoff.py")
    return _load("write_handoff_artifact", WRITER_CLI)


@pytest.fixture(scope="module")
def handoff_mod() -> ModuleType:
    if str(SHARED_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SHARED_SCRIPTS))
    return _load("handoff", SHARED_SCRIPTS / "handoff.py")


class TestPreambleRoundTrip:
    def test_ok_status_round_trips(
        self, writer: ModuleType, handoff_mod: ModuleType, tmp_path: Path
    ) -> None:
        target = writer.write_artifact(
            slug="my-task",
            status="ok",
            next_skill="age",
            artifact=".cheese/press/my-task.md",
            orientation="implemented widget",
            body=None,
            root=tmp_path,
        )
        assert target == tmp_path / ".cheese" / "age" / "my-task.md"
        slug = handoff_mod.parse_handoff_slug(target.read_text(encoding="utf-8"))
        assert slug.status == "ok"
        assert slug.halt_reason is None
        assert slug.next_skill == "age"
        assert slug.artifact == ".cheese/press/my-task.md"
        assert slug.orientation == "implemented widget"

    def test_halt_status_round_trips(
        self, writer: ModuleType, handoff_mod: ModuleType, tmp_path: Path
    ) -> None:
        target = writer.write_artifact(
            slug="blocked",
            status="halt: tests failed",
            next_skill="cure",
            artifact=".cheese/age/blocked.md",
            orientation="three findings remain",
            body=None,
            root=tmp_path,
        )
        slug = handoff_mod.parse_handoff_slug(target.read_text(encoding="utf-8"))
        assert slug.status == "halt"
        assert slug.halt_reason == "tests failed"
        assert slug.next_skill == "cure"


class TestBodyFile:
    def test_body_content_appended_with_blank_separator(
        self, writer: ModuleType, handoff_mod: ModuleType, tmp_path: Path
    ) -> None:
        body_src = tmp_path / "body.md"
        body_text = "# Report\n\nLine one.\nLine two.\n"
        body_src.write_text(body_text, encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(WRITER_CLI),
                "--slug", "with-body",
                "--status", "ok",
                "--next", "age",
                "--artifact", "",
                "--orientation", "demo",
                "--body-file", str(body_src),
                "--root", str(tmp_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        target = tmp_path / ".cheese" / "age" / "with-body.md"
        assert target.exists()
        assert result.stdout.strip().endswith("with-body.md")

        content = target.read_text(encoding="utf-8")
        lines = content.splitlines()
        # Preamble parses cleanly off the top.
        slug = handoff_mod.parse_handoff_slug(content)
        assert slug.orientation == "demo"
        assert slug.artifact is None  # empty artifact

        # Line 5 must be blank, then body verbatim.
        assert lines[4] == ""
        assert "\n".join(lines[5:]) + ("\n" if content.endswith("\n") else "") == body_text


class TestCliErrors:
    def test_missing_required_flag_exits_2(self, tmp_path: Path) -> None:
        # Drop --orientation; argparse should reject with exit code 2.
        result = subprocess.run(
            [
                sys.executable,
                str(WRITER_CLI),
                "--slug", "x",
                "--status", "ok",
                "--next", "age",
                "--artifact", "",
                "--root", str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "orientation" in result.stderr.lower()

    def test_missing_body_file_exits_2(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(WRITER_CLI),
                "--slug", "x",
                "--status", "ok",
                "--next", "age",
                "--artifact", "",
                "--orientation", "demo",
                "--body-file", str(tmp_path / "nope.md"),
                "--root", str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "body-file" in result.stderr.lower()


class TestPathDerivation:
    def test_path_is_under_root_dot_cheese_next(
        self, writer: ModuleType, tmp_path: Path
    ) -> None:
        target = writer.write_artifact(
            slug="curd-7",
            status="ok",
            next_skill="cheese-factory/skill-scripts/curds",
            artifact="",
            orientation="curd 7 done",
            body=None,
            root=tmp_path,
        )
        # Nested next paths should be honored (factory writes to subdirs).
        assert target == tmp_path / ".cheese" / "cheese-factory" / "skill-scripts" / "curds" / "curd-7.md"
        assert target.is_file()


class TestPhaseFlag:
    """`--phase` names this phase's own directory; `--next` stays as preamble-only."""

    def test_phase_overrides_next_for_on_disk_path(
        self, writer: ModuleType, tmp_path: Path
    ) -> None:
        # Press writes its own report at .cheese/press/<slug>.md while pointing
        # the next phase at age. Before --phase existed, the writer derived the
        # path from --next and so dropped press's report into .cheese/age/.
        target = writer.write_artifact(
            slug="my-task",
            status="ok",
            next_skill="age",
            artifact=".cheese/cook/my-task.md",
            orientation="press hardened the diff",
            body=None,
            root=tmp_path,
            phase="press",
        )
        assert target == tmp_path / ".cheese" / "press" / "my-task.md"
        assert not (tmp_path / ".cheese" / "age" / "my-task.md").exists()

    def test_phase_cli_flag_lands_artifact_under_phase_dir(
        self,
        handoff_mod: ModuleType,
        tmp_path: Path,
    ) -> None:
        # Subprocess: --phase age --next cure means the file lives at
        # .cheese/age/<slug>.md and the preamble names cure as next.
        result = subprocess.run(
            [
                sys.executable,
                str(WRITER_CLI),
                "--slug", "phase-flag",
                "--status", "ok",
                "--phase", "age",
                "--next", "cure",
                "--artifact", ".cheese/press/phase-flag.md",
                "--orientation", "age reviewed press output",
                "--root", str(tmp_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        target = tmp_path / ".cheese" / "age" / "phase-flag.md"
        assert target.exists()
        assert result.stdout.strip().endswith(str(target))
        slug = handoff_mod.parse_handoff_slug(target.read_text(encoding="utf-8"))
        assert slug.next_skill == "cure"
        assert slug.artifact == ".cheese/press/phase-flag.md"

    def test_phase_omitted_falls_back_to_next(
        self, writer: ModuleType, tmp_path: Path
    ) -> None:
        # Backward compatibility: callers that have not migrated still get the
        # legacy "write to next-phase directory" shape so existing chains keep
        # working until they update their invocations.
        target = writer.write_artifact(
            slug="legacy",
            status="ok",
            next_skill="age",
            artifact="",
            orientation="cook done",
            body=None,
            root=tmp_path,
        )
        assert target == tmp_path / ".cheese" / "age" / "legacy.md"


class TestAtomicRename:
    def test_no_partial_file_when_rename_fails(
        self,
        writer: ModuleType,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Force os.rename to fail; assert target is absent and no .tmp lingers.
        import os as _os

        def boom(src: str, dst: str) -> None:  # noqa: ARG001
            raise OSError("simulated rename failure")

        monkeypatch.setattr(_os, "rename", boom)

        with pytest.raises(OSError, match="simulated rename failure"):
            writer.write_artifact(
                slug="never",
                status="ok",
                next_skill="age",
                artifact="",
                orientation="will not land",
                body=None,
                root=tmp_path,
            )

        target_dir = tmp_path / ".cheese" / "age"
        # Directory may exist (we mkdir'd before the write), but no artifact and no .tmp.
        assert not (target_dir / "never.md").exists()
        leftovers = list(target_dir.glob("*.tmp")) if target_dir.exists() else []
        assert leftovers == [], f"tmp file leaked: {leftovers}"
