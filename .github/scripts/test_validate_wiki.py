#!/usr/bin/env python3
"""Golden-fixture tests for validate_wiki.py."""
from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import validate_wiki  # noqa: E402

WIKI = ".hallouminate/wiki"

ROOT_INDEX = """# Wiki index

<!-- HALLOUMINATE:INDEX-START -->
- [adr/](./adr/index.md) — adr
- [topic-one](./topic-one.md) — Topic one
<!-- HALLOUMINATE:INDEX-END -->
"""

ADR_INDEX = """# adr

<!-- HALLOUMINATE:INDEX-START -->
- [decision-001](./decision-001.md) — ADR: a decision
<!-- HALLOUMINATE:INDEX-END -->
"""


class ValidateWikiTest(unittest.TestCase):
    def setUp(self) -> None:
        self._cwd = Path.cwd()
        self.tmpdir = Path(tempfile.mkdtemp(prefix="validate-wiki-"))
        self.addCleanup(self._restore)
        os.chdir(self.tmpdir)

    def _restore(self) -> None:
        os.chdir(self._cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, rel: str, content: str) -> None:
        path = self.tmpdir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_bytes(self, rel: str, content: bytes) -> None:
        path = self.tmpdir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def _write_valid_wiki(self) -> None:
        self._write(f"{WIKI}/index.md", ROOT_INDEX)
        self._write(f"{WIKI}/topic-one.md", "# Topic one\n\nbody\n")
        self._write(f"{WIKI}/adr/index.md", ADR_INDEX)
        self._write(f"{WIKI}/adr/decision-001.md", "# ADR: a decision\n\nbody\n")

    def _run(self) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = validate_wiki.main()
        return rc, out.getvalue(), err.getvalue()

    def test_valid_wiki_passes(self) -> None:
        self._write_valid_wiki()
        rc, out, err = self._run()
        self.assertEqual(rc, 0, err)
        self.assertIn("validated 4 wiki page(s)", out)

    def test_wiki_dir_missing_fails_loud(self) -> None:
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn(f"ERROR: {WIKI}/ directory not found", err)

    def test_empty_wiki_dir_fails_loud(self) -> None:
        (self.tmpdir / WIKI).mkdir(parents=True)
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("ERROR: no wiki pages found", err)

    def test_missing_h1_fails(self) -> None:
        self._write_valid_wiki()
        self._write(f"{WIKI}/topic-one.md", "prose before the heading\n\n# Topic one\n")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("ERROR:", err)
        self.assertIn(f"{WIKI}/topic-one.md: first non-blank line is not a single '# ' H1", err)

    def test_h2_first_line_fails(self) -> None:
        self._write_valid_wiki()
        self._write(f"{WIKI}/topic-one.md", "## Topic one\n\nbody\n")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("not a single '# ' H1", err)

    def test_h1_without_space_fails(self) -> None:
        self._write_valid_wiki()
        self._write(f"{WIKI}/topic-one.md", "#Topic one\n\nbody\n")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("not a single '# ' H1", err)

    def test_bare_hash_heading_fails(self) -> None:
        self._write_valid_wiki()
        self._write(f"{WIKI}/topic-one.md", "# \n\nbody\n")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("not a single '# ' H1", err)

    def test_index_without_h1_fails(self) -> None:
        self._write_valid_wiki()
        self._write(f"{WIKI}/adr/index.md", ADR_INDEX.replace("# adr\n", "adr\n"))
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn(f"{WIKI}/adr/index.md: first non-blank line is not a single '# ' H1", err)

    def test_empty_page_fails(self) -> None:
        self._write_valid_wiki()
        self._write(f"{WIKI}/topic-one.md", "\n\n")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn(f"{WIKI}/topic-one.md: page is empty", err)

    def test_leading_blank_lines_before_h1_pass(self) -> None:
        self._write_valid_wiki()
        self._write(f"{WIKI}/topic-one.md", "\n\n# Topic one\n\nbody\n")
        rc, _, err = self._run()
        self.assertEqual(rc, 0, err)

    def test_non_kebab_stem_fails(self) -> None:
        self._write_valid_wiki()
        self._write(f"{WIKI}/Bad_Stem.md", "# Bad stem\n")
        self._write(
            f"{WIKI}/index.md",
            ROOT_INDEX.replace(
                "<!-- HALLOUMINATE:INDEX-END -->",
                "- [Bad_Stem](./Bad_Stem.md) — bad\n<!-- HALLOUMINATE:INDEX-END -->",
            ),
        )
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn(f"{WIKI}/Bad_Stem.md: file stem 'Bad_Stem' is not a kebab-case slug", err)

    def test_page_absent_from_index_fails(self) -> None:
        self._write_valid_wiki()
        self._write(f"{WIKI}/adr/decision-002.md", "# ADR: another decision\n")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn(
            f"{WIKI}/adr/decision-002.md: page is not listed in {WIKI}/adr/index.md", err
        )

    def test_index_entry_missing_file_fails(self) -> None:
        self._write_valid_wiki()
        self._write(
            f"{WIKI}/adr/index.md",
            ADR_INDEX.replace(
                "<!-- HALLOUMINATE:INDEX-END -->",
                "- [ghost](./ghost.md) — gone\n<!-- HALLOUMINATE:INDEX-END -->",
            ),
        )
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn(
            f"{WIKI}/adr/index.md: index entry './ghost.md' points at a missing file", err
        )

    def test_index_missing_markers_fails(self) -> None:
        self._write_valid_wiki()
        self._write(f"{WIKI}/adr/index.md", "# adr\n\n- [decision-001](./decision-001.md)\n")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn(f"{WIKI}/adr/index.md: missing HALLOUMINATE index markers", err)

    def test_markers_out_of_order_fails(self) -> None:
        self._write_valid_wiki()
        self._write(
            f"{WIKI}/adr/index.md",
            "# adr\n\n<!-- HALLOUMINATE:INDEX-END -->\n"
            "- [decision-001](./decision-001.md)\n<!-- HALLOUMINATE:INDEX-START -->\n",
        )
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("HALLOUMINATE index markers are out of order", err)

    def test_directory_without_index_fails(self) -> None:
        self._write_valid_wiki()
        self._write(f"{WIKI}/orphans/lost-page.md", "# Lost page\n")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn(f"{WIKI}/orphans: directory has wiki pages but no index.md", err)

    def test_subdir_index_entry_resolves_through_parent(self) -> None:
        # The root index's [adr/](./adr/index.md) entry must resolve; deleting
        # the subtree makes it dangle.
        self._write_valid_wiki()
        shutil.rmtree(self.tmpdir / WIKI / "adr")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn(
            f"{WIKI}/index.md: index entry './adr/index.md' points at a missing file", err
        )

    def test_dangling_entry_and_unlisted_page_both_reported(self) -> None:
        # A dangling entry must not mask the unlisted-page check for the same dir.
        self._write_valid_wiki()
        self._write(
            f"{WIKI}/adr/index.md",
            ADR_INDEX.replace(
                "<!-- HALLOUMINATE:INDEX-END -->",
                "- [ghost](./ghost.md) — gone\n<!-- HALLOUMINATE:INDEX-END -->",
            ),
        )
        self._write(f"{WIKI}/adr/decision-002.md", "# ADR: another decision\n")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("'./ghost.md' points at a missing file", err)
        self.assertIn("decision-002.md: page is not listed", err)

    def test_multiple_errors_all_reported(self) -> None:
        self._write_valid_wiki()
        self._write(f"{WIKI}/topic-one.md", "no heading\n")
        self._write(f"{WIKI}/adr/decision-002.md", "# ADR: another decision\n")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("not a single '# ' H1", err)
        self.assertIn("decision-002.md: page is not listed", err)
        self.assertIn("FAIL: 2 error(s)", err)

    def test_non_utf8_page_reported_as_error(self) -> None:
        # A non-UTF-8 page must join the ERROR: report, not traceback.
        self._write_valid_wiki()
        self._write_bytes(f"{WIKI}/topic-one.md", b"\xff\xfe# Topic one\n")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn(f"ERROR: {WIKI}/topic-one.md: page is not valid UTF-8", err)
        self.assertIn("FAIL: 1 error(s)", err)

    def test_non_utf8_index_reported_as_error(self) -> None:
        # A non-UTF-8 index must not traceback in the entry check either.
        self._write_valid_wiki()
        self._write_bytes(f"{WIKI}/adr/index.md", b"\xff\xfe# adr\n")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn(f"ERROR: {WIKI}/adr/index.md: page is not valid UTF-8", err)
        self.assertIn("cannot check index entries", err)


if __name__ == "__main__":
    unittest.main()
