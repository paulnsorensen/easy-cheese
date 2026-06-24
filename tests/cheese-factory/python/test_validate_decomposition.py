"""Unit tests for cheese-factory entity modules and validate_decomposition.py.

Each of the five decomposition criteria gets positive + negative coverage,
plus DAG cycle detection and the minimum-curd-count gate.

Granular content / graph checks are exercised via the entity modules
(curd.behaviour_errors, curd.disjoint_files_errors, wiring.graph_errors);
end-to-end composition and CLI are exercised via validate_decomposition.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import build_pyz

BUNDLE = build_pyz.cached_bundle("cheese-factory")


def _curds(n: int = 5) -> list[dict]:
    """Build n disjoint, valid curds."""
    return [
        {
            "id": i + 1,
            "behavior": f"Implement feature {chr(ord('A') + i)}",
            "acceptance_criterion": f"Spec §{i + 1}",
            "files": [f"src/feature_{i}.ts", f"src/feature_{i}.test.ts"],
            "test_target": f"vitest run src/feature_{i}.test.ts",
            "status": "pending",
            "retry_count": 0,
        }
        for i in range(n)
    ]


def _manifest(curds: list[dict] | None = None, wiring: list[dict] | None = None) -> dict:
    return {
        "slug": "test",
        "spec_path": ".cheese/specs/test.md",
        "created": "2026-05-14T10:00:00Z",
        "phase": "gate_approved",
        "quality_gates": ["just check"],
        "host_capabilities": {},
        "seed": {"items": []},
        "curds": curds if curds is not None else _curds(),
        "wiring": wiring if wiring is not None else [],
    }


# ---------------------------------------------------------------------------
# Criterion 1: one behaviour per curd (via curd.behaviour_errors)
# ---------------------------------------------------------------------------


class TestOneBehaviour:
    def test_clear_single_behaviour_passes(self, curd: ModuleType) -> None:
        c = {"id": 1, "behavior": "Adds order entity"}
        errs = curd.behaviour_errors(c)
        assert not any("behavior" in e or "split" in e for e in errs)

    def test_two_verbs_joined_by_and_fails(self, curd: ModuleType) -> None:
        c = {"id": 1, "behavior": "Adds order entity and renames the cart module"}
        errs = curd.behaviour_errors(c)
        assert any("split" in e for e in errs)

    def test_empty_behaviour_fails(self, curd: ModuleType) -> None:
        c = {"id": 1, "behavior": ""}
        errs = curd.behaviour_errors(c)
        assert any("missing or empty 'behavior'" in e for e in errs)

    def test_descriptive_and_without_two_verbs_passes(
        self, curd: ModuleType
    ) -> None:
        # "and" without joining two action verbs is fine.
        c = {"id": 1, "behavior": "Adds the order entity and its serialization helper"}
        errs = curd.behaviour_errors(c)
        assert not any("split" in e for e in errs)


# ---------------------------------------------------------------------------
# Criterion 2: one acceptance criterion (via curd.behaviour_errors)
# ---------------------------------------------------------------------------


class TestAcceptanceCriterion:
    def test_present_passes(self, curd: ModuleType) -> None:
        c = {"id": 1, "behavior": "Adds X", "acceptance_criterion": "Spec §3.1", "test_target": "pytest t.py"}
        errs = curd.behaviour_errors(c)
        assert not any("acceptance" in e for e in errs)

    def test_missing_fails(self, curd: ModuleType) -> None:
        c = {"id": 1, "behavior": "Adds X", "test_target": "pytest t.py"}
        errs = curd.behaviour_errors(c)
        assert any("missing or empty 'acceptance_criterion'" in e for e in errs)

    def test_empty_string_fails(self, curd: ModuleType) -> None:
        c = {"id": 1, "behavior": "Adds X", "acceptance_criterion": "   ", "test_target": "pytest t.py"}
        errs = curd.behaviour_errors(c)
        assert any("missing or empty 'acceptance_criterion'" in e for e in errs)


# ---------------------------------------------------------------------------
# Criterion 3: one test target (via curd.behaviour_errors)
# ---------------------------------------------------------------------------


class TestTestTarget:
    def test_focused_command_passes(self, curd: ModuleType) -> None:
        c = {"id": 1, "behavior": "Adds X", "acceptance_criterion": "AC", "test_target": "vitest run src/orders/order.test.ts"}
        errs = curd.behaviour_errors(c)
        assert not any("test_target" in e for e in errs)

    def test_chained_commands_fail(self, curd: ModuleType) -> None:
        c = {"id": 1, "behavior": "Adds X", "acceptance_criterion": "AC",
             "test_target": "vitest run a.test.ts && vitest run b.test.ts"}
        errs = curd.behaviour_errors(c)
        assert any("chain" in e.lower() or "split" in e.lower() for e in errs)

    def test_semicolon_chained_commands_fail(self, curd: ModuleType) -> None:
        c = {"id": 1, "behavior": "Adds X", "acceptance_criterion": "AC",
             "test_target": "pytest a; pytest b"}
        errs = curd.behaviour_errors(c)
        assert any("chain" in e.lower() or "split" in e.lower() for e in errs)

    def test_missing_fails(self, curd: ModuleType) -> None:
        c = {"id": 1, "behavior": "Adds X", "acceptance_criterion": "AC", "test_target": ""}
        errs = curd.behaviour_errors(c)
        assert any("missing or empty 'test_target'" in e for e in errs)


# ---------------------------------------------------------------------------
# Criterion 4: file disjointness (via curd.disjoint_files_errors)
# ---------------------------------------------------------------------------


class TestFileDisjointness:
    def test_disjoint_curds_pass(self, curd: ModuleType) -> None:
        errors = curd.disjoint_files_errors(_curds(3))
        assert errors == []

    def test_shared_file_fails(self, curd: ModuleType) -> None:
        curds = _curds(2)
        # Force a collision.
        curds[1]["files"] = curds[0]["files"][:1] + ["src/feature_1.test.ts"]
        errors = curd.disjoint_files_errors(curds)
        assert errors, "expected a file-disjointness error"
        assert any("file-disjoint" in e or "appears in curd" in e for e in errors)

    def test_missing_files_field_fails(self, curd: ModuleType) -> None:
        curds = _curds(1)
        curds[0].pop("files")
        errors = curd.disjoint_files_errors(curds)
        assert any("missing or empty 'files'" in e for e in errors)


# ---------------------------------------------------------------------------
# Wiring DAG: no cycles, references known ids (via wiring.graph_errors)
# ---------------------------------------------------------------------------


class TestWiringDag:
    def test_acyclic_dag_passes(self, wiring: ModuleType) -> None:
        w = [
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": []},
            {"id": "W2", "type": "di_registration", "file": "b.ts", "depends_on": ["W1"]},
            {"id": "W3", "type": "route_wiring", "file": "c.ts", "depends_on": ["W1", "W2"]},
        ]
        assert wiring.graph_errors(w) == []

    def test_cycle_is_detected(self, wiring: ModuleType) -> None:
        w = [
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": ["W2"]},
            {"id": "W2", "type": "di_registration", "file": "b.ts", "depends_on": ["W1"]},
        ]
        errors = wiring.graph_errors(w)
        assert any("cycle" in e for e in errors)

    def test_unknown_dependency_id_fails(self, wiring: ModuleType) -> None:
        w = [
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": ["W999"]},
        ]
        errors = wiring.graph_errors(w)
        assert any("unknown id" in e for e in errors)

    def test_self_loop_is_detected(self, wiring: ModuleType) -> None:
        # A node that lists itself in depends_on is a degenerate cycle.
        w = [
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": ["W1"]},
        ]
        errors = wiring.graph_errors(w)
        assert any("cycle" in e for e in errors), errors
        assert any("W1" in e for e in errors), errors

    def test_multi_component_graph_reports_one_cycle(
        self, wiring: ModuleType
    ) -> None:
        w = [
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": ["W2"]},
            {"id": "W2", "type": "di_registration", "file": "b.ts", "depends_on": ["W1"]},
            {"id": "W3", "type": "route_wiring", "file": "c.ts", "depends_on": ["W4"]},
            {"id": "W4", "type": "event_subscription", "file": "d.ts", "depends_on": ["W3"]},
        ]
        errors = wiring.graph_errors(w)
        cycle_errs = [e for e in errors if "cycle" in e]
        assert cycle_errs, "expected at least one cycle report"

    def test_disconnected_acyclic_components_pass(
        self, wiring: ModuleType
    ) -> None:
        w = [
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": []},
            {"id": "W2", "type": "di_registration", "file": "b.ts", "depends_on": ["W1"]},
            {"id": "W3", "type": "route_wiring", "file": "c.ts", "depends_on": []},
            {"id": "W4", "type": "event_subscription", "file": "d.ts", "depends_on": ["W3"]},
        ]
        assert wiring.graph_errors(w) == []

    def test_diamond_dependency_is_acyclic(self, wiring: ModuleType) -> None:
        w = [
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": []},
            {"id": "W2", "type": "di_registration", "file": "b.ts", "depends_on": ["W1"]},
            {"id": "W3", "type": "route_wiring", "file": "c.ts", "depends_on": ["W1"]},
            {"id": "W4", "type": "event_subscription", "file": "d.ts", "depends_on": ["W2", "W3"]},
        ]
        assert wiring.graph_errors(w) == []

    def test_three_node_transitive_cycle_is_detected(
        self, wiring: ModuleType
    ) -> None:
        w = [
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": ["W2"]},
            {"id": "W2", "type": "di_registration", "file": "b.ts", "depends_on": ["W3"]},
            {"id": "W3", "type": "route_wiring", "file": "c.ts", "depends_on": ["W1"]},
        ]
        errors = wiring.graph_errors(w)
        cycle_errs = [e for e in errors if "cycle" in e]
        assert cycle_errs, errors
        report = cycle_errs[0]
        assert "W1" in report and "W2" in report and "W3" in report, report

    def test_non_dict_wiring_entry_does_not_crash(self, wiring: ModuleType) -> None:
        w = [None, "string-not-dict", 42,  # type: ignore[list-item]
             {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": []}]
        errors = wiring.graph_errors(w)  # type: ignore[arg-type]
        assert errors == [], f"expected clean wiring result, got: {errors}"


# ---------------------------------------------------------------------------
# Minimum curd count: /cheese-factory requires 5+
# ---------------------------------------------------------------------------


class TestMinimumCurdCount:
    def test_five_curds_passes(self, validate_decomposition: ModuleType) -> None:
        assert validate_decomposition.check_minimum_curd_count(_curds(5)) is None

    def test_six_curds_passes(self, validate_decomposition: ModuleType) -> None:
        assert validate_decomposition.check_minimum_curd_count(_curds(6)) is None

    def test_four_curds_fails(self, validate_decomposition: ModuleType) -> None:
        err = validate_decomposition.check_minimum_curd_count(_curds(4))
        assert err is not None
        assert "ultracook" in err.lower(), "must mention the smaller-decomposition route"


# ---------------------------------------------------------------------------
# End-to-end: validate_manifest aggregates every check
# ---------------------------------------------------------------------------


class TestValidateManifestE2E:
    def test_valid_manifest_returns_no_errors(self, validate_decomposition: ModuleType) -> None:
        manifest = _manifest()
        errors = validate_decomposition.validate_manifest(manifest)
        assert errors == []

    def test_invalid_manifest_collects_multiple_errors(
        self, validate_decomposition: ModuleType
    ) -> None:
        # Build a manifest violating: minimum count + criterion 1 + criterion 3 + criterion 4.
        curds = _curds(2)  # too few
        curds[0]["behavior"] = "Adds X and removes Y"  # two verbs
        curds[0]["test_target"] = "pytest a && pytest b"  # chained
        curds[1]["files"] = curds[0]["files"][:1] + ["other.ts"]  # collision
        errors = validate_decomposition.validate_manifest(_manifest(curds=curds))
        assert len(errors) >= 3

    def test_curds_must_be_a_list(self, validate_decomposition: ModuleType) -> None:
        manifest = _manifest()
        manifest["curds"] = "not a list"
        errors = validate_decomposition.validate_manifest(manifest)
        assert any("must be a list" in e for e in errors)

    def test_wiring_must_be_a_list(self, validate_decomposition: ModuleType) -> None:
        manifest = _manifest()
        manifest["wiring"] = {"not": "a list"}
        errors = validate_decomposition.validate_manifest(manifest)
        assert any("wiring must be a list" in e for e in errors)

    def test_non_dict_curd_entry_does_not_crash(
        self, validate_decomposition: ModuleType
    ) -> None:
        curds = _curds(5) + [None, "string-not-dict", 42]  # type: ignore[list-item]
        manifest = _manifest(curds=curds)  # type: ignore[arg-type]
        errors = validate_decomposition.validate_manifest(manifest)
        non_dict_errors = [e for e in errors if "non-dict" in e]
        assert len(non_dict_errors) >= 3, f"expected 3 non-dict errors, got: {errors}"

    def test_missing_id_curd_does_not_crash(
        self, validate_decomposition: ModuleType
    ) -> None:
        curds = _curds(5)
        del curds[0]["id"]
        manifest = _manifest(curds=curds)
        validate_decomposition.validate_manifest(manifest)

    def test_non_dict_wiring_entry_does_not_crash(
        self, validate_decomposition: ModuleType
    ) -> None:
        wiring = [
            None,
            "string-not-dict",
            42,
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": []},
        ]
        errors = validate_decomposition.validate_manifest(_manifest(wiring=wiring))  # type: ignore[arg-type]
        assert errors == [], f"expected clean result, got: {errors}"


# ---------------------------------------------------------------------------
# CLI: exit codes and stderr signalling
# ---------------------------------------------------------------------------


class TestCLI:
    def test_exits_zero_on_valid_manifest(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(BUNDLE), "validate_decomposition", str(manifest_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_exits_nonzero_on_invalid_manifest(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(json.dumps(_manifest(curds=_curds(2))), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(BUNDLE), "validate_decomposition", str(manifest_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "ultracook" in result.stderr.lower()

    def test_exits_nonzero_on_missing_file(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [sys.executable, str(BUNDLE), "validate_decomposition", str(tmp_path / "nope.json")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_reads_from_stdin_when_no_arg(self) -> None:
        result = subprocess.run(
            [sys.executable, str(BUNDLE), "validate_decomposition"],
            input=json.dumps(_manifest()),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Press hardening: list-aggregation + the full dedup contract (acceptance #3)
# ---------------------------------------------------------------------------


class TestBehaviourErrorsAggregation:
    def test_all_three_content_rules_report_together(self, curd: ModuleType) -> None:
        # behaviour_errors returns a list, not the first error: a curd that
        # violates all three content rules must surface all three, not short-circuit.
        c = {
            "id": 1,
            "behavior": "Adds X and removes Y",
            "acceptance_criterion": "",
            "test_target": "a && b",
        }
        errs = curd.behaviour_errors(c)
        assert len(errs) == 3, errs
        assert any("split into two curds" in e for e in errs)  # two-verb behaviour
        assert any("acceptance_criterion" in e for e in errs)
        assert any("test_target" in e for e in errs)


class TestCurdLifecycleDedup:
    """lifecycle_errors owns ONLY id/status/retry_count. It must not re-check
    behaviour/acceptance/test_target/files — those belong to behaviour_errors and
    disjoint_files_errors. Locks the *full* dedup (acceptance #3), not just the
    behavior half pinned by test_empty_behavior_reported_exactly_once."""

    def test_lifecycle_ignores_content_and_files_fields(self, curd: ModuleType) -> None:
        # Bad on every content/files rule but valid on the lifecycle fields ->
        # zero lifecycle errors, so no field can re-enter the double-report.
        c = {
            "id": 1,
            "status": "pending",
            "retry_count": 0,
            "behavior": "",
            "acceptance_criterion": "",
            "test_target": "a && b",
            # files intentionally absent — disjoint_files_errors' job
        }
        assert curd.lifecycle_errors(c, "curds[1]") == []

    def test_lifecycle_required_keys_are_only_id_status_retry(self, curd: ModuleType) -> None:
        errs = curd.lifecycle_errors({}, "curds[2]")
        assert "curds[2].id is required" in errs
        assert "curds[2].status is required" in errs
        assert "curds[2].retry_count is required" in errs
        # content/files keys are NOT lifecycle-required (owned elsewhere)
        assert not any("behavior is required" in e for e in errs)
        assert not any("acceptance_criterion is required" in e for e in errs)
        assert not any("test_target is required" in e for e in errs)
        assert not any("files is required" in e for e in errs)
