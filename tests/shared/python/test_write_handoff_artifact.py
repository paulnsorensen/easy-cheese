"""Tests for shared/scripts/write_handoff_artifact.py."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Protocol, TypedDict

import pytest

from easy_cheese.shared.wheypoint import commit as commit_module
from easy_cheese.shared.wheypoint import lint as lint_module
from easy_cheese.shared.wheypoint import resolve as resolve_module
from easy_cheese.shared.wheypoint import storage as wheypoint_storage

from easy_cheese_schemas.contracts import CheckpointIntent, NextMove, WheypointDelta
from easy_cheese.shared.wheypoint import checkpoint

if TYPE_CHECKING:
    from easy_cheese.shared.cli import CliError
    from easy_cheese.shared.handoff import HandoffParseError, HandoffSlug

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SCRIPTS = REPO_ROOT / "src" / "easy_cheese" / "shared"
WRITER_CLI = SHARED_SCRIPTS / "write_handoff_artifact.py"


@pytest.fixture(autouse=True)
def _isolated_writer_environment(  # pyright: ignore[reportUnusedFunction]
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path / "corpus"))
    monkeypatch.setenv("EASY_CHEESE_PROJECT", "writer-tests")
    _ = (tmp_path / "context.md").write_text("grounded\n", encoding="utf-8")


class _CliModule(Protocol):
    CliError: type[CliError]


class _WriterModule(Protocol):
    cli: _CliModule

    def write_artifact(
        self,
        *,
        slug: str,
        status: str,
        next_skill: str,
        artifact: str,
        orientation: str,
        body: str | None,
        root: Path,
        phase: str,
        payload_schema_uri: str | None = None,
        taste_test: str | None = None,
        durable_flags: str | None = None,
        baseline: str | None = None,
        grounded: Sequence[str] = (),
        corpus_root: Path | str | None = None,
    ) -> Path: ...

    def main(self, argv: list[str]) -> int: ...


class _RerunKwargs(TypedDict):
    slug: str
    status: str
    phase: str
    next_skill: str
    artifact: str
    body: str | None
    root: Path


class _HandoffModule(Protocol):
    HandoffSlug: type[HandoffSlug]
    HandoffParseError: type[HandoffParseError]

    def parse_handoff_slug(self, text: str) -> HandoffSlug: ...
    def render_handoff_slug(self, slug: HandoffSlug) -> str: ...


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
    _ = _load("cli", SHARED_SCRIPTS / "cli.py")
    _ = _load("handoff", SHARED_SCRIPTS / "handoff.py")
    return _load("write_handoff_artifact", WRITER_CLI)


@pytest.fixture(scope="module")
def handoff_mod() -> ModuleType:
    if str(SHARED_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SHARED_SCRIPTS))
    return _load("handoff", SHARED_SCRIPTS / "handoff.py")


class TestPreambleRoundTrip:
    def test_ok_status_round_trips(
        self, writer: _WriterModule, handoff_mod: _HandoffModule, tmp_path: Path
    ) -> None:
        target = writer.write_artifact(
            slug="my-task",
            status="ok",
            phase="press",
            next_skill="age",
            artifact=".cheese/press/my-task.md",
            orientation="implemented widget",
            body=None,
            root=tmp_path,
            grounded=("context.md#1-1",),
        )
        assert target == tmp_path / ".cheese" / "press" / "my-task.md"
        slug = handoff_mod.parse_handoff_slug(target.read_text(encoding="utf-8"))
        assert slug.status == "ok"
        assert slug.halt_reason is None
        assert slug.next_skill == "age"
        assert slug.artifact == ".cheese/press/my-task.md"
        assert slug.orientation == "implemented widget"
        assert slug.taste_test is None
        assert slug.durable_flags is None

    def test_halt_status_round_trips(
        self, writer: _WriterModule, handoff_mod: _HandoffModule, tmp_path: Path
    ) -> None:
        target = writer.write_artifact(
            slug="blocked",
            status="halt: tests failed",
            phase="age",
            next_skill="cure",
            artifact=".cheese/age/blocked.md",
            orientation="three findings remain",
            body=None,
            grounded=("context.md#1-1",),
            root=tmp_path,
        )
        slug = handoff_mod.parse_handoff_slug(target.read_text(encoding="utf-8"))
        assert slug.status == "halt"
        assert slug.halt_reason == "tests failed"
        assert slug.next_skill == "cure"


class TestPathTraversalRejected:
    @pytest.mark.parametrize("bad_slug", ["../escape", "a/b", "..", "win\\esc"])
    def test_traversal_slug_rejected(
        self, writer: _WriterModule, tmp_path: Path, bad_slug: str
    ) -> None:
        with pytest.raises(writer.cli.CliError):
            _ = writer.write_artifact(
                slug=bad_slug,
                status="ok",
                phase="age",
                next_skill="done",
                artifact="",
                orientation="x",
                body=None,
                root=tmp_path,
            )

    def test_traversal_phase_rejected(
        self, writer: _WriterModule, tmp_path: Path
    ) -> None:
        with pytest.raises(writer.cli.CliError):
            _ = writer.write_artifact(
                slug="ok-slug",
                status="ok",
                next_skill="done",
                artifact="",
                orientation="x",
                body=None,
                root=tmp_path,
                phase="../etc",
            )

    def test_genesis_requires_grounded_context(
        self, writer: _WriterModule, tmp_path: Path
    ) -> None:
        with pytest.raises(
            writer.cli.CliError,
            match="a genesis phase write requires at least one --grounded entry",
        ) as excinfo:
            _ = writer.write_artifact(
                slug="empty-genesis",
                status="ok",
                phase="cook",
                next_skill="press",
                artifact="",
                orientation="x",
                body=None,
                root=tmp_path,
            )
        assert excinfo.value.exit_code == 2
        assert not (tmp_path / ".cheese" / "cook" / "empty-genesis.md").exists()


class TestRerunOverwrite:
    def test_rerun_same_slug_overwrites(
        self, writer: _WriterModule, tmp_path: Path
    ) -> None:
        # os.replace (not os.rename) must overwrite an existing artifact cleanly
        # on a re-run — the cross-platform atomic-overwrite contract.
        common: _RerunKwargs = {
            "slug": "rerun",
            "status": "ok",
            "phase": "press",
            "next_skill": "age",
            "artifact": "",
            "body": None,
            "root": tmp_path,
        }
        target = writer.write_artifact(
            orientation="first pass",
            grounded=("context.md#1-1",),
            **common,
        )
        rewritten = writer.write_artifact(
            orientation="second pass",
            grounded=("context.md#1-1",),
            **common,
        )
        assert rewritten == target
        assert "second pass" in target.read_text(encoding="utf-8")
        assert "first pass" not in target.read_text(encoding="utf-8")


class TestOptionalKeyedLines:
    """Regression tests: optional taste_test:/durable_flags: preamble lines.

    The prose slug schemas (skills/cook/SKILL.md, skills/age/SKILL.md) place
    these keyed lines between `artifact:` and the orientation; the parser
    must consume them instead of swallowing them as the orientation, while
    plain four-line slugs keep parsing identically.
    """

    def test_four_line_slug_back_compat(self, handoff_mod: _HandoffModule) -> None:
        slug = handoff_mod.parse_handoff_slug(
            "status: ok\n"
            + "next: cure\n"
            + "artifact: .cheese/press/demo.md\n"
            + "reviewed the retry path\n"
        )
        assert slug.orientation == "reviewed the retry path"
        assert slug.taste_test is None
        assert slug.durable_flags is None

    def test_durable_flags_keyed_line(self, handoff_mod: _HandoffModule) -> None:
        # The age-slug shape: durable_flags between artifact and orientation.
        slug = handoff_mod.parse_handoff_slug(
            "status: ok\n"
            + "next: cure\n"
            + "artifact: .cheese/press/demo.md\n"
            + "durable_flags: none\n"
            + "reviewed the retry path\n"
        )
        assert slug.durable_flags == "none"
        # The keyed line must not be swallowed as the orientation.
        assert slug.orientation == "reviewed the retry path"

    def test_taste_test_and_durable_flags(self, handoff_mod: _HandoffModule) -> None:
        # The cook-slug shape: both keyed lines before the orientation.
        slug = handoff_mod.parse_handoff_slug(
            "status: ok\n"
            + "next: press\n"
            + "artifact:\n"
            + "taste_test: inline-pass\n"
            + "durable_flags: keyed-line parsing added -> handoff-contract\n"
            + "cook implemented widget\n"
        )
        assert slug.taste_test == "inline-pass"
        assert slug.durable_flags == "keyed-line parsing added -> handoff-contract"
        assert slug.orientation == "cook implemented widget"

    def test_render_parse_roundtrip_with_keyed_lines(
        self, handoff_mod: _HandoffModule
    ) -> None:
        original = handoff_mod.HandoffSlug(
            status="ok",
            halt_reason=None,
            next_skill="cure",
            artifact=".cheese/age/demo.md",
            orientation="reviewed widget",
            taste_test="dispatched-pass",
            durable_flags="none",
        )
        rendered = handoff_mod.render_handoff_slug(original)
        assert handoff_mod.parse_handoff_slug(rendered) == original

    def test_duplicate_keyed_line_fails_loud(self, handoff_mod: _HandoffModule) -> None:
        text = (
            "status: ok\nnext: cure\nartifact:\n"
            "durable_flags: none\ndurable_flags: none\norient\n"
        )
        with pytest.raises(
            handoff_mod.HandoffParseError, match="duplicate 'durable_flags:'"
        ):
            _ = handoff_mod.parse_handoff_slug(text)

    def test_keyed_line_without_value_fails_loud(
        self, handoff_mod: _HandoffModule
    ) -> None:
        text = "status: ok\nnext: cure\nartifact:\ndurable_flags:\norient\n"
        with pytest.raises(handoff_mod.HandoffParseError, match="requires a value"):
            _ = handoff_mod.parse_handoff_slug(text)

    def test_writer_emits_durable_flags(
        self, writer: _WriterModule, handoff_mod: _HandoffModule, tmp_path: Path
    ) -> None:
        target = writer.write_artifact(
            slug="flagged",
            status="ok",
            next_skill="cure",
            artifact="",
            orientation="reviewed widget",
            body=None,
            root=tmp_path,
            phase="age",
            grounded=("context.md#1-1",),
            durable_flags="keyed-line contract -> handoff-contract",
        )
        slug = handoff_mod.parse_handoff_slug(target.read_text(encoding="utf-8"))
        assert target == tmp_path / ".cheese" / "age" / "flagged.md"
        assert slug.durable_flags == "keyed-line contract -> handoff-contract"
        assert slug.orientation == "reviewed widget"

    def test_writer_cli_flags_roundtrip(
        self, handoff_mod: _HandoffModule, tmp_path: Path
    ) -> None:
        # Locks the argparse dest wiring (--taste-test/--durable-flags).
        result = subprocess.run(
            [
                sys.executable,
                str(WRITER_CLI),
                "--slug",
                "cli-flagged",
                "--status",
                "ok",
                "--phase",
                "age",
                "--next",
                "cure",
                "--artifact",
                "",
                "--orientation",
                "demo",
                "--taste-test",
                "inline-pass",
                "--durable-flags",
                "none",
                "--grounded",
                "context.md#1-1",
            ],
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr
        target = tmp_path / ".cheese" / "age" / "cli-flagged.md"
        slug = handoff_mod.parse_handoff_slug(target.read_text(encoding="utf-8"))
        assert slug.taste_test == "inline-pass"
        assert slug.durable_flags == "none"

    def test_baseline_keyed_line_present_does_not_corrupt_orientation(
        self, handoff_mod: _HandoffModule
    ) -> None:
        # Repro: a `baseline:` line between artifact and orientation must be
        # consumed as a keyed line, not swallowed as the orientation.
        slug = handoff_mod.parse_handoff_slug(
            "status: ok\n"
            + "next: cure\n"
            + "artifact: .cheese/press/demo.md\n"
            + "baseline: none\n"
            + "reviewed the retry path\n"
        )
        assert slug.baseline == "none"
        assert slug.orientation == "reviewed the retry path"

    def test_render_parse_roundtrip_with_baseline_present(
        self, handoff_mod: _HandoffModule
    ) -> None:
        original = handoff_mod.HandoffSlug(
            status="ok",
            halt_reason=None,
            next_skill="cure",
            artifact=".cheese/age/demo.md",
            orientation="reviewed widget",
            taste_test="dispatched-pass",
            durable_flags="none",
            baseline="none",
        )
        rendered = handoff_mod.render_handoff_slug(original)
        assert handoff_mod.parse_handoff_slug(rendered) == original

    def test_render_parse_roundtrip_with_baseline_absent(
        self, handoff_mod: _HandoffModule
    ) -> None:
        original = handoff_mod.HandoffSlug(
            status="ok",
            halt_reason=None,
            next_skill="cure",
            artifact=".cheese/age/demo.md",
            orientation="reviewed widget",
        )
        rendered = handoff_mod.render_handoff_slug(original)
        round_tripped = handoff_mod.parse_handoff_slug(rendered)
        assert round_tripped == original
        assert round_tripped.baseline is None

    def test_writer_emits_baseline(
        self, writer: _WriterModule, handoff_mod: _HandoffModule, tmp_path: Path
    ) -> None:
        target = writer.write_artifact(
            slug="baselined",
            status="ok",
            next_skill="cure",
            artifact="",
            orientation="reviewed widget",
            body=None,
            root=tmp_path,
            grounded=("context.md#1-1",),
            phase="age",
            baseline="none",
        )
        slug = handoff_mod.parse_handoff_slug(target.read_text(encoding="utf-8"))
        assert slug.baseline == "none"
        assert slug.orientation == "reviewed widget"

    def test_writer_cli_baseline_flag_roundtrip(
        self, handoff_mod: _HandoffModule, tmp_path: Path
    ) -> None:
        # Locks the argparse dest wiring (--baseline).
        result = subprocess.run(
            [
                sys.executable,
                str(WRITER_CLI),
                "--slug",
                "cli-baselined",
                "--status",
                "ok",
                "--phase",
                "age",
                "--next",
                "cure",
                "--artifact",
                "",
                "--orientation",
                "demo",
                "--baseline",
                "none",
                "--grounded",
                "context.md#1-1",
            ],
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr
        target = tmp_path / ".cheese" / "age" / "cli-baselined.md"
        slug = handoff_mod.parse_handoff_slug(target.read_text(encoding="utf-8"))
        assert slug.baseline == "none"


class TestBodyFile:
    def test_body_content_appended_with_blank_separator(
        self, handoff_mod: _HandoffModule, tmp_path: Path
    ) -> None:
        body_src = tmp_path / "body.md"
        body_text = "# Report\n\nLine one.\nLine two.\n"
        _ = body_src.write_text(body_text, encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(WRITER_CLI),
                "--slug",
                "with-body",
                "--status",
                "ok",
                "--phase",
                "age",
                "--next",
                "cure",
                "--artifact",
                "",
                "--orientation",
                "demo",
                "--body-file",
                str(body_src),
                "--root",
                str(tmp_path),
                "--grounded",
                "context.md#1-1",
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
        slug = handoff_mod.parse_handoff_slug(content)
        assert slug.orientation == "demo"
        assert slug.artifact is None
        assert lines[4] == ""
        assert (
            "\n".join(lines[5:]) + ("\n" if content.endswith("\n") else "") == body_text
        )


class TestCliErrors:
    def test_missing_required_flag_exits_2(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(WRITER_CLI),
                "--slug",
                "x",
                "--status",
                "ok",
                "--phase",
                "age",
                "--next",
                "age",
                "--artifact",
                "",
                "--root",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "orientation" in result.stderr.lower()

    def test_missing_phase_flag_exits_2(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(WRITER_CLI),
                "--slug",
                "x",
                "--status",
                "ok",
                "--next",
                "age",
                "--artifact",
                "",
                "--orientation",
                "demo",
                "--root",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "phase" in result.stderr.lower()

    def test_missing_body_file_exits_2(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(WRITER_CLI),
                "--slug",
                "x",
                "--status",
                "ok",
                "--phase",
                "age",
                "--next",
                "age",
                "--artifact",
                "",
                "--orientation",
                "demo",
                "--body-file",
                str(tmp_path / "nope.md"),
                "--root",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "body-file" in result.stderr.lower()


class TestPathDerivation:
    def test_path_is_under_root_dot_cheese_phase(
        self, writer: _WriterModule, tmp_path: Path
    ) -> None:
        target = writer.write_artifact(
            slug="curd-7",
            status="ok",
            phase="age",
            next_skill="done",
            artifact="",
            orientation="curd 7 done",
            body=None,
            grounded=("context.md#1-1",),
            root=tmp_path,
        )
        assert target == tmp_path / ".cheese" / "age" / "curd-7.md"
        assert target.is_file()


class TestPhaseFlag:
    """`--phase` names this phase's own directory; `--next` stays as preamble-only."""

    def test_phase_overrides_next_for_on_disk_path(
        self, writer: _WriterModule, tmp_path: Path
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
            grounded=("context.md#1-1",),
            phase="press",
        )
        assert target == tmp_path / ".cheese" / "press" / "my-task.md"
        assert not (tmp_path / ".cheese" / "age" / "my-task.md").exists()

    def test_phase_cli_flag_lands_artifact_under_phase_dir(
        self,
        handoff_mod: _HandoffModule,
        tmp_path: Path,
    ) -> None:
        # Subprocess: --phase age --next cure means the file lives at
        # .cheese/age/<slug>.md and the preamble names cure as next.
        result = subprocess.run(
            [
                sys.executable,
                str(WRITER_CLI),
                "--slug",
                "phase-flag",
                "--status",
                "ok",
                "--phase",
                "age",
                "--next",
                "cure",
                "--artifact",
                ".cheese/press/phase-flag.md",
                "--orientation",
                "age reviewed press output",
                "--root",
                str(tmp_path),
                "--grounded",
                "context.md#1-1",
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

    def test_phase_is_required_for_direct_call(
        self, writer: _WriterModule, tmp_path: Path
    ) -> None:
        with pytest.raises(writer.cli.CliError, match="--phase must be non-empty"):
            _ = writer.write_artifact(
                slug="legacy",
                status="ok",
                next_skill="done",
                artifact="",
                orientation="phase is required",
                body=None,
                root=tmp_path,
                phase="",
            )


class TestAtomicRename:
    def test_no_partial_file_when_rename_fails(
        self,
        writer: _WriterModule,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Force the atomic move to fail; it must surface as a CliError (exit 2)
        # naming the target path, not a raw traceback, and must not leak a .tmp file.
        def boom(_src: str, _dst: str) -> None:
            raise OSError("simulated rename failure")

        monkeypatch.setattr(os, "replace", boom)

        target_dir = tmp_path / ".cheese" / "age"
        target = target_dir / "never.md"
        with pytest.raises(writer.cli.CliError) as excinfo:
            _ = writer.write_artifact(
                slug="never",
                status="ok",
                grounded=("context.md#1-1",),
                phase="age",
                next_skill="done",
                artifact="",
                orientation="will not land",
                body=None,
                root=tmp_path,
            )

        assert excinfo.value.exit_code == 2
        assert str(target) in str(excinfo.value)
        assert not target.exists()
        leftovers = list(target_dir.glob("*.tmp")) if target_dir.exists() else []
        assert leftovers == [], f"tmp file leaked: {leftovers}"

    def test_cli_replace_failure_exits_2(self, tmp_path: Path) -> None:
        # End-to-end: a write that fails after the tmp file lands must exit 2
        # (I/O), not 3 (contract) and not an unhandled traceback (1).
        target_dir = tmp_path / ".cheese" / "age"
        target_dir.mkdir(parents=True)
        target_dir.chmod(0o500)  # read+execute only: os.replace into it fails
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(WRITER_CLI),
                    "--slug",
                    "locked",
                    "--status",
                    "ok",
                    "--phase",
                    "age",
                    "--next",
                    "done",
                    "--artifact",
                    "",
                    "--orientation",
                    "demo",
                    "--root",
                    str(tmp_path),
                    "--grounded",
                    "context.md#1-1",
                ],
                capture_output=True,
                text=True,
            )
        finally:
            target_dir.chmod(0o700)
        assert result.returncode == 2, result.stderr
        assert str(target_dir / "locked.md") in result.stderr
        leftovers = list(target_dir.glob("*.tmp"))
        assert leftovers == [], f"tmp file leaked: {leftovers}"


class TestContractErrorContext:
    """A rejected `--status` (or any render-time contract violation) exits 3
    and names the `--phase`/`--slug` dispatch it came from."""

    def test_bad_status_exits_3_with_phase_and_slug_context(
        self, tmp_path: Path
    ) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(WRITER_CLI),
                "--slug",
                "my-task",
                "--status",
                "bogus-status",
                "--phase",
                "press",
                "--next",
                "age",
                "--artifact",
                "",
                "--orientation",
                "demo",
                "--root",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 3, result.stderr
        assert "--phase press" in result.stderr
        assert "--slug my-task" in result.stderr

    def test_render_time_newline_in_artifact_exits_3_before_cheese_dir_created(
        self, tmp_path: Path
    ) -> None:
        # `artifact` is only validated when render_handoff_slug renders the
        # preamble, which happens before the .cheese/<phase> directory or the
        # tmp file are created.
        result = subprocess.run(
            [
                sys.executable,
                str(WRITER_CLI),
                "--slug",
                "hurt",
                "--status",
                "ok",
                "--phase",
                "press",
                "--next",
                "age",
                "--artifact",
                "line1\nline2",
                "--orientation",
                "demo",
                "--root",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 3, result.stderr
        assert "--phase press" in result.stderr
        assert "--slug hurt" in result.stderr
        assert not (tmp_path / ".cheese").exists()

    def test_illegal_transition_exits_3_with_phase_and_slug_context(
        self, tmp_path: Path
    ) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(WRITER_CLI),
                "--slug",
                "hop",
                "--status",
                "ok",
                "--phase",
                "cook",
                "--next",
                "plate",
                "--artifact",
                "",
                "--orientation",
                "demo",
                "--root",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 3, result.stderr
        assert "--phase cook" in result.stderr
        assert "--slug hop" in result.stderr
        assert not (tmp_path / ".cheese").exists()


class TestGroundedValidation:
    @pytest.mark.parametrize(
        ("entry", "message"),
        [
            ("missing.md#1-1", "path not found"),
            ("context.md#1", "path not found"),
            ("", "path\\[#start-end\\]"),
            ("context.md#2-1", "range must ascend"),
            ("/etc/passwd#1-1", "must be under root"),
            ("../outside.md#1-1", "escapes the repository root"),
        ],
    )
    def test_invalid_grounded_entry_rejected_before_write(
        self,
        writer: _WriterModule,
        tmp_path: Path,
        entry: str,
        message: str,
    ) -> None:
        with pytest.raises(writer.cli.CliError, match=message):
            _ = writer.write_artifact(
                slug="invalid-grounded",
                status="ok",
                phase="cook",
                next_skill="press",
                artifact="",
                orientation="demo",
                body=None,
                root=tmp_path,
                grounded=(entry,),
            )
        assert not (tmp_path / ".cheese").exists()

    def test_grounded_cap_rejected_before_write(
        self, writer: _WriterModule, tmp_path: Path
    ) -> None:
        entries = tuple("context.md#1-1" for _ in range(17))
        with pytest.raises(writer.cli.CliError, match="at most 16"):
            _ = writer.write_artifact(
                slug="over-cap",
                status="ok",
                phase="cook",
                next_skill="press",
                artifact="",
                orientation="demo",
                body=None,
                root=tmp_path,
                grounded=entries,
            )
        assert not (tmp_path / ".cheese").exists()

    def test_grounded_symlink_escape_rejected(
        self,
        writer: _WriterModule,
        tmp_path: Path,
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:
        outside_dir = tmp_path_factory.mktemp("outside")
        outside = outside_dir / "secret.md"
        _ = outside.write_text("secret\n", encoding="utf-8")
        link = tmp_path / "linked.md"
        link.symlink_to(outside)
        with pytest.raises(writer.cli.CliError, match="escapes the repository root"):
            _ = writer.write_artifact(
                slug="symlink-escape",
                status="ok",
                phase="cook",
                next_skill="press",
                artifact="",
                orientation="demo",
                body=None,
                root=tmp_path,
                grounded=("linked.md#1-1",),
            )
        assert not (tmp_path / ".cheese").exists()


class TestWheypointCommitFailure:
    def test_commit_failure_keeps_written_artifact(
        self,
        writer: _WriterModule,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The artifact lands before the commit, and the next resolve gates on it."""
        target = writer.write_artifact(
            slug="commit-failed",
            status="ok",
            phase="cook",
            next_skill="press",
            artifact="",
            orientation="first pass",
            body=None,
            root=tmp_path,
            grounded=("context.md#1-1",),
        )
        _ = capsys.readouterr()

        def fail(*_args: object, **_kwargs: object) -> commit_module.CommitResult:
            raise commit_module.CommitError("corpus unavailable")

        monkeypatch.setattr(commit_module, "commit", fail)
        with pytest.raises(writer.cli.CliError) as excinfo:
            _ = writer.write_artifact(
                slug="commit-failed",
                status="ok",
                phase="cook",
                next_skill="press",
                artifact="",
                orientation="second pass",
                body=None,
                root=tmp_path,
                grounded=("context.md#1-1",),
            )
        assert target.is_file()
        assert "second pass" in target.read_text(encoding="utf-8")
        assert excinfo.value.exit_code == 5
        assert f"wheypoint: artifact-orphaned {target}" in capsys.readouterr().err

        resolution = resolve_module.resolve("commit-failed", workspace_root=tmp_path)
        assert resolution.outcome is resolve_module.ResolutionOutcome.GATED
        assert lint_module.LintCode.STALE_ARTIFACT_LINK in [
            finding.code for finding in resolution.findings
        ]

    def test_read_only_corpus_orphans_the_artifact_through_the_real_kernel(
        self,
        writer: _WriterModule,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            pytest.skip("root ignores directory permissions")
        corpus_root = tmp_path / "ro-corpus"
        work_dir = corpus_root / "work" / "read-only"
        work_dir.mkdir(parents=True)
        work_dir.chmod(0o500)
        try:
            with pytest.raises(writer.cli.CliError) as excinfo:
                _ = writer.write_artifact(
                    slug="read-only",
                    status="ok",
                    phase="cook",
                    next_skill="press",
                    artifact="",
                    orientation="demo",
                    body=None,
                    root=tmp_path,
                    grounded=("context.md#1-1",),
                    corpus_root=corpus_root,
                )
        finally:
            work_dir.chmod(0o700)
        target = tmp_path / ".cheese" / "cook" / "read-only.md"
        assert target.is_file()
        assert excinfo.value.exit_code == 5
        assert f"wheypoint: artifact-orphaned {target}" in capsys.readouterr().err

    def test_commit_failure_prints_traceback_for_unclassified_exception(
        self,
        writer: _WriterModule,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def fail(*_args: object, **_kwargs: object) -> commit_module.CommitResult:
            raise KeyError("missing")

        monkeypatch.setattr(commit_module, "commit", fail)
        with pytest.raises(writer.cli.CliError) as excinfo:
            _ = writer.write_artifact(
                slug="commit-failed-keyerror",
                status="ok",
                phase="cook",
                next_skill="press",
                artifact="",
                orientation="demo",
                body=None,
                root=tmp_path,
                grounded=("context.md#1-1",),
            )
        assert "KeyError" in str(excinfo.value)
        assert excinfo.value.exit_code == 5
        assert "Traceback" in capsys.readouterr().err

    def test_missing_grounded_on_genesis_is_caller_usage_without_a_traceback(
        self,
        writer: _WriterModule,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with pytest.raises(writer.cli.CliError, match="at least one --grounded") as e:
            _ = writer.write_artifact(
                slug="ungrounded",
                status="ok",
                phase="cook",
                next_skill="press",
                artifact="",
                orientation="demo",
                body=None,
                root=tmp_path,
            )
        assert e.value.exit_code == 2
        assert "Traceback" not in capsys.readouterr().err
        assert not (tmp_path / ".cheese").exists()


class TestSuccessTelemetry:
    def test_success_reports_the_landed_revision(
        self,
        writer: _WriterModule,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _ = writer.write_artifact(
            slug="reported",
            status="ok",
            phase="cook",
            next_skill="press",
            artifact="",
            orientation="demo",
            body=None,
            root=tmp_path,
            grounded=("context.md#1-1",),
        )
        record = wheypoint_storage.WorkStore.open("reported").read_record()
        assert record is not None
        assert (
            f"wheypoint: revision work_id=reported "
            f"revision_id={record.revision_id} revision_number=1 retried=false"
        ) in capsys.readouterr().err


class TestSessionProvenanceFromEnvironment:
    def test_valid_session_environment_lands_in_the_record(
        self, writer: _WriterModule, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EASY_CHEESE_SESSION_ID", "sess-01")
        monkeypatch.setenv("EASY_CHEESE_CAPTURED_AT", "2026-01-02T03:04:05Z")
        _ = writer.write_artifact(
            slug="env-valid",
            status="ok",
            phase="cook",
            next_skill="press",
            artifact="",
            orientation="demo",
            body=None,
            root=tmp_path,
            grounded=("context.md#1-1",),
        )
        record = wheypoint_storage.WorkStore.open("env-valid").read_record()
        assert record is not None
        assert record.created == "2026-01-02T03:04:05Z"

    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("EASY_CHEESE_SESSION_ID", "Session One"),
            ("CHEESE_CAPTURED_AT", "yesterday"),
        ],
    )
    def test_unparseable_session_environment_is_dropped_not_fatal(
        self,
        writer: _WriterModule,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        name: str,
        value: str,
    ) -> None:
        monkeypatch.setenv(name, value)
        target = writer.write_artifact(
            slug="env-invalid",
            status="ok",
            phase="cook",
            next_skill="press",
            artifact="",
            orientation="demo",
            body=None,
            root=tmp_path,
            grounded=("context.md#1-1",),
        )
        assert target.is_file()
        record = wheypoint_storage.WorkStore.open("env-invalid").read_record()
        assert record is not None
        assert record.created != value
        assert f"wheypoint: ignoring {name}" in capsys.readouterr().err


class TestRepoRootAnchoring:
    def test_write_from_a_subdirectory_lands_at_the_git_toplevel(
        self, writer: _WriterModule, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for args in (("init",), ("config", "user.email", "t@example.com")):
            _ = subprocess.run(
                ["git", *args], cwd=tmp_path, check=True, capture_output=True
            )
        subdir = tmp_path / "nested" / "deeper"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)

        status = writer.main(
            [
                "--slug",
                "anchored",
                "--status",
                "ok",
                "--phase",
                "cook",
                "--next",
                "press",
                "--artifact",
                "",
                "--orientation",
                "demo",
                "--grounded",
                "context.md#1-1",
            ]
        )
        assert status == 0
        assert (tmp_path / ".cheese" / "cook" / "anchored.md").is_file()
        assert not (subdir / ".cheese").exists()
        record = wheypoint_storage.WorkStore.open("anchored").read_record()
        assert record is not None
        assert [link.path for link in record.artifact_links] == [
            ".cheese/cook/anchored.md"
        ]


class TestSiblingArtifactLinks:
    def test_a_phase_commit_does_not_repin_a_sibling_artifact(
        self, writer: _WriterModule, tmp_path: Path
    ) -> None:
        def write(phase: str, next_skill: str, orientation: str) -> Path:
            return writer.write_artifact(
                slug="siblings",
                status="ok",
                phase=phase,
                next_skill=next_skill,
                artifact="",
                orientation=orientation,
                body=None,
                root=tmp_path,
                grounded=("context.md#1-1",),
            )

        cook_target = write("cook", "press", "cook pass")
        _ = write("press", "age", "press pass")
        store = wheypoint_storage.WorkStore.open("siblings")
        after_press = store.read_record()
        assert after_press is not None
        pinned = {link.path: link.digest for link in after_press.artifact_links}
        assert sorted(pinned) == [
            ".cheese/cook/siblings.md",
            ".cheese/press/siblings.md",
        ]

        _ = cook_target.write_text("edited after cook committed\n", encoding="utf-8")
        _ = write("press", "age", "press second pass")
        after_second = store.read_record()
        assert after_second is not None
        repinned = {link.path: link.digest for link in after_second.artifact_links}
        assert (
            repinned[".cheese/cook/siblings.md"] == pinned[".cheese/cook/siblings.md"]
        )
        assert (
            repinned[".cheese/press/siblings.md"] != pinned[".cheese/press/siblings.md"]
        )


class TestWheypointConflictRetry:
    def test_retry_rebinds_base_and_drops_genesis_notes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from easy_cheese.shared.wheypoint import phase_commit

        target = tmp_path / ".cheese" / "cook" / "seam.md"
        target.parent.mkdir(parents=True)
        _ = target.write_text("phase\n", encoding="utf-8")

        store = wheypoint_storage.WorkStore.open("seam")
        real_commit = commit_module.commit
        calls = {"n": 0}

        def commit_with_concurrent_landing(
            delta: WheypointDelta,
            *,
            store: wheypoint_storage.WorkStore,
            artifact_root: Path | str | None = None,
        ) -> commit_module.CommitResult:
            calls["n"] += 1
            if calls["n"] == 1:
                concurrent_delta = checkpoint.build_delta(
                    CheckpointIntent(
                        work_id="seam",
                        orientation="concurrent handoff",
                        working_context=["context.md#1-1"],
                        notes="concurrent handoff",
                        next=NextMove("press"),
                        artifact="seam.md",
                    ),
                    None,
                )
                _ = real_commit(
                    concurrent_delta, store=store, artifact_root=artifact_root
                )
            return real_commit(delta, store=store, artifact_root=artifact_root)

        monkeypatch.setattr(commit_module, "commit", commit_with_concurrent_landing)

        outcome = phase_commit.commit_phase_revision(
            work_id="seam",
            phase="cook",
            next_skill="press",
            artifact=str(target),
            orientation="demo",
            grounded=("context.md#1-1",),
            root=tmp_path,
            store=store,
            write_contents=lambda: None,
        )
        current = store.read_record()
        assert current is not None
        assert outcome.retried is True
        assert outcome.result.record.revision_id == current.revision_id
        assert outcome.result.revision.parent_revision_id is not None
        assert outcome.result.record.working_context == ["context.md#1-1"]
        assert [link.path for link in outcome.result.record.artifact_links] == [
            ".cheese/cook/seam.md"
        ]
        err = capsys.readouterr().err
        assert "wheypoint: retry work_id=seam phase=cook stale_parent=genesis" in err
        assert (
            f"wheypoint: retry outcome=committed work_id=seam phase=cook "
            f"revision_id={outcome.result.revision.revision_id}"
        ) in err

    def test_retry_refuses_an_ungrounded_genesis_retry(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A record that vanished under the retry must not commit a bare genesis."""
        from easy_cheese.shared.wheypoint import phase_commit

        target = tmp_path / ".cheese" / "cook" / "vanished.md"
        target.parent.mkdir(parents=True)
        _ = target.write_text("phase\n", encoding="utf-8")

        store = wheypoint_storage.WorkStore.open("vanished")
        genesis_delta = checkpoint.build_delta(
            CheckpointIntent(
                work_id="vanished",
                orientation="genesis handoff",
                notes="genesis handoff",
                next=NextMove("press"),
                artifact="vanished.md",
                working_context=["context.md#1-1"],
            ),
            None,
        )
        _ = commit_module.commit(genesis_delta, store=store, artifact_root=tmp_path)
        seeded = store.read_record()
        assert seeded is not None

        reads = [seeded, None]

        def read_record(_self: wheypoint_storage.WorkStore) -> object:
            return reads.pop(0)

        def always_conflict(*_args: object, **_kwargs: object) -> None:
            raise commit_module.StaleParentError("race")

        monkeypatch.setattr(type(store), "read_record", read_record)
        monkeypatch.setattr(commit_module, "commit", always_conflict)

        with pytest.raises(
            commit_module.CommitError, match="at least one --grounded entry"
        ):
            _ = phase_commit.commit_phase_revision(
                work_id="vanished",
                phase="cook",
                next_skill="press",
                artifact=str(target),
                orientation="demo",
                grounded=(),
                root=tmp_path,
                store=store,
                write_contents=lambda: None,
            )

    def test_persistent_parent_conflict_stops_after_one_retry(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from easy_cheese.shared.wheypoint import phase_commit

        target = tmp_path / ".cheese" / "cook" / "seam.md"
        target.parent.mkdir(parents=True)
        _ = target.write_text("phase\n", encoding="utf-8")

        store = wheypoint_storage.WorkStore.open("seam")
        genesis_delta = checkpoint.build_delta(
            CheckpointIntent(
                work_id="seam",
                orientation="genesis handoff",
                notes="genesis handoff",
                next=NextMove("press"),
                artifact="seam.md",
                working_context=["context.md#1-1"],
            ),
            None,
        )
        _ = commit_module.commit(genesis_delta, store=store, artifact_root=tmp_path)

        commits: list[object] = []

        def always_conflict(*_args: object, **_kwargs: object) -> None:
            commits.append(object())
            raise commit_module.StaleParentError("race")

        monkeypatch.setattr(commit_module, "commit", always_conflict)

        with pytest.raises(commit_module.StaleParentError):
            _ = phase_commit.commit_phase_revision(
                work_id="seam",
                phase="cook",
                next_skill="press",
                artifact=str(target),
                orientation="demo",
                grounded=("context.md#1-1",),
                root=tmp_path,
                store=store,
                write_contents=lambda: None,
            )
        assert len(commits) == 2
        err = capsys.readouterr().err
        assert "wheypoint: retry work_id=seam phase=cook" in err
        assert "wheypoint: retry outcome=failed work_id=seam phase=cook" in err
