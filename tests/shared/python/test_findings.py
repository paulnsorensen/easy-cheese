"""Tests for shared/findings.py — severity-heading and bullet matchers."""

from __future__ import annotations

from easy_cheese.shared.findings import match_bullet, match_severity_heading


def test_match_severity_heading_matches_severity_line() -> None:
    assert match_severity_heading("## Blocker") == "blocker"


def test_match_severity_heading_rejects_non_heading() -> None:
    assert match_severity_heading("not a heading") is None


def test_match_bullet_matches_bullet_line() -> None:
    line = (
        "- **[encapsulation:blocker]** `src/users/index.ts:42` — "
        "`index` re-exports `SqlPgUser` across slice boundary."
    )
    match = match_bullet(line)
    assert match is not None
    assert match.group("dim") == "encapsulation"
    assert match.group("sev") == "blocker"
    assert match.group("loc") == "src/users/index.ts:42"


def test_match_bullet_rejects_non_bullet() -> None:
    assert match_bullet("not a bullet") is None
