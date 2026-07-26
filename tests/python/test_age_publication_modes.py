"""Contract tests for Age's explicit GitHub publication modes.

Age remains local-only by default.  The two opt-in modes must stay mutually
exclusive, idempotent, comment-only, and lossless for findings that GitHub
cannot anchor to a changed line.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGE = (REPO_ROOT / "skills" / "age" / "SKILL.md").read_text(encoding="utf-8")
PUBLICATION_PATH = REPO_ROOT / "skills" / "age" / "references" / "publication.md"


def test_age_advertises_both_publication_modes() -> None:
    assert "--post-report" in AGE
    assert "--post-inline" in AGE
    assert "`--post-report` and `--post-inline` are mutually exclusive" in AGE


def test_publication_reference_preserves_local_only_default() -> None:
    assert PUBLICATION_PATH.is_file()
    publication = PUBLICATION_PATH.read_text(encoding="utf-8")

    assert "The default remains local-only" in publication
    assert "existing pull request" in publication
    assert "write the canonical local report first" in publication.lower()
    assert "exact committed `base...head` diff" in publication
    assert "Exclude index and working-tree" in publication


def test_full_report_mode_is_one_idempotent_conversation_comment() -> None:
    publication = PUBLICATION_PATH.read_text(encoding="utf-8")

    assert "one top-level PR conversation comment" in publication
    assert "<!-- easy-cheese:age:report slug=<slug> -->" in publication
    assert "update the existing comment" in publication


def test_inline_mode_is_lossless_and_idempotent() -> None:
    publication = PUBLICATION_PATH.read_text(encoding="utf-8")

    assert "one inline thread per anchorable finding" in publication
    assert "<!-- easy-cheese:age:finding slug=<slug> key=<finding-key> -->" in publication
    assert "unanchorable findings" in publication
    assert "top-level summary comment" in publication
    assert "update the existing inline comment" in publication
    assert "Do not include line numbers, severity," in publication
    assert "semantically reconcile same-slug Age comments" in publication
    assert "Partition the canonical findings into anchorable and unanchorable" in publication
    assert "whose finding is now unanchorable" in publication
    assert "while preserving its marker" in publication
    assert "resolve the thread" in publication


def test_publication_never_changes_review_state_or_propagates() -> None:
    publication = PUBLICATION_PATH.read_text(encoding="utf-8")

    assert "COMMENT" in publication
    assert "never `APPROVE` or `REQUEST_CHANGES`" in publication
    assert "Do not propagate either publication flag" in publication
    assert all(target in publication for target in ("`/cure`", "`/plate`", "`/age --auto`"))
