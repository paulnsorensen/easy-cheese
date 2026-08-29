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

from easy_cheese.shared.fanout import age_route, pasteurize_route

ROOT = Path(__file__).resolve().parents[2]

AGE_SKILL = ROOT / "skills" / "age" / "SKILL.md"
AGE_SUB_AGENT_GATE = ROOT / "skills" / "age" / "references" / "sub-agent-gate.md"
AFFINAGE_SKILL = ROOT / "skills" / "affinage" / "SKILL.md"
COOK_SKILL = ROOT / "skills" / "cook" / "SKILL.md"
PASTEURIZE_SKILL = ROOT / "skills" / "pasteurize" / "SKILL.md"
ROUTING_POLICY = ROOT / "skills" / "cheese" / "references" / "routing-policy.md"
DECOMPOSER_DOC = ROOT / "skills" / "cheese" / "references" / "decomposer.md"
PACKET_DOC = ROOT / "skills" / "age" / "references" / "packet.md"
MODE_PY = ROOT / "src" / "easy_cheese" / "shared" / "fanout" / "mode.py"
CURD_BLOCK_PY = ROOT / "src" / "easy_cheese" / "shared" / "fanout" / "curd_block.py"
AFFINAGE_FLOW_DETAILS_DOC = ROOT / "skills" / "affinage" / "references" / "flow-details.md"
AGE_FAN_OUT_DOC = ROOT / "skills" / "age" / "references" / "fan-out.md"
COOK_FAN_PATHWAY_DOC = ROOT / "skills" / "cook" / "references" / "fan-pathway.md"

WIKI_AGE_ROUTER = ROOT / ".hallouminate" / "wiki" / "architecture" / "age-fanout-router.md"
WIKI_ADR_001 = ROOT / ".hallouminate" / "wiki" / "adr" / "deterministic-fanout-sizing-001.md"
WIKI_ADR_002 = ROOT / ".hallouminate" / "wiki" / "adr" / "deterministic-fanout-sizing-002.md"
WIKI_ADR_003 = ROOT / ".hallouminate" / "wiki" / "adr" / "deterministic-fanout-sizing-003.md"
WIKI_ADR_004 = ROOT / ".hallouminate" / "wiki" / "adr" / "deterministic-fanout-sizing-004.md"
WIKI_ENTITIES = ROOT / ".hallouminate" / "wiki" / "fanout-engine-entities.md"

ALL_SIX = [
    AGE_SKILL,
    AGE_SUB_AGENT_GATE,
    AFFINAGE_SKILL,
    COOK_SKILL,
    PASTEURIZE_SKILL,
    ROUTING_POLICY,
]

# The retired-vocabulary sweep (TestNoVacuousRouteParams, TestAgeLadder) also
# covers the wiki pages a full /age review found stale on this branch. The
# ADRs legitimately discuss the *old* ladder as historical contrast (e.g.
# ADR-001's "n=10" in a before/after sentence), but the banned patterns below
# are the whole-ladder shapes (`{1, 4, 10}` / `1/4/10`) and the vacuous diff-stat
# params -- neither appears in that legitimate historical prose, so the same
# ban applies file-wide without punishing correct contrast.
WIKI_SET = [
    WIKI_AGE_ROUTER,
    WIKI_ADR_001,
    WIKI_ADR_002,
    WIKI_ADR_003,
    WIKI_ADR_004,
    WIKI_ENTITIES,
    PACKET_DOC,
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestNoVacuousRouteParams:
    """The decomposer's original gate checked for `files_changed=` -- a
    parameter no current route() call takes. None of the six docs should
    reference the old files_changed/insertions/deletions shape as a route()
    parameter."""

    def test_no_doc_references_old_diff_stat_params(self) -> None:
        for path in ALL_SIX + WIKI_SET:
            text = read(path)
            for banned in ("files_changed=", "insertions=", "deletions="):
                assert banned not in text, f"{path} still references {banned!r}"


class TestAgeLadder:
    """Age's fan-out ladder moved from the old 1/4/10 sizes to n in {1, 2, 5}."""

    def test_age_skill_describes_1_2_5_ladder(self) -> None:
        text = read(AGE_FAN_OUT_DOC)
        assert re.search(r"\{\s*1\s*,\s*2\s*,\s*5\s*\}", text), (
            "age/references/fan-out.md does not describe the n in {1, 2, 5} ladder"
        )

    def test_age_skill_does_not_describe_old_1_4_10_ladder(self) -> None:
        text = read(AGE_FAN_OUT_DOC)
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
        text = read(AGE_FAN_OUT_DOC)
        lens_tree = age_route._LENS_TREE
        for group in lens_tree:
            pattern = r"\[\s*" + r"\s*,\s*".join(group) + r"\s*\]"
            assert re.search(pattern, text), (
                f"age/references/fan-out.md does not name the lens grouping {group!r}"
            )

    def test_wiki_docs_do_not_describe_old_1_4_10_ladder(self) -> None:
        for path in WIKI_SET:
            text = read(path)
            assert not re.search(r"\{\s*1\s*,\s*4\s*,\s*10\s*\}", text), (
                f"{path} still describes the retired {{1, 4, 10}} ladder"
            )
            assert "1/4/10" not in text, f"{path} still describes the retired 1/4/10 ladder"


class TestAffinageRouteCall:
    def test_affinage_route_call_passes_score_kwarg(self) -> None:
        text = read(AFFINAGE_FLOW_DETAILS_DOC)
        assert re.search(r"route\(\s*score\s*=", text), (
            "affinage/references/flow-details.md's route call does not pass score="
        )


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

        cook_text = read(COOK_FAN_PATHWAY_DOC)
        assert threshold in cook_text, (
            f"cook/references/fan-pathway.md does not mention the live threshold {threshold}"
        )

    def test_age_skill_router_ladder_matches_live_score_floors(self) -> None:
        n2_floor = age_route._SCORE_N2_FLOOR
        n5_floor = age_route._SCORE_N5_FLOOR
        high_effort_score = age_route._HIGH_EFFORT_SCORE
        assert n2_floor == 60
        assert n5_floor == 250
        assert high_effort_score == 900

        age_text = read(AGE_FAN_OUT_DOC)
        assert f"<{n2_floor}" in age_text, (
            f"age/references/fan-out.md does not quote the live _SCORE_N2_FLOOR "
            f"({n2_floor})"
        )
        assert f"{n2_floor}–{n5_floor}" in age_text, (
            f"age/references/fan-out.md does not quote the live _SCORE_N2_FLOOR-_SCORE_N5_FLOOR "
            f"band ({n2_floor}-{n5_floor})"
        )
        assert f">{n5_floor}" in age_text, (
            f"age/references/fan-out.md does not quote the live _SCORE_N5_FLOOR "
            f"({n5_floor})"
        )
        assert str(high_effort_score) in age_text, (
            f"age/references/fan-out.md does not quote the live _HIGH_EFFORT_SCORE "
            f"({high_effort_score})"
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

        tight_deterministic_n = pasteurize_route._REGRESSION_TIGHT_DETERMINISTIC_N
        tight_nondeterministic_n = pasteurize_route._REGRESSION_TIGHT_NONDETERMINISTIC_N
        wide_deterministic_n = pasteurize_route._REGRESSION_WIDE_DETERMINISTIC_N
        wide_nondeterministic_n = pasteurize_route._REGRESSION_WIDE_NONDETERMINISTIC_N
        unstable_repro_n = pasteurize_route._UNSTABLE_REPRO_N
        cold_bug_deterministic_n = pasteurize_route._COLD_BUG_DETERMINISTIC_N
        cold_bug_nondeterministic_n = pasteurize_route._COLD_BUG_NONDETERMINISTIC_N

        expectations = [
            ("tight", "deterministic", tight_deterministic_n),
            ("tight", "non-deterministic", tight_nondeterministic_n),
            ("wide", "deterministic", wide_deterministic_n),
            ("wide", "non-deterministic", wide_nondeterministic_n),
        ]
        for range_word, repro_word, expected_n in expectations:
            row_pattern = (
                r"\| regression \| " + range_word + r"[^|]*\| " + repro_word
                + r" \| " + str(expected_n) + r"\b"
            )
            assert re.search(row_pattern, rows), (
                f"pasteurize/SKILL.md's table does not show n={expected_n} for "
                f"regression/{range_word}/{repro_word}"
            )

        assert re.search(
            r"heisenbug.*?\| " + str(unstable_repro_n) + r"\b", rows
        ), (
            f"pasteurize/SKILL.md's table does not show n="
            f"{unstable_repro_n} for the heisenbug row"
        )
        assert re.search(
            r"cold bug.*?deterministic \| "
            + str(cold_bug_deterministic_n) + r"\b",
            rows,
        ), (
            f"pasteurize/SKILL.md's table does not show n="
            f"{cold_bug_deterministic_n} for the deterministic cold-bug row"
        )
        assert re.search(
            r"cold bug.*?non-deterministic \| "
            + str(cold_bug_nondeterministic_n) + r"\b",
            rows,
        ), (
            f"pasteurize/SKILL.md's table does not show n="
            f"{cold_bug_nondeterministic_n} for the non-deterministic "
            f"cold-bug row"
        )

    def test_min_curd_surface_matches_docs(self) -> None:
        curd_block_text = read(CURD_BLOCK_PY)
        match = re.search(r"MIN_CURD_SURFACE\s*=\s*(\d+)", curd_block_text)
        assert match, "src/fanout/curd_block.py no longer defines MIN_CURD_SURFACE"
        floor = match.group(1)

        for path in (DECOMPOSER_DOC, WIKI_ENTITIES):
            text = read(path)
            assert re.search(r"MIN_CURD_SURFACE\W{0,4}" + floor + r"\b", text), (
                f"{path} does not quote the live MIN_CURD_SURFACE ({floor})"
            )


class TestPacketSpeaksLens:
    """packet.md moved from per-dimension workers to per-lens workers; it must
    not describe the retired per-dimension contract as current."""

    def test_packet_doc_does_not_describe_per_dimension_workers(self) -> None:
        # Match any phrasing that assigns a worker a *dimension*, not just the one
        # exact retired phrase -- "Each dimension worker" is the same defect as
        # "per-dimension worker" and must fail too.
        text = read(PACKET_DOC)
        stale = re.search(r"(per-)?dimension\s+worker", text, re.IGNORECASE)
        assert not stale, (
            "packet.md still assigns workers a dimension rather than a lens: "
            f"{stale.group(0)!r}"
        )

    def test_packet_doc_describes_lens_workers(self) -> None:
        # Pin the structural contract, not the mere presence of the word "lens":
        # a worker owns a lenses[i] entry whose rubric slice is the union of that
        # lens's dimension rubrics.
        text = read(PACKET_DOC)
        assert re.search(r"lens\s+worker", text, re.IGNORECASE), (
            "packet.md does not describe per-lens workers"
        )
        assert "lenses[i]" in text, (
            "packet.md does not name the lenses[i] entry a worker owns"
        )
        assert re.search(r"union of the dimension rubrics", text, re.IGNORECASE), (
            "packet.md does not state the rubric slice is the union over the lens's dimensions"
        )
