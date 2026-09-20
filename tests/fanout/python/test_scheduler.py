"""Unit tests for dependency-wave scheduling (mini-spec Sec9, AC-6/7/8)."""
from __future__ import annotations

from easy_cheese_schemas import (
    BoundedScope,
    ContractVersion,
    Criterion,
    CriterionDisposition,
    CriterionResult,
    CurdDisposition,
    CurdPlan,
    CurdResult,
    EvidenceKind,
    EvidenceRef,
    ArtifactRef,
    IdentityAction,
    IdentityLineage,
    SemanticCurd,
    SourceCurdRef,
    SourcePlanRef,
)

from easy_cheese.shared.fanout.scheduler import BlockedCurd, schedule_wave

DIGEST = f"sha256:{'a' * 64}"
PLAN_SCHEMA = "https://schemas.easy-cheese.dev/curd-plan"
RESULT_SCHEMA = "https://schemas.easy-cheese.dev/curd-result"


def _evidence() -> EvidenceRef:
    return EvidenceRef(
        evidence_id="evidence-1",
        kind=EvidenceKind.SOURCE,
        artifact=ArtifactRef(
            artifact_id="artifact-1",
            role="source",
            uri="repo://artifacts/artifact-1",
            digest=DIGEST,
            size_bytes=12,
            media_type="text/plain",
        ),
        summary="evidence",
    )


def _curd(curd_id: str, deps: tuple[str, ...] = ()) -> SemanticCurd:
    return SemanticCurd(
        curd_id=curd_id,
        outcome=f"Implement {curd_id}",
        scope=BoundedScope(paths=[f"src/{curd_id}.py"]),
        inputs=(),
        outputs=(f"{curd_id}-out",),
        dependencies=deps,
        criteria=(
            Criterion(
                criterion_id=f"{curd_id}-crit",
                description=f"{curd_id} passes",
                check="the focused regression passes",
            ),
        ),
        lineage=IdentityLineage(IdentityAction.NEW),
    )


def _plan() -> CurdPlan:
    # Diamond: a -> {b, c} -> d.
    return CurdPlan.signed(
        contract_version=ContractVersion(schema_uri=PLAN_SCHEMA, major="1", minor="0"),
        plan_id="plan-1",
        revision=1,
        objective="exercise dependency waves",
        curds=(
            _curd("a"),
            _curd("b", ("a",)),
            _curd("c", ("a",)),
            _curd("d", ("b", "c")),
        ),
    )


def _result(curd_id: str, disposition: CurdDisposition) -> CurdResult:
    if disposition is CurdDisposition.PASSED:
        rows = (
            CriterionResult(
                criterion_id=f"{curd_id}-crit",
                disposition=CriterionDisposition.PASSED,
                evidence=(_evidence(),),
            ),
        )
        unresolved: tuple[str, ...] = ()
    else:
        rows = (
            CriterionResult(
                criterion_id=f"{curd_id}-crit",
                disposition=CriterionDisposition.BLOCKED,
                reason="a prerequisite did not pass",
            ),
        )
        unresolved = ("blocking-prereq",)
    return CurdResult(
        contract_version=ContractVersion(schema_uri=RESULT_SCHEMA, major="1", minor="0"),
        result_id=f"{curd_id}-result",
        source_plan_ref=SourcePlanRef(plan_id="plan-1", revision=1, digest=DIGEST),
        source_curd_ref=SourceCurdRef(curd_id=curd_id, digest=DIGEST),
        disposition=disposition,
        expected_criterion_ids=(f"{curd_id}-crit",),
        criterion_results=rows,
        unresolved_work=unresolved,
    )


class TestReadyWaves:
    def test_root_is_the_only_first_wave(self) -> None:
        decision = schedule_wave(_plan(), {})
        assert decision.ready == ("a",)
        assert decision.remaining == ("b", "c", "d")
        assert not decision.complete

    def test_independent_siblings_both_ready_after_root(self) -> None:
        # AC-6/AC-7: b and c are independent and both continue once a passes.
        decision = schedule_wave(_plan(), {"a": _result("a", CurdDisposition.PASSED)})
        assert decision.ready == ("b", "c")
        assert decision.remaining == ("d",)
        assert decision.blocked == ()

    def test_join_is_ready_when_both_branches_pass(self) -> None:
        results = {
            cid: _result(cid, CurdDisposition.PASSED) for cid in ("a", "b", "c")
        }
        decision = schedule_wave(_plan(), results)
        assert decision.ready == ("d",)


class TestBlockedPropagation:
    def test_independent_branch_continues_while_sibling_blocks(self) -> None:
        # AC-7 + AC-8: b blocked -> c still ready, d blocked without dispatch.
        results = {
            "a": _result("a", CurdDisposition.PASSED),
            "b": _result("b", CurdDisposition.BLOCKED),
        }
        decision = schedule_wave(_plan(), results)
        assert decision.ready == ("c",)
        assert decision.blocked == (BlockedCurd(curd_id="d", blocked_by=("b",)),)
        assert decision.blocked[0].curd_id == "d"
        assert decision.blocked[0].blocked_by == ("b",)

    def test_root_block_blocks_direct_dependents_first(self) -> None:
        # AC-8: a blocked -> b and c blocked now; d still waits on unresolved b/c.
        decision = schedule_wave(
            _plan(), {"a": _result("a", CurdDisposition.BLOCKED)}
        )
        assert decision.ready == ()
        assert decision.blocked == (
            BlockedCurd(curd_id="b", blocked_by=("a",)),
            BlockedCurd(curd_id="c", blocked_by=("a",)),
        )
        assert decision.remaining == ("d",)

    def test_transitive_block_after_dependents_finalized(self) -> None:
        # AC-8: once b and c are finalized blocked, d blocks on both.
        results = {
            "a": _result("a", CurdDisposition.BLOCKED),
            "b": _result("b", CurdDisposition.BLOCKED),
            "c": _result("c", CurdDisposition.BLOCKED),
        }
        decision = schedule_wave(_plan(), results)
        assert decision.blocked == (BlockedCurd(curd_id="d", blocked_by=("b", "c")),)
        assert decision.ready == ()


class TestCompletion:
    def test_all_resulted_is_complete(self) -> None:
        results = {
            cid: _result(cid, CurdDisposition.PASSED)
            for cid in ("a", "b", "c", "d")
        }
        decision = schedule_wave(_plan(), results)
        assert decision.complete
        assert decision.ready == ()
        assert decision.blocked == ()

    def test_selected_subset_restricts_scope(self) -> None:
        # Only a and b are in scope; c and d are ignored.
        decision = schedule_wave(_plan(), {}, selected=("a", "b"))
        assert decision.ready == ("a",)
        assert decision.remaining == ("b",)


class TestSelectedValidation:
    def test_unknown_selected_curd_is_rejected(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="unknown curd"):
            _ = schedule_wave(_plan(), {}, selected=("missing",))

    def test_non_dependency_closed_selection_is_rejected(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="dependency-closed"):
            _ = schedule_wave(_plan(), {}, selected=("b",))
