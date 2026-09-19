"""Documentation checks for Cook and Pasteurize sizing."""

import re
from pathlib import Path

from easy_cheese.shared.fanout import pasteurize_route

ROOT = Path(__file__).resolve().parents[2]

COOK_SKILL = ROOT / "skills" / "cook" / "SKILL.md"
PASTEURIZE_SKILL = ROOT / "skills" / "pasteurize" / "SKILL.md"
ROUTING_POLICY = ROOT / "skills" / "cheese" / "references" / "routing-policy.md"

MODE_PY = ROOT / "src" / "easy_cheese" / "shared" / "fanout" / "mode.py"

COOK_FAN_PATHWAY_DOC = ROOT / "skills" / "cook" / "references" / "fan-pathway.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestCookModeSelection:
    def test_documents_select_mode_from_score(self) -> None:
        text = read(COOK_FAN_PATHWAY_DOC)
        assert "select_mode_from_score" in text

    def test_documents_both_linear_and_decompose_first(self) -> None:
        text = read(COOK_FAN_PATHWAY_DOC)
        assert '"linear"' in text
        assert "decompose-first" in text

    def test_states_it_never_returns_parallel(self) -> None:
        text = read(COOK_FAN_PATHWAY_DOC)
        assert re.search(r"never returns[^.]*parallel", text), (
            "cook/references/fan-pathway.md does not state select_mode_from_score never returns parallel"
        )


class TestPasteurizeFanoutSizing:
    def test_documents_size_pasteurize_fanout(self) -> None:
        text = read(PASTEURIZE_SKILL)
        assert "size_pasteurize_fanout" in text

    def test_documents_descending_score_over_suspect_range(self) -> None:
        text = read(PASTEURIZE_SKILL)
        assert "descending" in text
        assert "suspect range" in text

    def test_flags_constants_as_unvalidated(self) -> None:
        text = read(PASTEURIZE_SKILL)
        assert "reasoned" in text and "not measured" in text, (
            "pasteurize/SKILL.md does not flag its fan-out constants as "
            "unvalidated / reasoned-not-measured"
        )


class TestRoutingPolicyTable:
    def test_table_has_pasteurize_gate_row(self) -> None:
        text = read(ROUTING_POLICY)
        assert "pasteurize gate" in text
        assert "1/2" in text
        assert "heisenbug" in text
        assert "3-5" in text and "cold bug" in text


class TestThresholdCodeDocsAgreement:
    """cook/SKILL.md's stated decompose-first threshold must match the live
    DECOMPOSE_FIRST_THRESHOLD constant, or the doc has silently drifted from
    the code."""

    def test_cook_skill_mentions_the_live_threshold_constant(self) -> None:
        mode_text = read(MODE_PY)
        match = re.search(r"DECOMPOSE_FIRST_THRESHOLD\s*=\s*(\d+)", mode_text)
        assert match, "src/fanout/mode.py no longer defines DECOMPOSE_FIRST_THRESHOLD"
        threshold = match.group(1)

        cook_text = read(COOK_FAN_PATHWAY_DOC)
        assert threshold in cook_text, (
            f"cook/references/fan-pathway.md does not mention the live threshold {threshold}"
        )

    def test_pasteurize_skill_fanout_table_matches_live_constants(self) -> None:
        pasteurize_text = read(PASTEURIZE_SKILL)

        assert f"score < {pasteurize_route.WIDE_RANGE_THRESHOLD}" in pasteurize_text
        assert f"score > {pasteurize_route.WIDE_RANGE_THRESHOLD}" in pasteurize_text

        table = re.search(
            r"\| Bug shape \| Range \| Repro \| Agents \|.*?(?=\n\n)",
            pasteurize_text,
            re.DOTALL,
        )
        assert table, "pasteurize/SKILL.md's fan-out sizing table is missing"
        rows = table.group(0)

        tight_deterministic_n = pasteurize_route._REGRESSION_TIGHT_DETERMINISTIC_N  # pyright: ignore[reportPrivateUsage]
        tight_nondeterministic_n = pasteurize_route._REGRESSION_TIGHT_NONDETERMINISTIC_N  # pyright: ignore[reportPrivateUsage]
        wide_deterministic_n = pasteurize_route._REGRESSION_WIDE_DETERMINISTIC_N  # pyright: ignore[reportPrivateUsage]
        wide_nondeterministic_n = pasteurize_route._REGRESSION_WIDE_NONDETERMINISTIC_N  # pyright: ignore[reportPrivateUsage]
        unstable_repro_n = pasteurize_route._UNSTABLE_REPRO_N  # pyright: ignore[reportPrivateUsage]
        cold_bug_deterministic_n = pasteurize_route._COLD_BUG_DETERMINISTIC_N  # pyright: ignore[reportPrivateUsage]
        cold_bug_nondeterministic_n = pasteurize_route._COLD_BUG_NONDETERMINISTIC_N  # pyright: ignore[reportPrivateUsage]

        expectations = [
            ("tight", "deterministic", tight_deterministic_n),
            ("tight", "non-deterministic", tight_nondeterministic_n),
            ("wide", "deterministic", wide_deterministic_n),
            ("wide", "non-deterministic", wide_nondeterministic_n),
        ]
        for range_word, repro_word, expected_n in expectations:
            row_pattern = (
                r"\| regression \| "
                + range_word
                + r"[^|]*\| "
                + repro_word
                + r" \| "
                + str(expected_n)
                + r"\b"
            )
            assert re.search(row_pattern, rows), (
                f"pasteurize/SKILL.md's table does not show n={expected_n} for "
                f"regression/{range_word}/{repro_word}"
            )

        assert re.search(r"heisenbug.*?\| " + str(unstable_repro_n) + r"\b", rows), (
            f"pasteurize/SKILL.md's table does not show n="
            f"{unstable_repro_n} for the heisenbug row"
        )
        assert re.search(
            r"cold bug.*?deterministic \| " + str(cold_bug_deterministic_n) + r"\b",
            rows,
        ), (
            f"pasteurize/SKILL.md's table does not show n="
            f"{cold_bug_deterministic_n} for the deterministic cold-bug row"
        )
        assert re.search(
            r"cold bug.*?non-deterministic \| "
            + str(cold_bug_nondeterministic_n)
            + r"\b",
            rows,
        ), (
            f"pasteurize/SKILL.md's table does not show n="
            f"{cold_bug_nondeterministic_n} for the non-deterministic "
            f"cold-bug row"
        )
