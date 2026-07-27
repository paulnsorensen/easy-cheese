"""Content-asserting tests replacing the vacuous `grep -L ... | wc -l` docs gate.

That construction always exits 0 (grep -L inverts the match, wc swallows the
exit code), so it could never fail regardless of whether the six fanout-sizing
docs actually describe the shipped code. Every assertion here is a real
Python check against file content, so a doc reverting to the old contract
(files_changed param, the 1/4/10 age ladder, a missing decompose-first
policy, ...) makes the corresponding test fail.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

AGE_SKILL = ROOT / "skills" / "age" / "SKILL.md"
AGE_SUB_AGENT_GATE = ROOT / "skills" / "age" / "references" / "sub-agent-gate.md"
AFFINAGE_SKILL = ROOT / "skills" / "affinage" / "SKILL.md"
COOK_SKILL = ROOT / "skills" / "cook" / "SKILL.md"
PASTEURIZE_SKILL = ROOT / "skills" / "pasteurize" / "SKILL.md"
ROUTING_POLICY = ROOT / "skills" / "cheese" / "references" / "routing-policy.md"

ALL_SIX = [
    AGE_SKILL,
    AGE_SUB_AGENT_GATE,
    AFFINAGE_SKILL,
    COOK_SKILL,
    PASTEURIZE_SKILL,
    ROUTING_POLICY,
]

MODE_PY = ROOT / "src" / "fanout" / "mode.py"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestNoVacuousRouteParams:
    """The decomposer's original gate checked for `files_changed=` -- a
    parameter no current route() call takes. None of the six docs should
    reference the old files_changed/insertions/deletions shape as a route()
    parameter."""

    def test_no_doc_references_old_diff_stat_params(self) -> None:
        for path in ALL_SIX:
            text = read(path)
            for banned in ("files_changed=", "insertions=", "deletions="):
                assert banned not in text, f"{path} still references {banned!r}"


class TestAgeLadder:
    """Age's fan-out ladder moved from the old 1/4/10 sizes to n in {1, 2, 5}."""

    def test_age_skill_describes_1_2_5_ladder(self) -> None:
        text = read(AGE_SKILL)
        assert re.search(r"\{\s*1\s*,\s*2\s*,\s*5\s*\}", text), (
            "age/SKILL.md does not describe the n in {1, 2, 5} ladder"
        )

    def test_age_skill_does_not_describe_old_1_4_10_ladder(self) -> None:
        text = read(AGE_SKILL)
        assert not re.search(r"\{\s*1\s*,\s*4\s*,\s*10\s*\}", text)
        assert "1/4/10" not in text

    def test_sub_agent_gate_describes_1_2_5_ladder(self) -> None:
        text = read(AGE_SUB_AGENT_GATE)
        assert re.search(r"1\s*/\s*2\s*/\s*5", text), (
            "sub-agent-gate.md does not describe the 1 / 2 / 5 ladder"
        )

    def test_sub_agent_gate_does_not_describe_old_1_4_10_ladder(self) -> None:
        text = read(AGE_SUB_AGENT_GATE)
        assert not re.search(r"1\s*/\s*4\s*/\s*10", text)

    def test_age_skill_names_all_five_lens_groupings(self) -> None:
        text = read(AGE_SKILL)
        lens_groups = [
            ("correctness", "spec", "assertions"),
            ("security", "telemetry"),
            ("encapsulation", "complexity"),
            ("deslop", "nih"),
            ("efficiency",),
        ]
        for group in lens_groups:
            pattern = r"\[\s*" + r"\s*,\s*".join(group) + r"\s*\]"
            assert re.search(pattern, text), (
                f"age/SKILL.md does not name the lens grouping {group!r}"
            )


class TestAffinageRouteCall:
    def test_affinage_route_call_passes_score_kwarg(self) -> None:
        text = read(AFFINAGE_SKILL)
        assert re.search(r"route\(\s*score\s*=", text), (
            "affinage/SKILL.md's route call does not pass score="
        )


class TestCookModeSelection:
    def test_documents_select_mode_from_score(self) -> None:
        text = read(COOK_SKILL)
        assert "select_mode_from_score" in text

    def test_documents_both_linear_and_decompose_first(self) -> None:
        text = read(COOK_SKILL)
        assert '"linear"' in text
        assert "decompose-first" in text

    def test_states_it_never_returns_parallel(self) -> None:
        text = read(COOK_SKILL)
        assert re.search(r"never returns[^.]*parallel", text), (
            "cook/SKILL.md does not state select_mode_from_score never returns parallel"
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
    def test_table_has_age_router_row(self) -> None:
        text = read(ROUTING_POLICY)
        assert "age router" in text
        assert re.search(
            r"\{\s*1\s*all-dims\s*,\s*2\s*grouped\s*,\s*5\s*lenses\s*\}", text
        ), (
            "routing-policy.md's age router row does not reflect the n in "
            "{1, 2, 5} ladder"
        )

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

        cook_text = read(COOK_SKILL)
        assert threshold in cook_text, (
            f"cook/SKILL.md does not mention the live threshold {threshold}"
        )
