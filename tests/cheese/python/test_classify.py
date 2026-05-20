"""Tests for skills/cheese/scripts/classify.py — deterministic dispatch table.

Loaded via importlib (no conftest) so the test stays self-contained under
the new tests/cheese/python/ directory.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CLASSIFY_PATH = REPO_ROOT / "skills" / "cheese" / "scripts" / "classify.py"


@pytest.fixture(scope="module")
def classify_mod() -> ModuleType:
    # classify.py inserts shared/scripts onto sys.path at import time, which
    # makes `import cli` resolve. Mirror the test_cli.py loader pattern.
    spec = importlib.util.spec_from_file_location("classify", CLASSIFY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["classify"] = module
    spec.loader.exec_module(module)
    return module


class TestCookIntent:
    def test_implement_verb(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("implement spec X")
        assert result["intent"] == "cook"
        assert result["target_skill"] == "cook"
        assert result["confidence"] in {"medium", "high"}
        assert "implement-verb" in result["signals"]

    def test_spec_path_is_high_confidence(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify(".cheese/specs/dark-mode.md")
        assert result["intent"] == "cook"
        assert result["confidence"] == "high"
        assert "spec-path" in result["signals"]

    def test_write_the_code(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("write the code for this feature")
        assert result["intent"] == "cook"
        assert result["target_skill"] == "cook"

    def test_make_it_work(self, classify_mod: ModuleType) -> None:
        # "make it work" is a cook signal even with no other markers.
        result = classify_mod.classify("make it work please")
        assert result["intent"] == "cook"


class TestAgeIntent:
    def test_review_this_pr(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("review this PR")
        assert result["intent"] == "age"
        assert result["target_skill"] == "age"
        assert "review-verb" in result["signals"]

    def test_pr_ref_with_number(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("PR#142")
        assert result["intent"] == "age"
        assert result["confidence"] == "high"
        assert "pr-ref" in result["signals"]

    def test_github_pr_url(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("https://github.com/foo/bar/pull/42")
        assert result["intent"] == "age"
        assert result["confidence"] == "high"

    def test_find_bugs(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("find bugs in src/auth.ts")
        assert result["intent"] == "age"

    def test_safe_to_merge(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("is this safe to merge?")
        assert result["intent"] == "age"


class TestMoldIntent:
    def test_lets_design(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("let's design a new feature")
        assert result["intent"] == "mold"
        assert result["target_skill"] == "mold"

    def test_shape_into_spec(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("shape this into a spec")
        assert result["intent"] == "mold"

    def test_design_verb_alone(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("designing the API")
        assert result["intent"] == "mold"


class TestMeltIntent:
    def test_conflict_marker(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("<<<<<<< HEAD\nfoo\n=======\nbar\n>>>>>>> branch")
        assert result["intent"] == "melt"
        assert result["target_skill"] == "melt"
        assert result["confidence"] == "high"

    def test_fix_the_merge(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("fix the merge conflicts")
        assert result["intent"] == "melt"

    def test_git_conflict_output(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("CONFLICT (content): Merge conflict in foo.py")
        assert result["intent"] == "melt"
        assert result["confidence"] == "high"


class TestDebugIntent:
    def test_stack_trace(self, classify_mod: ModuleType) -> None:
        text = "Traceback (most recent call last):\n  File 'foo.py', line 3\nTypeError: bad"
        result = classify_mod.classify(text)
        assert result["intent"] == "debug"
        assert result["target_skill"] == "pasteurize"

    def test_exception_line(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("got a ValueError: invalid input")
        assert result["intent"] == "debug"

    def test_js_style_stack_frame(self, classify_mod: ModuleType) -> None:
        # The stack-trace alternation should match `at fn(file.js):42` style too,
        # not just Python tracebacks. Otherwise JS errors silently misroute.
        result = classify_mod.classify("    at handler(server.js):42")
        assert result["intent"] == "debug"
        assert "stack-trace" in result["signals"]


class TestResearchIntent:
    def test_best_library(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("what's the best rate-limiter library for fastify")
        assert result["intent"] == "research"
        assert result["target_skill"] == "briesearch"


class TestRubberDuckIntent:
    def test_help_me_think(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("help me think through splitting this slice")
        assert result["intent"] == "rubber-duck"
        assert result["target_skill"] == "culture"

    def test_help_me_think_beats_design_noun(self, classify_mod: ModuleType) -> None:
        # "design" appears but the explicit `think through` verb wins per the
        # /cheese disambiguation rule: explicit conversational verb > noun mention.
        result = classify_mod.classify("help me think through this design tradeoff")
        assert result["intent"] == "rubber-duck"


class TestAgeThenCureIntent:
    def test_review_and_fix(self, classify_mod: ModuleType) -> None:
        # "review and fix" weight 3 beats plain "review" weight 2.
        result = classify_mod.classify("review and fix the findings")
        assert result["intent"] == "age-then-cure"
        assert result["target_skill"] == "age"


class TestUnknownFallback:
    def test_empty_string_is_unknown(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("")
        assert result["intent"] == "unknown"
        assert result["target_skill"] == "cheese"
        assert result["confidence"] == "low"

    def test_whitespace_only_is_unknown(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("   \n  ")
        assert result["intent"] == "unknown"
        assert result["target_skill"] == "cheese"

    def test_unrelated_text_is_unknown(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("hello world, this is unrelated text")
        assert result["intent"] == "unknown"
        assert result["target_skill"] == "cheese"
        assert result["confidence"] == "low"

    def test_single_weak_signal_downgrades_to_unknown(self, classify_mod: ModuleType) -> None:
        # `ship it` alone is weight-1 (low) — should fall back to unknown.
        result = classify_mod.classify("ship it")
        assert result["intent"] == "unknown"
        assert result["target_skill"] == "cheese"
        assert result["confidence"] == "low"


class TestDisambiguation:
    """Lock the /cheese disambiguation rules: explicit verb wins, strongest signal wins."""

    def test_fix_the_merge_beats_fix_this_bug(self, classify_mod: ModuleType) -> None:
        # Both `fix the merge` (melt, weight 2) and `fix this bug` (cook, weight 2)
        # could fire on this phrase; melt should win because the merge signal is more
        # specific to the failure mode. If this regresses, /cheese silently misroutes
        # conflict-resolution work to /cook.
        result = classify_mod.classify("fix the merge conflict in this bug")
        assert result["intent"] == "melt"
        assert result["target_skill"] == "melt"

    def test_review_and_fix_beats_plain_review(self, classify_mod: ModuleType) -> None:
        # `review and fix` (age-then-cure, weight 3) must outrank `review` alone
        # (age, weight 2). Otherwise the router skips the cure handoff.
        result = classify_mod.classify("please review and fix the bugs in src/auth.ts")
        assert result["intent"] == "age-then-cure"

    def test_spec_path_in_sentence(self, classify_mod: ModuleType) -> None:
        # Spec path embedded in prose — the regex must still anchor on the path.
        result = classify_mod.classify(
            "please work on .cheese/specs/skill-scripts.md when you can"
        )
        assert result["intent"] == "cook"
        assert "spec-path" in result["signals"]

    def test_score_floor_confidence_boundary(self, classify_mod: ModuleType) -> None:
        # Exactly one weight-2 signal: must yield `medium` (not `high`, not `low`).
        # Locks the _bucket_confidence boundary so refactors can't silently shift it.
        result = classify_mod.classify("review")
        assert result["intent"] == "age"
        assert result["confidence"] == "medium"


class TestOutputShape:
    def test_required_keys_present(self, classify_mod: ModuleType) -> None:
        result = classify_mod.classify("implement spec X")
        assert set(result.keys()) == {"intent", "confidence", "signals", "target_skill"}
        assert isinstance(result["signals"], list)
        assert isinstance(result["intent"], str)
        assert isinstance(result["confidence"], str)
        assert isinstance(result["target_skill"], str)

    def test_confidence_is_one_of_three_tiers(self, classify_mod: ModuleType) -> None:
        for text in ("implement spec X", "review this PR", "hello", ""):
            result = classify_mod.classify(text)
            assert result["confidence"] in {"low", "medium", "high"}


class TestCli:
    def test_implement_returns_cook_json(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CLASSIFY_PATH), "--input", "implement spec X", "--json"],
            capture_output=True, text=True, check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["intent"] == "cook"
        assert payload["target_skill"] == "cook"
        # Lock the CLI output shape — all 4 keys must always be present.
        assert set(payload.keys()) == {"intent", "confidence", "signals", "target_skill"}
        assert isinstance(payload["signals"], list)

    def test_review_returns_age_json(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CLASSIFY_PATH), "--input", "review this PR", "--json"],
            capture_output=True, text=True, check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["intent"] == "age"

    def test_design_returns_mold_json(self) -> None:
        # No --json: emit() still outputs JSON because the payload is a dict.
        result = subprocess.run(
            [sys.executable, str(CLASSIFY_PATH), "--input", "let's design a new feature"],
            capture_output=True, text=True, check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["intent"] == "mold"
        assert payload["target_skill"] == "mold"

    def test_unknown_input_returns_cheese(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CLASSIFY_PATH), "--input", "hello world", "--json"],
            capture_output=True, text=True, check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["target_skill"] == "cheese"
        assert payload["confidence"] == "low"

    def test_missing_input_exits_two(self) -> None:
        # argparse handles `required=True` and exits with status 2.
        result = subprocess.run(
            [sys.executable, str(CLASSIFY_PATH)],
            capture_output=True, text=True,
        )
        assert result.returncode == 2

    def test_help_flag_lists_input(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CLASSIFY_PATH), "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "--input" in result.stdout
