#!/usr/bin/env python3
"""Unit tests for validate_skills.py."""
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

import validate_skills  # noqa: E402

VALID_BODY = """---
name: {name}
description: a test skill
license: MIT
---

body
"""


class ValidateSkillsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._cwd = Path.cwd()
        self.tmpdir = Path(tempfile.mkdtemp(prefix="validate-skills-"))
        self.addCleanup(self._restore)
        os.chdir(self.tmpdir)

    def _restore(self) -> None:
        os.chdir(self._cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, rel: str, content: str) -> None:
        path = self.tmpdir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_skill(self, name: str, parent: str = "skills") -> None:
        self._write(f"{parent}/{name}/SKILL.md", VALID_BODY.format(name=name))

    def _run(self) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = validate_skills.main()
        return rc, out.getvalue(), err.getvalue()

    def test_valid_skill_passes(self) -> None:
        self._write_skill("foo")
        rc, out, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("validated 1", out)

    def test_skills_dir_missing(self) -> None:
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("skills/ directory not found", err)

    def test_no_skill_files(self) -> None:
        (self.tmpdir / "skills").mkdir()
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("no SKILL.md files found", err)

    def test_stray_outside_skills_fails(self) -> None:
        # Cheese-flow guard: a copy-pasted plugin tree must fail validation.
        self._write_skill("foo")
        self._write_skill("bar", parent="plugins/cheese-flow/skills")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("plugins/cheese-flow/skills/bar/SKILL.md", err)
        self.assertIn("not at the documented path", err)

    def test_nested_subskill_fails(self) -> None:
        self._write("skills/foo/bar/SKILL.md", VALID_BODY.format(name="bar"))
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("nested sub-skills are not supported", err)

    def test_hidden_dirs_skipped(self) -> None:
        self._write_skill("foo")
        self._write(".github/SKILL.md", VALID_BODY.format(name="github"))
        self._write(".cache/plugins/x/skills/y/SKILL.md", VALID_BODY.format(name="y"))
        rc, out, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("validated 1", out)

    def test_missing_frontmatter(self) -> None:
        self._write("skills/foo/SKILL.md", "no frontmatter here\n")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("missing or malformed YAML frontmatter", err)

    def test_invalid_yaml(self) -> None:
        # Unterminated quoted string -> YAMLError.
        self._write(
            "skills/foo/SKILL.md",
            '---\nname: foo\ndescription: "unterminated\n---\n',
        )
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("invalid YAML frontmatter", err)

    def test_frontmatter_not_a_mapping(self) -> None:
        self._write(
            "skills/foo/SKILL.md",
            "---\n- just\n- a\n- list\n---\n",
        )
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("must be a YAML mapping", err)

    def test_name_dir_mismatch(self) -> None:
        self._write("skills/foo/SKILL.md", VALID_BODY.format(name="bar"))
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("does not match parent directory", err)

    def test_invalid_kebab_case(self) -> None:
        self._write("skills/Foo_Bar/SKILL.md", VALID_BODY.format(name="Foo_Bar"))
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("not kebab-case", err)

    def test_missing_description(self) -> None:
        self._write("skills/foo/SKILL.md", "---\nname: foo\n---\n\nbody\n")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("missing required key 'description'", err)

    def test_disallowed_keys(self) -> None:
        self._write(
            "skills/foo/SKILL.md",
            "---\nname: foo\ndescription: x\nbogus: 1\n---\n",
        )
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("disallowed frontmatter keys", err)
        self.assertIn("bogus", err)

    def test_allowed_optional_keys_pass(self) -> None:
        self._write(
            "skills/foo/SKILL.md",
            "---\nname: foo\ndescription: x\nlicense: MIT\nallowed-tools: Read,Write\n---\n",
        )
        rc, out, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("validated 1", out)


if __name__ == "__main__":
    unittest.main()
