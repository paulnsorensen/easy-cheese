"""The Age -> Cure handoff contract must survive as a typed ReviewResult.

/age no longer publishes a Markdown finding syntax that /cure re-parses. It
publishes a canonical ReviewResult behind a HandoffPointer (`age.pyz
publish-review`), and /cure consumes that payload and its `finding_ids`. These
tests bind the published prose to the new contract, and bind the writer command
to the handoff fields that /cheese, /cook, and /cure expect back.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILL = (ROOT / "skills" / "age" / "SKILL.md").read_text(encoding="utf-8")
# The auto-mode rules live in the handoff reference; the corpus is what a
# reviewer actually reads.
CORPUS = SKILL + "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted((ROOT / "skills" / "age" / "references").glob("*.md"))
)


def test_age_publishes_a_typed_review_result_not_a_markdown_sidecar() -> None:
    """The clean break: age publishes a ReviewResult; /cure never re-parses Markdown."""
    # The new contract is present.
    assert "publish-review" in CORPUS
    assert "ReviewResult" in CORPUS
    assert "coverage row" in CORPUS
    assert "finding_ids" in CORPUS
    # The deleted Markdown-parse contract is gone.
    assert "Do not add JSON sidecars" not in CORPUS
    assert "reads the markdown directly" not in CORPUS
    assert "invisible to `/cure`" not in CORPUS
    assert "parses this form with" not in CORPUS


def _writer_command() -> str:
    line = next(
        raw
        for raw in SKILL.splitlines()
        if "write-handoff-artifact" in raw and "--phase age" in raw
    )
    return line


def test_the_writer_command_forwards_upstream_artifact_and_baseline() -> None:
    """Dropping these fields loses the press/cook chain that `/cure` resumes."""
    command = _writer_command()

    assert '--artifact ""' not in command
    assert '--artifact "<artifact>"' in command
    assert "--baseline " in command
    assert '--body-file ".cheese/age/<slug>-body.md"' in command


def test_the_report_body_is_a_separate_file_from_the_final_report() -> None:
    """Two writers on one target left a prewritten report after a failed gate."""
    assert "Write the body only. Do not write the handoff preamble into that file." in SKILL
    assert "Do not write `.cheese/age/<slug>.md` yourself. The gated writer creates it." in SKILL


def test_age_holds_no_cure_pass_counter() -> None:
    """`/cook`'s fixed chain length owns the cap; Age has no counter input."""
    assert "Increment the cure-pass count" not in CORPUS
    assert "Age counts no cure passes and holds no pass state." in CORPUS


@pytest.mark.parametrize("form", ["/age [<ref-or-range>]", "/age <slug>"])  # noqa: V107
def test_both_input_forms_accept_the_hard_flag(form: str) -> None:
    line = next(raw for raw in SKILL.splitlines() if raw.startswith(form))
    assert "[--hard]" in line


def test_the_scoped_form_accepts_a_slug_and_repeated_scopes() -> None:
    line = next(
        raw for raw in SKILL.splitlines() if raw.startswith("/age [<ref-or-range>]")
    )
    assert "[--scope <path>]..." in line
    assert "[--slug <slug>]" in line
