"""Focused tests for the contextual /age and /affinage planner."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src" / "fanout"))

from easy_cheese.shared.fanout import age_route  # noqa: E402


def _context(
    *,
    scope: str = "diff",
    effort: str = "normal",
    score: int | float = 20,
    applicability: dict[str, str] | None = None,
    risks: list[dict[str, object]] | None = None,
    can_fan_out: bool = True,
    is_subagent: bool = False,
    concurrency_limit: int | None = None,
) -> dict[str, object]:
    applicability = applicability or {}
    changed_paths = ["src/feature.py", "tests/test_feature.py"]
    subjects = [
        {
            "subject": subject,
            "applicability": applicability.get(subject, "yes"),
            "targets": list(changed_paths),
            "evidence": (
                [f"{subject} is outside this change"]
                if applicability.get(subject) == "no"
                else [f"{subject} applies to the changed feature"]
            ),
        }
        for subject in age_route.SUBJECTS
    ]
    return {
        "scope": scope,
        "effort": effort,
        "snapshot": "0123456789abcdef",
        "changed_paths": changed_paths,
        "surface_score": score,
        "components": [
            {"id": "feature", "role": "application", "paths": ["src/feature.py"]},
            {"id": "feature-tests", "role": "test", "paths": ["tests/test_feature.py"]},
        ],
        "subjects": subjects,
        "risks": risks or [],
        "is_subagent": is_subagent,
        "can_fan_out": can_fan_out,
        "concurrency_limit": concurrency_limit,
    }


def _route(
    *,
    scope: str = "diff",
    effort: str = "normal",
    score: int | float = 20,
    applicability: dict[str, str] | None = None,
    risks: list[dict[str, object]] | None = None,
    can_fan_out: bool = True,
    is_subagent: bool = False,
    concurrency_limit: int | None = None,
) -> dict[str, object]:
    return age_route.route(
        context=_context(
            scope=scope,
            effort=effort,
            score=score,
            applicability=applicability,
            risks=risks,
            can_fan_out=can_fan_out,
            is_subagent=is_subagent,
            concurrency_limit=concurrency_limit,
        )
    )


def _assignment(plan: dict[str, object], assignment_id: str) -> dict[str, object]:
    assignments = cast(list[dict[str, object]], plan["assignments"])
    return next(
        assignment for assignment in assignments if assignment["id"] == assignment_id
    )


class TestPublicContract:
    def test_subjects_are_complete_and_ordered(self) -> None:
        assert age_route.SUBJECTS == (
            "changed-behavior",
            "removed-behavior",
            "caller-impact",
            "security",
            "spec-tests",
            "reuse",
            "simplification",
            "efficiency",
            "conventions",
            "altitude",
        )

    def test_plan_contains_contextual_shape_not_dimension_partition(self) -> None:
        plan = _route()
        assert {
            "policy_version",
            "input_digest",
            "n",
            "effort",
            "assignments",
            "subject_dispositions",
            "rationale",
            "verification",
            "gap_sweep",
            "dispatch_batches",
            "degraded_reason",
        } <= set(plan)
        assert plan["policy_version"] == "age-review-plan.v1"
        assert plan["n"] == len(cast(list[object], plan["assignments"]))

    def test_reordering_canonicalizes_plan_and_digest(self) -> None:
        first = _context()
        second = copy.deepcopy(first)
        second["changed_paths"] = list(
            reversed(cast(list[str], second["changed_paths"]))
        )
        second["components"] = list(
            reversed(cast(list[dict[str, object]], second["components"]))
        )
        second["subjects"] = list(
            reversed(cast(list[dict[str, object]], second["subjects"]))
        )
        first_plan = age_route.route(context=first)
        second_plan = age_route.route(context=second)
        assert second_plan == first_plan


class TestSubjectPolicy:
    def test_normal_small_reserves_protected_subjects_without_padding(self) -> None:
        plan = _route(effort="normal", score=20)
        assert plan["n"] == 3
        assert [
            assignment["id"]
            for assignment in cast(list[dict[str, object]], plan["assignments"])
        ] == [
            "general",
            "conventions",
            "altitude",
        ]
        assert _assignment(plan, "general")["subjects"] == [
            "changed-behavior",
            "removed-behavior",
            "caller-impact",
            "security",
            "spec-tests",
            "reuse",
            "simplification",
            "efficiency",
        ]

    def test_ordinary_specialists_follow_policy_priority(self) -> None:
        normal = _route(effort="normal", score=100)
        assert [
            row["id"] for row in cast(list[dict[str, object]], normal["assignments"])
        ] == ["general", "security", "conventions", "altitude"]
        deep = _route(effort="deep", score=100)
        assert [
            row["id"] for row in cast(list[dict[str, object]], deep["assignments"])
        ] == [
            "general",
            "security",
            "caller-impact",
            "removed-behavior",
            "spec-tests",
            "conventions",
            "altitude",
        ]
        assert "changed-behavior" in cast(
            list[str], _assignment(deep, "general")["subjects"]
        )

    def test_quick_combines_protected_subjects(self) -> None:
        plan = _route(effort="quick", score=20)
        assert plan["n"] == 1
        assert _assignment(plan, "general")["subjects"] == list(age_route.SUBJECTS)

    def test_unknown_subject_stays_with_general_owner(self) -> None:
        plan = _route(
            effort="normal",
            score=400,
            applicability={"security": "unknown"},
        )
        security_owner = next(
            disposition["owner"]
            for disposition in cast(
                list[dict[str, object]], plan["subject_dispositions"]
            )
            if disposition["subject"] == "security"
        )
        assert security_owner == "general"
        assert "security" not in [
            assignment["id"]
            for assignment in cast(list[dict[str, object]], plan["assignments"])
            if assignment["id"] != "general"
        ]

    def test_no_applicability_requires_evidence_and_is_not_assigned(self) -> None:
        plan = _route(applicability={"security": "no"})
        security = next(
            disposition
            for disposition in cast(
                list[dict[str, object]], plan["subject_dispositions"]
            )
            if disposition["subject"] == "security"
        )
        assert security["owner"] is None
        assert security["assigned"] is False
        assert security["evidence"]

    def test_overall_scope_separates_all_relevant_subjects(self) -> None:
        plan = _route(scope="overall", effort="quick", score=1)
        assert plan["n"] == len(age_route.SUBJECTS)
        assignments = cast(list[dict[str, object]], plan["assignments"])
        assert [assignment["id"] for assignment in assignments] == list(
            age_route.SUBJECTS
        )
        assert all(
            assignment["subjects"] == [assignment["id"]] for assignment in assignments
        )


class TestRiskAndAffinagePolicy:
    def test_removed_and_hot_path_risks_are_mandatory_even_in_quick_mode(self) -> None:
        plan = _route(
            effort="quick",
            risks=[
                {
                    "flag": "hot-path",
                    "state": "yes",
                    "evidence": ["request loop is hot"],
                },
                {
                    "flag": "removed-protection",
                    "state": "yes",
                    "evidence": ["guard was deleted"],
                },
                {
                    "flag": "auth",
                    "state": "yes",
                    "evidence": ["token boundary changed"],
                },
            ],
        )
        assignments = cast(list[dict[str, object]], plan["assignments"])
        assert [assignment["id"] for assignment in assignments] == [
            "general",
            "removed-behavior",
            "security",
            "efficiency",
        ]
        for subject in ("removed-behavior", "security", "efficiency"):
            specialist = _assignment(plan, subject)
            assert specialist["effort"] == "high"
            assert any(
                str(reason).startswith("risk:")
                for reason in cast(list[str], specialist["reasons"])
            )

    def test_existing_risk_flags_keep_explicit_subject_mappings(self) -> None:
        assert age_route.RISK_MAPPINGS["auth"] == "security"
        assert age_route.RISK_MAPPINGS["public-api-change"] == "caller-impact"
        assert age_route.RISK_MAPPINGS["weak-integration-coverage"] == "spec-tests"
        assert age_route.RISK_MAPPINGS["removed-protection"] == "removed-behavior"
        assert age_route.RISK_MAPPINGS["hot-path"] == "efficiency"

    def test_affinage_comments_and_ci_escalate_contextual_effort(self) -> None:
        context = _context(effort="quick")
        comments_plan = age_route.route(context=context, entry="affinage", comments=10)
        assert comments_plan["effort"] == "normal"
        ci_plan = age_route.route(context=context, entry="affinage", ci_class="failing")
        assert ci_plan["effort"] == "normal"
        with pytest.raises(ValueError, match="comments/ci_class"):
            _ = age_route.route(context=context, comments=10)

    def test_positive_risk_cannot_be_contradicted_by_not_applicable_subject(
        self,
    ) -> None:
        with pytest.raises(ValueError, match="contradicts"):
            _ = _route(
                applicability={"security": "no"},
                risks=[{"flag": "auth", "state": "yes", "evidence": ["auth changed"]}],
            )


class TestCapabilitiesAndVerification:
    def test_empty_degraded_plan_is_checkable_without_losing_desired_work(self) -> None:
        plan = _route(
            effort="quick",
            is_subagent=True,
            applicability={subject: "no" for subject in age_route.SUBJECTS},
        )
        result = age_route.check_execution(plan=plan, observations=None)
        assert result["status"] == "unobserved"
        assert result["planned_assignment_ids"] == []

        missing_work = _route(is_subagent=True)
        missing_work["assignments"] = []
        missing_work["n"] = 0
        missing_work["dispatch_batches"] = []
        with pytest.raises(ValueError, match="preserve every desired subject"):
            _ = age_route.check_execution(plan=missing_work, observations=None)

    def test_initial_plan_does_not_invent_candidate_findings(self) -> None:
        plan = _route()
        verification = cast(dict[str, object], plan["verification"])
        assert verification["candidate_batches"] == []

    def test_unavailable_fanout_reports_desired_and_combined_plans(self) -> None:
        plan = _route(can_fan_out=False, effort="normal")
        assert plan["degraded_reason"] == "agent fan-out unavailable"
        assert plan["desired_n"] == 3
        assert plan["n"] == 1
        assert _assignment(plan, "combined")["subjects"] == list(age_route.SUBJECTS)
        verification = cast(dict[str, object], plan["verification"])
        assert verification["status"] == "unavailable"
        assert verification["candidate_batches"] == []

    def test_concurrency_batches_without_dropping_full_deep_work(self) -> None:
        plan = _route(effort="deep", score=400, concurrency_limit=2)
        assignments = cast(list[dict[str, object]], plan["assignments"])
        batches = cast(list[list[str]], plan["dispatch_batches"])
        assert len(assignments) == 10
        assert all(1 <= len(batch) <= 2 for batch in batches)
        assert [item for batch in batches for item in batch] == [
            cast(str, assignment["id"]) for assignment in assignments
        ]

    def test_deep_gap_sweep_is_planned_after_verification(self) -> None:
        plan = _route(effort="deep", score=20)
        gap_sweep = cast(dict[str, object], plan["gap_sweep"])
        assert gap_sweep == {
            "required": True,
            "after": "verification",
            "status": "planned",
        }

    def test_check_execution_distinguishes_unobserved_and_reported(self) -> None:
        plan = _route()
        ids = [
            assignment["id"]
            for assignment in cast(list[dict[str, object]], plan["assignments"])
        ]
        unobserved = age_route.check_execution(plan=plan, observations=None)
        assert unobserved["status"] == "unobserved"
        assert unobserved["verified"] is False

        reported = age_route.check_execution(
            plan=plan,
            observations={
                "assignment_ids": ids,
                "one_message": True,
                "source": "reported",
            },
        )
        assert reported["status"] == "unverified"
        assert reported["consistent"] is True
        assert reported["verified"] is False

        host = age_route.check_execution(
            plan=plan,
            observations={"assignment_ids": ids, "one_message": True, "source": "host"},
        )
        assert host["status"] == "consistent"
        assert host["authenticated"] is False

    def test_check_execution_reports_exact_id_mismatch(self) -> None:
        plan = _route()
        ids = [
            assignment["id"]
            for assignment in cast(list[dict[str, object]], plan["assignments"])
        ]
        result = age_route.check_execution(
            plan=plan,
            observations={
                "assignment_ids": ids[:-1],
                "one_message": True,
                "source": "host",
            },
        )
        assert result["status"] == "inconsistent"
        assert result["missing_assignment_ids"] == [ids[-1]]

    def test_checker_accepts_mixed_applicability_plan(self) -> None:
        plan = _route(applicability={"security": "unknown"})
        assignments = cast(list[dict[str, object]], plan["assignments"])
        result = age_route.check_execution(
            plan=plan,
            observations={
                "assignment_ids": [assignment["id"] for assignment in assignments],
                "one_message": True,
                "source": "reported",
            },
        )
        assert result["consistent"] is True

    def test_deep_large_separates_uncertain_relevant_subjects(self) -> None:
        plan = _route(
            effort="deep",
            score=400,
            applicability={subject: "unknown" for subject in age_route.SUBJECTS},
        )
        assignments = cast(list[dict[str, object]], plan["assignments"])
        assert sorted(
            tuple(cast(list[str], assignment["subjects"])) for assignment in assignments
        ) == sorted((subject,) for subject in age_route.SUBJECTS)


class TestInputValidation:
    def test_context_requires_exact_fields(self) -> None:
        context = _context()
        del context["scope"]
        with pytest.raises(ValueError, match="context keys mismatch"):
            _ = age_route.route(context=context)

    def test_rejects_unknown_risk_signal(self) -> None:
        with pytest.raises(ValueError, match="supported risk signal"):
            _ = _route(
                risks=[{"flag": "mystery", "state": "yes", "evidence": ["unknown"]}]
            )

    def test_rejects_duplicate_subject_rows(self) -> None:
        context = _context()
        subjects = cast(list[dict[str, object]], context["subjects"])
        subjects[-1] = copy.deepcopy(subjects[0])
        with pytest.raises(ValueError, match="duplicate subject"):
            _ = age_route.route(context=context)

    def test_rejects_nonpositive_concurrency_limit(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            _ = _route(concurrency_limit=0)


class TestContractBoundaries:
    def test_unknown_ci_class_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="ci_class"):
            _ = age_route.route(
                context=_context(), entry="affinage", ci_class="fialing"
            )

    def test_active_subject_requires_nonempty_targets(self) -> None:
        context = _context()
        subjects = cast(list[dict[str, object]], context["subjects"])
        subjects[0]["targets"] = []
        with pytest.raises(ValueError, match="non-empty"):
            _ = age_route.route(context=context)

    def test_overall_assigns_not_applicable_subjects_independently(self) -> None:
        context = _context(scope="overall", effort="quick")
        subjects = cast(list[dict[str, object]], context["subjects"])
        subjects[-1]["applicability"] = "no"
        subjects[-1]["evidence"] = ["overall review explicitly includes altitude"]
        plan = age_route.route(context=context)
        assert plan["n"] == len(age_route.SUBJECTS)
        altitude = _assignment(plan, "altitude")
        assert altitude["subjects"] == ["altitude"]

    def test_protected_not_applicable_subject_requires_targets_for_override(
        self,
    ) -> None:
        context = _context(applicability={"conventions": "no"})
        subjects = cast(list[dict[str, object]], context["subjects"])
        subjects[-2]["targets"] = []
        with pytest.raises(ValueError, match="planned assignment"):
            _ = age_route.route(context=context)

    def test_unknown_risk_does_not_extract_a_specialist(self) -> None:
        plan = _route(
            score=400,
            risks=[
                {"flag": "auth", "state": "unknown", "evidence": ["boundary unclear"]}
            ],
        )
        assert "security" in cast(list[str], _assignment(plan, "general")["subjects"])
        assert "security" not in [
            assignment["id"]
            for assignment in cast(list[dict[str, object]], plan["assignments"])
            if assignment["id"] != "general"
        ]

    def test_affinage_comment_and_ci_signals_promote_one_band(self) -> None:
        context = _context(effort="quick")
        plan = age_route.route(
            context=context,
            entry="affinage",
            comments=10,
            ci_class="failing",
        )
        assert plan["effort"] == "normal"

    def test_checker_allows_multiple_planned_batches(self) -> None:
        plan = _route(effort="deep", score=400, concurrency_limit=2)
        ids = [
            assignment["id"]
            for assignment in cast(list[dict[str, object]], plan["assignments"])
        ]
        result = age_route.check_execution(
            plan=plan,
            observations={
                "assignment_ids": ids,
                "one_message": False,
                "source": "host",
            },
        )
        assert result["status"] == "consistent"
        assert result["expected_one_message"] is False

    def test_checker_rejects_empty_overall_plan(self) -> None:
        plan = _route(scope="overall", effort="quick")
        plan["assignments"] = []
        plan["n"] = 0
        plan["dispatch_batches"] = []
        with pytest.raises(ValueError):
            _ = age_route.check_execution(plan=plan, observations=None)
