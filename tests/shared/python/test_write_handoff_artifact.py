"""Tests for shared/scripts/write_handoff_artifact.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Protocol, TypedDict

import pytest

if TYPE_CHECKING:
    from easy_cheese.shared.cli import CliError
    from easy_cheese.shared.handoff import HandoffParseError, HandoffSlug

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SCRIPTS = REPO_ROOT / "src" / "easy_cheese" / "shared"
WRITER_CLI = SHARED_SCRIPTS / "write_handoff_artifact.py"


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
    ) -> Path: ...


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
                slug=bad_slug, status="ok", phase="age", next_skill="done",
                artifact="", orientation="x", body=None, root=tmp_path,
            )

    def test_traversal_phase_rejected(self, writer: _WriterModule, tmp_path: Path) -> None:
        with pytest.raises(writer.cli.CliError):
            _ = writer.write_artifact(
                slug="ok-slug", status="ok", next_skill="done", artifact="",
                orientation="x", body=None, root=tmp_path, phase="../etc",
            )


class TestRerunOverwrite:
    def test_rerun_same_slug_overwrites(self, writer: _WriterModule, tmp_path: Path) -> None:
        # os.replace (not os.rename) must overwrite an existing artifact cleanly
        # on a re-run — the cross-platform atomic-overwrite contract.
        common: _RerunKwargs = {
            "slug": "rerun", "status": "ok", "phase": "press",
            "next_skill": "age", "artifact": "",
            "body": None, "root": tmp_path,
        }
        target = writer.write_artifact(orientation="first pass", **common)
        rewritten = writer.write_artifact(orientation="second pass", **common)
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

    def test_render_parse_roundtrip_with_keyed_lines(self, handoff_mod: _HandoffModule) -> None:
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
        with pytest.raises(handoff_mod.HandoffParseError, match="duplicate 'durable_flags:'"):
            _ = handoff_mod.parse_handoff_slug(text)

    def test_keyed_line_without_value_fails_loud(self, handoff_mod: _HandoffModule) -> None:
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
                sys.executable, str(WRITER_CLI),
                "--slug", "cli-flagged", "--status", "ok", "--phase", "age",
                "--next", "cure", "--artifact", "", "--orientation", "demo",
                "--taste-test", "inline-pass", "--durable-flags", "none",
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
                sys.executable, str(WRITER_CLI),
                "--slug", "cli-baselined", "--status", "ok", "--phase", "age",
                "--next", "cure", "--artifact", "", "--orientation", "demo",
                "--baseline", "none",
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
                "--slug", "with-body",
                "--status", "ok",
                "--phase", "age",
                "--next", "cure",
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
        slug = handoff_mod.parse_handoff_slug(content)
        assert slug.orientation == "demo"
        assert slug.artifact is None
        assert lines[4] == ""
        assert "\n".join(lines[5:]) + ("\n" if content.endswith("\n") else "") == body_text


class TestCliErrors:
    def test_missing_required_flag_exits_2(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(WRITER_CLI),
                "--slug", "x",
                "--status", "ok",
                "--phase", "age",
                "--next", "age",
                "--artifact", "",
                "--root", str(tmp_path),
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
                "--slug", "x",
                "--status", "ok",
                "--next", "age",
                "--artifact", "",
                "--orientation", "demo",
                "--root", str(tmp_path),
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
                "--slug", "x",
                "--status", "ok",
                "--phase", "age",
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
        import os as _os

        def boom(_src: str, _dst: str) -> None:
            raise OSError("simulated rename failure")

        monkeypatch.setattr(_os, "replace", boom)

        target_dir = tmp_path / ".cheese" / "age"
        target = target_dir / "never.md"
        with pytest.raises(writer.cli.CliError) as excinfo:
            _ = writer.write_artifact(
                slug="never",
                status="ok",
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
                    sys.executable, str(WRITER_CLI),
                    "--slug", "locked", "--status", "ok", "--phase", "age",
                    "--next", "done", "--artifact", "", "--orientation", "demo",
                    "--root", str(tmp_path),
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

    def test_bad_status_exits_3_with_phase_and_slug_context(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [
                sys.executable, str(WRITER_CLI),
                "--slug", "my-task", "--status", "bogus-status", "--phase", "press",
                "--next", "age", "--artifact", "", "--orientation", "demo",
                "--root", str(tmp_path),
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
                sys.executable, str(WRITER_CLI),
                "--slug", "hurt", "--status", "ok", "--phase", "press",
                "--next", "age", "--artifact", "line1\nline2", "--orientation", "demo",
                "--root", str(tmp_path),
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
                sys.executable, str(WRITER_CLI),
                "--slug", "hop", "--status", "ok", "--phase", "cook",
                "--next", "plate", "--artifact", "", "--orientation", "demo",
                "--root", str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 3, result.stderr
        assert "--phase cook" in result.stderr
        assert "--slug hop" in result.stderr
        assert not (tmp_path / ".cheese").exists()
