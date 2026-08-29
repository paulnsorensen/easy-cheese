"""Tests for src/fanout/age_route.py -- the pure age/affinage sizing router.

Locks deterministic-fanout-sizing.md's age-router seam (`### 2. Reviewer
ladder` + `### 3. Overrides promote`): n in {1, 2, 5} from a single score,
override flags PROMOTING their mapped dimension into a solo lens (not
escalating to the top tier), and the five-lens refinement tree.
"""
from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path
from typing import TypedDict, cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src" / "fanout"))

from easy_cheese.shared.fanout import age_route  # noqa: E402

class _RouteResult(TypedDict):
    n: int
    lenses: list[list[str]]
    effort: str
    overrides_hit: list[str]
    rationale: str


def _route(
    *,
    score: float,
    risk_flags: list[str] | None = None,
    entry: str = "age",
    comments: int | None = None,
    ci_class: str | None = None,
) -> _RouteResult:
    raw = age_route.route(
        score=score,
        risk_flags=risk_flags,
        entry=entry,
        comments=comments,
        ci_class=ci_class,
    )
    return cast(_RouteResult, cast(object, raw))


class TestScoreTiers:
    """No risk flags: n is decided purely by score."""

    def test_low_score_routes_n1_low_effort(self) -> None:
        # Acceptance: route(score=30) -> n=1, effort='low', one lens of all ten.
        result = _route(score=30, risk_flags=[])
        assert result["n"] == 1
        assert result["effort"] == "low"
        assert result["overrides_hit"] == []
        assert result["lenses"] == [list(age_route.DIMENSIONS)]

    def test_mid_score_routes_n2_medium(self) -> None:
        # Acceptance: route(score=150) -> n=2, the two-group split, medium.
        result = _route(score=150, risk_flags=[])
        assert result["n"] == 2
        assert result["effort"] == "medium"
        assert result["overrides_hit"] == []
        assert result["lenses"] == [
            ["correctness", "spec", "assertions", "security", "telemetry"],
            ["encapsulation", "complexity", "deslop", "nih", "efficiency"],
        ]

    def test_high_score_routes_n5_five_named_lenses(self) -> None:
        # Acceptance: route(score=400) -> n=5, the five named lenses.
        result = _route(score=400, risk_flags=[])
        assert result["n"] == 5
        assert result["effort"] == "medium"
        assert result["overrides_hit"] == []
        assert result["lenses"] == [
            ["correctness", "spec", "assertions"],
            ["security", "telemetry"],
            ["encapsulation", "complexity"],
            ["deslop", "nih"],
            ["efficiency"],
        ]

    def test_score_over_900_is_high_effort_alone(self) -> None:
        # Acceptance: route(score=1000, risk_flags=[]) -> effort='high' via
        # the score>900 branch alone (no overrides involved).
        result = _route(score=1000, risk_flags=[])
        assert result["n"] == 5
        assert result["effort"] == "high"
        assert result["overrides_hit"] == []

    def test_boundary_just_under_n2_stays_n1(self) -> None:
        result = _route(score=59.9, risk_flags=[])
        assert result["n"] == 1

    def test_boundary_at_n2_floor_moves_to_n2(self) -> None:
        result = _route(score=60, risk_flags=[])
        assert result["n"] == 2

    def test_boundary_at_n5_floor_stays_n2(self) -> None:
        result = _route(score=250, risk_flags=[])
        assert result["n"] == 2

    def test_boundary_just_over_n5_floor_moves_to_n5(self) -> None:
        result = _route(score=250.1, risk_flags=[])
        assert result["n"] == 5

    def test_score_at_900_is_not_high_effort(self) -> None:
        result = _route(score=900, risk_flags=[])
        assert result["effort"] == "medium"


class TestOverridePromotion:
    """An OVERRIDE_FLAGS hit promotes its dimension to a solo lens; the
    group it left survives with its remaining members -- it never escalates
    to a blanket top tier."""

    def test_auth_on_tiny_score_promotes_security_solo(self) -> None:
        # SPEC ACCEPTANCE 5: route(score=20, risk_flags=['auth']) -> n=2,
        # lenses [[security],[rest]], overrides_hit=['auth'], effort='high'.
        result = _route(score=20, risk_flags=["auth"])
        assert result["n"] == 2
        assert result["effort"] == "high"
        assert result["overrides_hit"] == ["auth"]
        rest = [d for d in age_route.DIMENSIONS if d != "security"]
        assert result["lenses"] == [["security"], rest]

    def test_multiple_overrides_all_recorded(self) -> None:
        result = _route(
            score=1,
            risk_flags=["schema-migration", "production-destructive", "not-an-override"],
        )
        assert result["effort"] == "high"
        assert result["overrides_hit"] == ["production-destructive", "schema-migration"]
        # Both flags promote different dimensions (correctness, encapsulation);
        # both must appear as solo lenses, nothing truncated.
        assert ["correctness"] in result["lenses"]
        assert ["encapsulation"] in result["lenses"]

    def test_unrecognized_flag_does_not_promote(self) -> None:
        result = _route(score=20, risk_flags=["typo-fix"])
        assert result["n"] == 1
        assert result["overrides_hit"] == []
        assert result["effort"] == "low"

    def test_every_documented_override_category_is_recognized(self) -> None:
        for flag in age_route.OVERRIDE_FLAGS:
            result = _route(score=1, risk_flags=[flag])
            assert result["overrides_hit"] == [flag]
            assert result["effort"] == "high"
            promoted = age_route._PROMOTIONS[flag]
            assert [promoted] in result["lenses"], f"{flag} did not promote {promoted}"

    def test_all_four_override_categories_uncapped_n9(self) -> None:
        # SPEC ACCEPTANCE 7: all four override categories at once -> n=9,
        # every promoted dimension solo, nothing truncated. Requires the n=5
        # base tree (score > 250) so each promoted dimension comes from its
        # own tree lens.
        result = _route(
            score=400,
            risk_flags=["auth", "payments", "schema-migration", "weak-integration-coverage"],
        )
        assert result["n"] == 9
        assert result["effort"] == "high"
        assert result["overrides_hit"] == [
            "auth",
            "payments",
            "schema-migration",
            "weak-integration-coverage",
        ]
        for solo in ("security", "correctness", "encapsulation", "assertions"):
            assert [solo] in result["lenses"]
        # Every dimension appears exactly once across the partition.
        flat = [dim for lens in result["lenses"] for dim in lens]
        assert sorted(flat) == sorted(age_route.DIMENSIONS)
        assert len(flat) == len(age_route.DIMENSIONS)

class TestOverridePromotionNeverReducesN:
    """Finding 1 regression (BLOCKER): an override must never reduce n
    below what the same score/comments/ci_class would route without it --
    promotion composes on top of any affinage escalation, it never resets
    the tier the override promotes from."""

    @pytest.mark.parametrize("score", [1, 20, 59.9, 60, 100, 150, 250, 250.1, 400, 1000])
    @pytest.mark.parametrize(
        "entry,comments,ci_class",
        [
            ("age", None, None),
            ("affinage", None, None),
            ("affinage", 2, None),
            ("affinage", 15, None),
            ("affinage", None, "passing"),
            ("affinage", None, "failing"),
            ("affinage", 20, "failing"),
        ],
    )
    def test_override_never_lowers_n(
        self, score: float, entry: str, comments: int | None, ci_class: str | None
    ) -> None:
        without = _route(
            score=score, risk_flags=[], entry=entry, comments=comments, ci_class=ci_class
        )
        with_override = _route(
            score=score, risk_flags=["auth"], entry=entry, comments=comments, ci_class=ci_class
        )
        assert with_override["n"] >= without["n"]

    def test_blocker_repro_auth_flag_increases_n_under_affinage_escalation(self) -> None:
        # The exact repro from the BLOCKER finding: adding "auth" must not
        # drop n from 5 to 3 -- it must compose on top of the escalated tier.
        without = _route(
            score=100.0, risk_flags=[], entry="affinage", comments=20, ci_class="failing"
        )
        with_override = _route(
            score=100.0, risk_flags=["auth"], entry="affinage", comments=20, ci_class="failing"
        )
        assert with_override["n"] >= without["n"]
        assert without["n"] == 5
        assert with_override["n"] == 6

class TestEncapsulationSeparation:
    """SPEC ACCEPTANCE 6: encapsulation never shares a lens with efficiency
    or telemetry at the ladder's finest partition (n=5), which is the level
    the old N=4 'leftovers' grouping got wrong. Coarser tiers merge whole
    tree lenses together by design (n=2's second group spans lens3-5), so
    the never-co-occur guarantee is meaningful precisely where the tree is
    fully resolved."""

    def test_n5_keeps_encapsulation_isolated_from_efficiency_and_telemetry(self) -> None:
        result = _route(score=400, risk_flags=[])
        for lens in result["lenses"]:
            if "encapsulation" in lens:
                assert "efficiency" not in lens
                assert "telemetry" not in lens

    def test_promoted_encapsulation_is_always_isolated(self) -> None:
        # Whenever encapsulation is promoted (any base tier), it is solo --
        # trivially separated from efficiency and telemetry.
        for score in (20, 150, 400):
            result = _route(score=score, risk_flags=["schema-migration"])
            assert ["encapsulation"] in result["lenses"]


class TestDimensionPartitionInvariant:
    """Every dimension appears exactly once across the lens partition, at
    every tier and under every override combination."""

    @pytest.mark.parametrize("score", [10, 30, 59.9, 60, 150, 250, 250.1, 400, 1000])
    def test_partition_covers_every_dimension_exactly_once_no_override(self, score: float) -> None:
        result = _route(score=score, risk_flags=[])
        flat = [dim for lens in result["lenses"] for dim in lens]
        assert sorted(flat) == sorted(age_route.DIMENSIONS)
        assert len(flat) == len(age_route.DIMENSIONS)

    @pytest.mark.parametrize("score", [20, 150, 400])
    @pytest.mark.parametrize(
        "flags",
        [
            ["auth"],
            ["payments"],
            ["schema-migration"],
            ["weak-integration-coverage"],
            ["auth", "payments", "schema-migration", "weak-integration-coverage"],
        ],
    )
    def test_partition_covers_every_dimension_exactly_once_with_overrides(
        self, score: float, flags: list[str]
    ) -> None:
        result = _route(score=score, risk_flags=flags)
        flat = [dim for lens in result["lenses"] for dim in lens]
        assert sorted(flat) == sorted(age_route.DIMENSIONS)
        assert len(flat) == len(age_route.DIMENSIONS)


class TestRefinementTreeStructuralInvariant:
    """A regrouping regression that only shifted which lens a dimension
    lands in -- without changing DIMENSIONS or lens counts -- would not be
    caught by the hardcoded-list tests above if they were ever loosened.
    Every coarser tier's lens groups must be exact unions of whole
    next-finer-tier groups, with no finer group split across two coarser
    ones. Computed structurally from route()'s own output -- no dimension
    names hardcoded here."""

    @staticmethod
    def _assert_coarse_is_union_of_fine(coarse: list[list[str]], fine: list[list[str]]) -> None:
        fine_sets = [frozenset(group) for group in fine]
        for coarse_group in coarse:
            coarse_set = frozenset(coarse_group)
            covering = [fs for fs in fine_sets if fs <= coarse_set]
            assert covering, (coarse_group, fine)
            assert frozenset().union(*covering) == coarse_set, (coarse_group, fine)
            # No fine group straddles this coarse group's boundary: each one
            # is either fully inside it or fully outside it.
            for fs in fine_sets:
                assert fs <= coarse_set or fs.isdisjoint(coarse_set), (fs, coarse_group)

    def test_n2_groups_are_unions_of_whole_n5_groups(self) -> None:
        n2 = _route(score=150, risk_flags=[])["lenses"]
        n5 = _route(score=400, risk_flags=[])["lenses"]
        self._assert_coarse_is_union_of_fine(n2, n5)

    def test_n1_lens_is_union_of_both_n2_groups(self) -> None:
        n1 = _route(score=30, risk_flags=[])["lenses"]
        n2 = _route(score=150, risk_flags=[])["lenses"]
        self._assert_coarse_is_union_of_fine(n1, n2)


class TestAffinageEscalation:
    """affinage entries weight high comment count / risky ci_class upward,
    one tier step in the (1, 2, 5) order, capped at the top."""

    def test_age_entry_rejects_comments_and_ci_class(self) -> None:
        # entry="age" silently dropping comments/ci_class hid a miswired
        # caller getting a quietly smaller fan-out -- now it fails loud.
        with pytest.raises(ValueError):
            _ = _route(
                score=30, risk_flags=[], entry="age", comments=999, ci_class="failing"
            )

    def test_affinage_high_comment_count_bumps_tier(self) -> None:
        result = _route(score=30, risk_flags=[], entry="affinage", comments=15)
        assert result["n"] == 2

    def test_affinage_low_comment_count_does_not_bump(self) -> None:
        result = _route(score=30, risk_flags=[], entry="affinage", comments=2)
        assert result["n"] == 1

    def test_affinage_failing_ci_class_bumps_tier(self) -> None:
        result = _route(score=30, risk_flags=[], entry="affinage", ci_class="failing")
        assert result["n"] == 2

    def test_affinage_bump_never_exceeds_n5(self) -> None:
        result = _route(
            score=400, risk_flags=[], entry="affinage", comments=50, ci_class="failing"
        )
        assert result["n"] == 5

    def test_affinage_comment_count_at_exact_threshold_bumps(self) -> None:
        result = _route(score=30, risk_flags=[], entry="affinage", comments=10)
        assert result["n"] == 2

    def test_affinage_comment_count_just_under_threshold_does_not_bump(self) -> None:
        result = _route(score=30, risk_flags=[], entry="affinage", comments=9)
        assert result["n"] == 1

    def test_affinage_red_ci_class_bumps_tier(self) -> None:
        result = _route(score=30, risk_flags=[], entry="affinage", ci_class="red")
        assert result["n"] == 2

    def test_affinage_flaky_ci_class_bumps_tier(self) -> None:
        result = _route(score=30, risk_flags=[], entry="affinage", ci_class="flaky")
        assert result["n"] == 2

    def test_affinage_healthy_ci_class_does_not_bump(self) -> None:
        result = _route(score=30, risk_flags=[], entry="affinage", ci_class="passing")
        assert result["n"] == 1

    def test_affinage_comments_and_ci_class_both_bump_in_one_call(self) -> None:
        # A score in the n=1 rung with both a high comment count and a risky
        # ci_class must bump twice: 1 -> 2 -> 5, one step per signal, and the
        # rationale must record both reasons in the combined form.
        result = _route(
            score=30, risk_flags=[], entry="affinage", comments=15, ci_class="failing"
        )
        assert result["n"] == 5
        assert result["effort"] == "medium"
        assert "15 comments + ci_class=failing" in result["rationale"]


class TestInputValidation:
    def test_invalid_entry_raises(self) -> None:
        with pytest.raises(ValueError):
            _ = _route(score=1, entry="bogus")

    def test_negative_score_raises(self) -> None:
        with pytest.raises(ValueError):
            _ = _route(score=-1)

    def test_non_finite_score_raises(self) -> None:
        with pytest.raises(ValueError):
            _ = _route(score=float("nan"))
        with pytest.raises(ValueError):
            _ = _route(score=float("inf"))

    def test_score_is_keyword_only(self) -> None:
        # `score` used to be `files_changed: int` in the same position, so a
        # stale positional call must fail loud rather than silently route
        # under a new meaning. Asserted on the signature rather than by
        # making the bad call: it pins the contract directly (a TypeError
        # could come from anything) and does not plant a deliberate
        # wrong-arity call for static analysis to flag.
        params = inspect.signature(age_route.route).parameters
        assert params["score"].kind is inspect.Parameter.KEYWORD_ONLY, (
            "route()'s score must stay keyword-only so a stale positional "
            "call raises TypeError instead of being read as a score"
        )
        assert not [
            name
            for name, p in params.items()
            if p.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ], "route() takes no positional parameters"

    def test_age_entry_rejects_comments_only(self) -> None:
        with pytest.raises(ValueError):
            _ = _route(score=30, entry="age", comments=50)


class TestOutputSchema:
    def test_output_keys_are_exactly_the_locked_shape(self) -> None:
        # SPEC ACCEPTANCE 9: output keys are exactly {n, lenses, effort,
        # overrides_hit, rationale}.
        result = _route(score=30)
        assert set(result.keys()) == {"n", "lenses", "effort", "overrides_hit", "rationale"}


class TestRationale:
    def test_rationale_is_one_line_and_mentions_decision(self) -> None:
        result = _route(score=150, risk_flags=[])
        assert "\n" not in result["rationale"]
        assert "n=2" in result["rationale"]
        assert "effort=medium" in result["rationale"]

    def test_override_rationale_reflects_affinage_inputs(self) -> None:
        # Finding 3: the audit trail must reconstruct the decision -- two
        # calls differing only in comments/ci_class must not produce
        # byte-identical rationale (that's how finding 1 stayed invisible).
        escalated = _route(
            score=100.0, risk_flags=["auth"], entry="affinage", comments=20, ci_class="failing"
        )
        baseline = _route(
            score=100.0, risk_flags=["auth"], entry="affinage", comments=0, ci_class=None
        )
        assert escalated["rationale"] != baseline["rationale"]


class TestPurity:
    """Acceptance #2: the module is a pure function -- no os/network/file I/O."""

    def test_module_has_no_io_imports(self) -> None:
        src = (REPO_ROOT / "src/easy_cheese/shared/fanout/age_route.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        banned = {"os", "sys", "socket", "subprocess", "requests", "urllib", "pathlib", "shutil"}
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not (imported & banned), f"unexpected I/O-shaped imports: {imported & banned}"

    def test_module_parses_as_valid_python(self) -> None:
        src = (REPO_ROOT / "src/easy_cheese/shared/fanout/age_route.py").read_text(encoding="utf-8")
        _ = ast.parse(src)  # raises SyntaxError if invalid


class TestLadderBounds:
    """Brute-forced bounds the routing ladder must never exceed (spec
    'Invariants that must survive')."""

    def test_max_n_under_promotion_is_9(self) -> None:
        all_flags = ["auth", "payments", "schema-migration", "weak-integration-coverage"]
        max_n = 0
        for score in range(0, 2000, 5):
            for entry, comments, ci_class in (
                ("age", None, None),
                ("affinage", 0, None),
                ("affinage", 50, "failing"),
            ):
                result = _route(
                    score=score,
                    risk_flags=all_flags,
                    entry=entry,
                    comments=comments,
                    ci_class=ci_class,
                )
                max_n = max(max_n, result["n"])
        assert max_n == 9

    def test_min_n_with_any_override_is_2(self) -> None:
        min_n: int | None = None
        for score in range(0, 2000, 5):
            for flag in sorted(age_route.OVERRIDE_FLAGS):
                for entry, comments, ci_class in (
                    ("age", None, None),
                    ("affinage", 0, None),
                ):
                    result = _route(
                        score=score,
                        risk_flags=[flag],
                        entry=entry,
                        comments=comments,
                        ci_class=ci_class,
                    )
                    if min_n is None or result["n"] < min_n:
                        min_n = result["n"]
        assert min_n == 2
