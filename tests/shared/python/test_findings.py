"""Tests for shared/findings.py — severity-heading and bullet matchers."""

from __future__ import annotations

from types import ModuleType


def test_match_severity_heading_matches_severity_line(findings: ModuleType) -> None:
    assert findings.match_severity_heading("## Blocker") == "blocker"


def test_match_severity_heading_rejects_non_heading(findings: ModuleType) -> None:
    assert findings.match_severity_heading("not a heading") is None


def test_match_bullet_matches_bullet_line(findings: ModuleType) -> None:
    line = (
        "- **[encapsulation:blocker]** `src/users/index.ts:42` — "
        "`index` re-exports `SqlPgUser` across slice boundary."
    )
    match = findings.match_bullet(line)
    assert match is not None
    assert match.group("dim") == "encapsulation"
    assert match.group("sev") == "blocker"
    assert match.group("loc") == "src/users/index.ts:42"


def test_match_bullet_rejects_non_bullet(findings: ModuleType) -> None:
    assert findings.match_bullet("not a bullet") is None
