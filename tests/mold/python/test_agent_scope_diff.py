"""Tests for skills/mold/scripts/agent_scope_diff.py — agent-introduced-noun diff.

Loaded via importlib (no conftest) so the test stays self-contained under the
new tests/mold/python/ directory.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import build_pyz  # noqa: E402

BUNDLE = build_pyz.cached_bundle("mold")


class TestDiffPure:
    """The acceptance criterion locked in the manifest."""

    def test_introduced_noun_surfaces(self, agent_scope_diff: ModuleType) -> None:
        # Acceptance: spec containing "tail", transcript with "tail" plus
        # "retry-loop", script emits ["retry-loop"].
        introduced = agent_scope_diff.diff("tail", "tail retry-loop")
        assert introduced == ["retry-loop"]

    def test_identical_sets_emit_empty(self, agent_scope_diff: ModuleType) -> None:
        # Acceptance: identical sets emit [].
        introduced = agent_scope_diff.diff("tail", "tail")
        assert introduced == []

    def test_spec_superset_of_transcript_emits_empty(self, agent_scope_diff: ModuleType) -> None:
        # The diff is directional: only words in transcript-not-in-spec count.
        introduced = agent_scope_diff.diff("tail retry-loop", "tail")
        assert introduced == []

    def test_multiple_introduced_words_sorted(self, agent_scope_diff: ModuleType) -> None:
        introduced = agent_scope_diff.diff("tail", "tail retry-loop sidecar zebra")
        assert introduced == ["retry-loop", "sidecar", "zebra"]

    def test_case_insensitive_match(self, agent_scope_diff: ModuleType) -> None:
        # `Retry-Loop` in transcript must match `retry-loop` in spec.
        introduced = agent_scope_diff.diff("retry-loop", "Retry-Loop")
        assert introduced == []

    def test_hyphenated_token_stays_one_word(self, agent_scope_diff: ModuleType) -> None:
        # The whole hyphenated identifier is one noun — splitting on `-` would
        # let "retry-loop" hide because "retry" and "loop" appear elsewhere.
        introduced = agent_scope_diff.diff("retry loop", "retry-loop")
        assert introduced == ["retry-loop"]

    def test_stopwords_ignored(self, agent_scope_diff: ModuleType) -> None:
        # Filler English words must not be flagged as agent-introduced — only
        # the scope-bearing nouns should surface in the diff.
        introduced = agent_scope_diff.diff("tail", "the tail is in there")
        assert introduced == []

    def test_pure_numeric_tokens_ignored(self, agent_scope_diff: ModuleType) -> None:
        # Numbers in headings (e.g. "step 1") are not scope-bearing nouns.
        introduced = agent_scope_diff.diff("tail", "tail 42 99")
        assert introduced == []

    def test_punctuation_does_not_leak_tokens(self, agent_scope_diff: ModuleType) -> None:
        # `tail.` should normalise to `tail`, not surface a phantom noun.
        introduced = agent_scope_diff.diff("tail", "tail.")
        assert introduced == []


class TestTokenize:
    """Lock the tokeniser so refactors cannot silently change scope semantics."""

    def test_drops_stopwords(self, agent_scope_diff: ModuleType) -> None:
        tokens = agent_scope_diff._tokens("the quick brown fox")
        assert "the" not in tokens
        assert "quick" in tokens
        assert "brown" in tokens

    def test_drops_pure_numerics(self, agent_scope_diff: ModuleType) -> None:
        tokens = agent_scope_diff._tokens("retry 3 times")
        assert "3" not in tokens
        assert "retry" in tokens

    def test_lowercases(self, agent_scope_diff: ModuleType) -> None:
        tokens = agent_scope_diff._tokens("Tail TAIL tail")
        assert tokens == {"tail"}

    def test_handles_markdown(self, agent_scope_diff: ModuleType) -> None:
        # Realistic spec body: headings, bullets, code fences. The tokeniser
        # must still extract the content words.
        body = "## Approach\n- Use a `retry-loop` for transient errors.\n"
        tokens = agent_scope_diff._tokens(body)
        assert "retry-loop" in tokens
        assert "approach" in tokens


class TestIOErrors:
    def test_missing_spec_exits_2(
        self, agent_scope_diff: ModuleType, tmp_path: Path
    ) -> None:
        # Acceptance: missing spec exits 2.
        transcript = tmp_path / "t.md"
        transcript.write_text("tail retry-loop")
        result = subprocess.run(
            [
                sys.executable,
                str(BUNDLE),
                "agent_scope_diff",
                "--spec",
                str(tmp_path / "does-not-exist.md"),
                "--transcript",
                str(transcript),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "spec" in result.stderr.lower()

    def test_missing_transcript_exits_2(
        self, agent_scope_diff: ModuleType, tmp_path: Path
    ) -> None:
        spec = tmp_path / "s.md"
        spec.write_text("tail")
        result = subprocess.run(
            [
                sys.executable,
                str(BUNDLE),
                "agent_scope_diff",
                "--spec",
                str(spec),
                "--transcript",
                str(tmp_path / "does-not-exist.md"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "transcript" in result.stderr.lower()

    def test_directory_passed_as_spec_exits_2(
        self, agent_scope_diff: ModuleType, tmp_path: Path
    ) -> None:
        # A directory exists but isn't readable as a spec body. Treat as error 2.
        transcript = tmp_path / "t.md"
        transcript.write_text("tail")
        result = subprocess.run(
            [
                sys.executable,
                str(BUNDLE),
                "agent_scope_diff",
                "--spec",
                str(tmp_path),
                "--transcript",
                str(transcript),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2


# ---------------------------------------------------------------------------
# CLI entrypoint tests via subprocess.
# ---------------------------------------------------------------------------


def _run_cli(
    spec_text: str, transcript_text: str, tmp_path: Path
) -> subprocess.CompletedProcess[str]:
    spec = tmp_path / "spec.md"
    transcript = tmp_path / "transcript.md"
    spec.write_text(spec_text)
    transcript.write_text(transcript_text)
    return subprocess.run(
        [
            sys.executable,
            str(BUNDLE),
            "agent_scope_diff",
            "--spec",
            str(spec),
            "--transcript",
            str(transcript),
        ],
        capture_output=True,
        text=True,
    )


class TestCli:
    def test_acceptance_case_returns_retry_loop(self, tmp_path: Path) -> None:
        # The locked acceptance criterion, exercised through the CLI.
        result = _run_cli("tail", "tail retry-loop", tmp_path)
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["agent_introduced"] == ["retry-loop"]
        assert payload["count"] == 1

    def test_identical_returns_empty(self, tmp_path: Path) -> None:
        result = _run_cli("tail", "tail", tmp_path)
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["agent_introduced"] == []
        assert payload["count"] == 0

    def test_output_shape_keys(self, tmp_path: Path) -> None:
        result = _run_cli("tail", "tail retry-loop", tmp_path)
        payload = json.loads(result.stdout)
        assert set(payload.keys()) == {"spec", "transcript", "agent_introduced", "count"}
        assert isinstance(payload["agent_introduced"], list)
        assert isinstance(payload["count"], int)

    def test_missing_spec_arg_exits_2(self) -> None:
        # argparse handles `required=True` and exits with status 2.
        result = subprocess.run(
            [sys.executable, str(BUNDLE), "agent_scope_diff"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2

    def test_help_lists_required_flags(self) -> None:
        result = subprocess.run(
            [sys.executable, str(BUNDLE), "agent_scope_diff", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--spec" in result.stdout
        assert "--transcript" in result.stdout
