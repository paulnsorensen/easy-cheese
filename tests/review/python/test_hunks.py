"""hunks_from_diff(): deletion hunks, line ends, and git's C-style quoted names."""

from __future__ import annotations

import pytest

from easy_cheese_review import hunks_from_diff


def test_a_deletion_hunk_covers_the_lines_on_each_side() -> None:
    diff = "--- a/x.py\n+++ b/x.py\n@@ -5,2 +4,0 @@\n-a\n-b\n"
    assert hunks_from_diff(diff) == {"x.py": [(4, 5)]}


def test_a_deletion_at_the_top_of_a_file_covers_line_one() -> None:
    diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +0,0 @@\n-a\n"
    assert hunks_from_diff(diff) == {"x.py": [(1, 1)]}


def test_a_quoted_name_with_raw_utf8_and_an_escape_decodes() -> None:
    """`core.quotePath=false`: git keeps UTF-8 raw and escapes only `"`, `\\`, and controls."""
    diff = '--- "a/é\\"x.py"\n+++ "b/é\\"x.py"\n@@ -1 +1 @@\n-a\n+b\n'
    assert hunks_from_diff(diff) == {'é"x.py': [(1, 1)]}


def test_a_quoted_name_with_octal_utf8_escapes_decodes() -> None:
    """`core.quotePath=true`: git writes each non-ASCII byte as an octal escape."""
    diff = '--- "a/\\303\\251\\tx.py"\n+++ "b/\\303\\251\\tx.py"\n@@ -1 +1 @@\n-a\n+b\n'
    assert hunks_from_diff(diff) == {"é\tx.py": [(1, 1)]}


@pytest.mark.parametrize(
    "separator", ["\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", " ", " ", "\r"]
)
def test_only_a_line_feed_ends_a_diff_line(separator: str) -> None:
    """A changed line that holds a `str.splitlines` boundary stays one body line."""
    diff = (
        "--- a/x.py\n+++ b/x.py\n"
        f"@@ -1 +1 @@\n-x = 0\n+x = 1{separator}+++ /dev/null\n"
        "@@ -5 +5 @@\n-print(x)\n+eval(x)\n"
    )
    assert hunks_from_diff(diff) == {"x.py": [(1, 1), (5, 5)]}
