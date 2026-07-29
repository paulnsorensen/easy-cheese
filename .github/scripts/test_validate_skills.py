#!/usr/bin/env python3
"""Unit tests for validate_skills.py."""
from __future__ import annotations

import io
import json
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

    def _write_budgets(self, data: dict) -> None:
        self._write(".github/skill-budgets.json", json.dumps(data))

    def _skill_text(self, name: str, body_tokens: int) -> str:
        # FRONTMATTER_RE consumes the single \n right after the closing '---',
        # so the filler below is exactly the measured body.
        filler = "x" * (body_tokens * 4)
        return f"---\nname: {name}\ndescription: t\n---\n{filler}"

    def _run(self) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = validate_skills.main()
        return rc, out.getvalue(), err.getvalue()

    def _run_argv(self, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = validate_skills.main(argv)
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

    # --- .agents/skills/ repo-local skills ---

    def test_agents_skill_passes_and_is_counted(self) -> None:
        self._write_skill("foo")
        self._write_skill("bar", parent=".agents/skills")
        rc, out, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("validated 2", out)

    def test_agents_skill_name_dir_mismatch_fails(self) -> None:
        self._write_skill("foo")
        self._write(".agents/skills/bar/SKILL.md", VALID_BODY.format(name="baz"))
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("does not match parent directory", err)

    def test_agents_skill_over_target_fails(self) -> None:
        self._write_skill("foo")
        over = validate_skills.TARGET_TOKENS + 1
        self._write(".agents/skills/bar/SKILL.md", self._skill_text("bar", over))
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn(f"~{over} estimated tokens", err)
        self.assertIn(f"exceeds budget of {validate_skills.TARGET_TOKENS}", err)

    def test_agents_skill_too_deep_fails(self) -> None:
        self._write_skill("foo")
        self._write(".agents/skills/bar/baz/SKILL.md", VALID_BODY.format(name="baz"))
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("not at the documented path", err)
        self.assertIn("nested sub-skills are not supported", err)

    def test_agents_dir_outside_skills_still_skipped(self) -> None:
        self._write_skill("foo")
        self._write(".agents/bar/SKILL.md", VALID_BODY.format(name="bar"))
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

    def test_description_too_long_fails(self) -> None:
        long_desc = "x" * (validate_skills.DESCRIPTION_MAX_LEN + 1)
        self._write(
            "skills/foo/SKILL.md",
            f"---\nname: foo\ndescription: {long_desc}\n---\n",
        )
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("exceeds 1024-char limit", err)

    def test_description_at_limit_passes(self) -> None:
        desc = "x" * validate_skills.DESCRIPTION_MAX_LEN
        self._write(
            "skills/foo/SKILL.md",
            f"---\nname: foo\ndescription: {desc}\n---\n",
        )
        rc, out, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("validated 1", out)

    def test_allowed_optional_keys_pass(self) -> None:
        self._write(
            "skills/foo/SKILL.md",
            "---\nname: foo\ndescription: x\nlicense: MIT\nallowed-tools: Read,Write\n---\n",
        )
        rc, out, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("validated 1", out)

    # --- size ratchet ---

    def test_body_size_at_target_passes(self) -> None:
        self._write("skills/foo/SKILL.md", self._skill_text("foo", validate_skills.TARGET_TOKENS))
        rc, out, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("validated 1", out)

    def test_body_size_over_target_fails(self) -> None:
        over = validate_skills.TARGET_TOKENS + 1
        self._write("skills/foo/SKILL.md", self._skill_text("foo", over))
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn(f"~{over} estimated tokens", err)
        self.assertIn(f"exceeds budget of {validate_skills.TARGET_TOKENS}", err)

    def test_body_size_shrink_passes(self) -> None:
        self._write_budgets({"skills": {"foo": 6000}})
        self._write("skills/foo/SKILL.md", self._skill_text("foo", 5500))
        rc, out, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("validated 1", out)

    def test_body_size_grandfathered_at_recorded_value_passes(self) -> None:
        self._write_budgets({"skills": {"foo": 6000}})
        self._write("skills/foo/SKILL.md", self._skill_text("foo", 6000))
        rc, out, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("validated 1", out)

    def test_body_size_grandfathered_over_recorded_value_fails(self) -> None:
        self._write_budgets({"skills": {"foo": 6000}})
        self._write("skills/foo/SKILL.md", self._skill_text("foo", 6001))
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("~6001 estimated tokens", err)
        self.assertIn("exceeds budget of 6000", err)
        self.assertIn("grandfathered", err)

    def test_body_size_new_skill_over_target_fails(self) -> None:
        self._write_budgets({"skills": {"bar": 9000}})
        over = validate_skills.TARGET_TOKENS + 1
        self._write("skills/foo/SKILL.md", self._skill_text("foo", over))
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn(f"exceeds budget of {validate_skills.TARGET_TOKENS}", err)

    def test_body_size_recorded_at_target_stays_capped_at_target(self) -> None:
        self._write_budgets({"skills": {"foo": 2000}})
        over = validate_skills.TARGET_TOKENS + 1
        self._write("skills/foo/SKILL.md", self._skill_text("foo", over))
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn(f"exceeds budget of {validate_skills.TARGET_TOKENS}", err)

    # --- structural ratchet ---

    def test_cross_skill_reference_link_counts_as_linked(self) -> None:
        self._write_skill("a")
        self._write("skills/a/references/shared.md", "shared content\n")
        self._write_skill("b")
        self._write(
            "skills/b/SKILL.md",
            VALID_BODY.format(name="b") + "See [shared](../a/references/shared.md).\n",
        )
        rc, out, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("validated 2", out)

    def test_new_nested_reference_fails(self) -> None:
        self._write_skill("a")
        self._write(
            "skills/a/references/x.md",
            "See [y](../references/y.md) for detail.\n",
        )
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("skills/a/references/x.md", err)
        self.assertIn("references/", err)
        self.assertIn("keep references one level deep", err)

    def test_hidden_second_hop_fails(self) -> None:
        # skills/a/SKILL.md links x.md (reachable); x.md links b.md, which is
        # NOT linked from any SKILL.md. That is a genuine hidden hop: reading
        # only x.md misses b.md's content. Under the OLD any-references/-link
        # behaviour this fires for the same reason as test_new_nested_reference_fails
        # above; the point of this test is that it still fires under the
        # narrowed reachability-based check.
        self._write_skill("a")
        self._write(
            "skills/a/SKILL.md",
            VALID_BODY.format(name="a") + "See [x](references/x.md).\n",
        )
        self._write(
            "skills/a/references/x.md",
            "See [b](references/b.md) for detail.\n",
        )
        self._write("skills/a/references/b.md", "unreachable tail content\n")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("skills/a/references/x.md", err)
        self.assertIn("keep references one level deep", err)

    def test_lateral_reference_link_passes(self) -> None:
        # x.md links b.md, but b.md IS also linked directly from a SKILL.md
        # (a lateral citation, not a hidden hop) -- reading x.md alone never
        # hides content nobody else could find. Under the OLD any-references/-
        # link behaviour this would have failed; the narrowed check must not
        # flag it.
        self._write_skill("a")
        self._write(
            "skills/a/SKILL.md",
            VALID_BODY.format(name="a")
            + "See [x](references/x.md) and [b](references/b.md).\n",
        )
        self._write(
            "skills/a/references/x.md",
            "See [b](references/b.md) for detail.\n",
        )
        self._write("skills/a/references/b.md", "shared content\n")
        rc, out, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("validated 1", out)

    def test_allowlisted_nested_reference_passes(self) -> None:
        self._write_skill("a")
        self._write(
            "skills/a/references/x.md",
            "See [y](../references/y.md) for detail.\n",
        )
        self._write(
            "skills/a/SKILL.md",
            VALID_BODY.format(name="a") + "See [x](references/x.md).\n",
        )
        self._write_budgets(
            {"nested_references_allowlist": ["skills/a/references/x.md"]}
        )
        rc, out, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("validated 1", out)

    def test_new_orphan_reference_fails(self) -> None:
        self._write_skill("a")
        self._write("skills/a/references/orphan.md", "nobody links here\n")
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("skills/a/references/orphan.md", err)
        self.assertIn("orphaned reference file", err)

    def test_allowlisted_orphan_reference_passes(self) -> None:
        self._write_skill("a")
        self._write("skills/a/references/orphan.md", "nobody links here\n")
        self._write_budgets(
            {"orphaned_references_allowlist": ["skills/a/references/orphan.md"]}
        )
        rc, out, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("validated 1", out)

    # --- regen (just update-skill-budgets) ---

    def test_write_budgets_is_idempotent(self) -> None:
        self._write("skills/foo/SKILL.md", self._skill_text("foo", 6000))
        validate_skills.write_budgets()
        first = validate_skills.BUDGET_FILE.read_text(encoding="utf-8")
        validate_skills.write_budgets()
        second = validate_skills.BUDGET_FILE.read_text(encoding="utf-8")
        self.assertEqual(first, second)
        data = json.loads(first)
        self.assertEqual(data["skills"]["foo"], 6000)

    def test_write_budgets_clamps_growth_to_prior_recorded_value(self) -> None:
        self._write_budgets({"skills": {"foo": 3000}})
        self._write("skills/foo/SKILL.md", self._skill_text("foo", 6000))
        validate_skills.write_budgets()
        data = json.loads(validate_skills.BUDGET_FILE.read_text(encoding="utf-8"))
        self.assertEqual(data["skills"]["foo"], 3000)

    def test_write_budgets_still_shrinks(self) -> None:
        self._write_budgets({"skills": {"foo": 6000}})
        self._write("skills/foo/SKILL.md", self._skill_text("foo", 3000))
        validate_skills.write_budgets()
        data = json.loads(validate_skills.BUDGET_FILE.read_text(encoding="utf-8"))
        self.assertEqual(data["skills"]["foo"], 3000)

    # --- frontmatter reporting (goal + aggregate) ---

    def test_frontmatter_reporting_emits_on_pass_and_exits_0(self) -> None:
        self._write_skill("foo")
        rc, out, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("Frontmatter tokens", out)

    def test_frontmatter_reporting_absent_when_other_check_fails(self) -> None:
        self._write_skill("foo")
        self._write("skills/bar/SKILL.md", "---\nname: bar\nbogus: 1\n---\n")
        rc, out, err = self._run()
        self.assertEqual(rc, 1)
        self.assertNotIn("Frontmatter tokens", out)
        self.assertNotIn("Frontmatter tokens", err)

    # --- frontmatter extra-token cap ---
    def test_frontmatter_extra_over_cap_fails(self) -> None:
        filler = "y" * (validate_skills.FRONTMATTER_EXTRA_MAX * 4 + 40)
        self._write(
            "skills/foo/SKILL.md",
            f"---\nname: foo\ndescription: t\nmetadata:\n  x: {filler}\n---\n",
        )
        rc, _, err = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("non-description frontmatter", err)
        self.assertIn("metadata", err)
        self.assertIn(f"{validate_skills.FRONTMATTER_EXTRA_MAX}-token cap", err)

    # --- body-size goal report ---
    def test_body_size_goal_report_shows_over_goal_row(self) -> None:
        excess = 100
        self._write(
            "skills/foo/SKILL.md",
            self._skill_text("foo", validate_skills.GOAL_TOKENS + excess),
        )
        rc, out, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("Body-size goal", out)
        self.assertIn(f"skills/foo/SKILL.md: +{excess} over goal", out)

    # --- shipped/repo-local split ---
    def test_frontmatter_reporting_shipped_local_split_counts(self) -> None:
        self._write_skill("foo")
        self._write_skill("bar", parent=".agents/skills")
        rc, out, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("(1 shipped + 1 repo-local under .agents/skills/)", out)

    # --- --checks family selection ---

    def test_checks_frontmatter_skips_size_violation(self) -> None:
        over = validate_skills.TARGET_TOKENS + 1
        self._write("skills/foo/SKILL.md", self._skill_text("foo", over))
        rc, _, _ = self._run_argv(["--checks", "frontmatter"])
        self.assertEqual(rc, 0)

    def test_no_checks_flag_still_catches_size_violation(self) -> None:
        over = validate_skills.TARGET_TOKENS + 1
        self._write("skills/foo/SKILL.md", self._skill_text("foo", over))
        rc, _, err = self._run_argv([])
        self.assertEqual(rc, 1)
        self.assertIn("exceeds budget", err)

    def test_checks_frontmatter_still_catches_frontmatter_violation(self) -> None:
        filler = "y" * (validate_skills.FRONTMATTER_EXTRA_MAX * 4 + 40)
        self._write(
            "skills/foo/SKILL.md",
            f"---\nname: foo\ndescription: t\nmetadata:\n  x: {filler}\n---\n",
        )
        rc, _, err = self._run_argv(["--checks", "frontmatter"])
        self.assertEqual(rc, 1)
        self.assertIn("non-description frontmatter", err)

    def test_checks_structure_ignores_size_violation(self) -> None:
        over = validate_skills.TARGET_TOKENS + 1
        self._write("skills/foo/SKILL.md", self._skill_text("foo", over))
        rc, _, _ = self._run_argv(["--checks", "structure"])
        self.assertEqual(rc, 0)

    def test_checks_size_ignores_structure_violation(self) -> None:
        self._write_skill("a")
        self._write("skills/a/references/orphan.md", "nobody links here\n")
        rc, _, _ = self._run_argv(["--checks", "size"])
        self.assertEqual(rc, 0)

    def test_narrowed_run_omits_report_blocks(self) -> None:
        self._write_skill("foo")
        rc, out, _ = self._run_argv(["--checks", "frontmatter"])
        self.assertEqual(rc, 0)
        self.assertIn("OK: validated 1 SKILL.md file(s)", out)
        self.assertNotIn("Frontmatter tokens", out)
        self.assertNotIn("Body-size goal", out)

    def test_full_run_still_emits_report_blocks(self) -> None:
        self._write_skill("foo")
        rc, out, _ = self._run_argv([])
        self.assertEqual(rc, 0)
        self.assertIn("Frontmatter tokens", out)
        self.assertIn("Body-size goal", out)

    def test_checks_bogus_family_is_argparse_error(self) -> None:
        self._write_skill("foo")
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                validate_skills.main(["--checks", "bogus"])
        self.assertEqual(cm.exception.code, 2)

    def test_write_budgets_flag_via_argv(self) -> None:
        self._write("skills/foo/SKILL.md", self._skill_text("foo", 6000))
        rc, out, _ = self._run_argv(["--write-budgets"])
        self.assertEqual(rc, 0)
        self.assertIn("OK: wrote", out)


if __name__ == "__main__":
    unittest.main()
