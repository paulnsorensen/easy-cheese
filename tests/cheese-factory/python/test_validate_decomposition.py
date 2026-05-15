"""Unit tests for skills/cheese-factory/scripts/validate_decomposition.py.

Each of the five decomposition criteria gets positive + negative coverage,
plus DAG cycle detection and the minimum-curd-count gate.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType


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
# Criterion 1: one behaviour per curd
# ---------------------------------------------------------------------------


class TestOneBehaviour:
    def test_clear_single_behaviour_passes(self, validate_decomposition: ModuleType) -> None:
        curd = {"id": 1, "behavior": "Adds order entity"}
        assert validate_decomposition.check_one_behaviour(curd) is None

    def test_two_verbs_joined_by_and_fails(self, validate_decomposition: ModuleType) -> None:
        curd = {"id": 1, "behavior": "Adds order entity and renames the cart module"}
        err = validate_decomposition.check_one_behaviour(curd)
        assert err is not None
        assert "split" in err

    def test_empty_behaviour_fails(self, validate_decomposition: ModuleType) -> None:
        curd = {"id": 1, "behavior": ""}
        err = validate_decomposition.check_one_behaviour(curd)
        assert err is not None
        assert "behavior" in err

    def test_descriptive_and_without_two_verbs_passes(
        self, validate_decomposition: ModuleType
    ) -> None:
        # "and" without joining two action verbs is fine — this is the natural
        # English noun-list case, not a split-required two-behaviour case.
        curd = {"id": 1, "behavior": "Adds the order entity and its serialization helper"}
        # "Adds ... helper" is one behaviour. No second action verb after "and".
        assert validate_decomposition.check_one_behaviour(curd) is None


# ---------------------------------------------------------------------------
# Criterion 2: one acceptance criterion
# ---------------------------------------------------------------------------


class TestAcceptanceCriterion:
    def test_present_passes(self, validate_decomposition: ModuleType) -> None:
        curd = {"id": 1, "acceptance_criterion": "Spec §3.1"}
        assert validate_decomposition.check_acceptance_criterion(curd) is None

    def test_missing_fails(self, validate_decomposition: ModuleType) -> None:
        curd = {"id": 1}
        err = validate_decomposition.check_acceptance_criterion(curd)
        assert err is not None

    def test_empty_string_fails(self, validate_decomposition: ModuleType) -> None:
        curd = {"id": 1, "acceptance_criterion": "   "}
        err = validate_decomposition.check_acceptance_criterion(curd)
        assert err is not None


# ---------------------------------------------------------------------------
# Criterion 3: one test target
# ---------------------------------------------------------------------------


class TestTestTarget:
    def test_focused_command_passes(self, validate_decomposition: ModuleType) -> None:
        curd = {"id": 1, "test_target": "vitest run src/orders/order.test.ts"}
        assert validate_decomposition.check_test_target(curd) is None

    def test_chained_commands_fail(self, validate_decomposition: ModuleType) -> None:
        curd = {"id": 1, "test_target": "vitest run a.test.ts && vitest run b.test.ts"}
        err = validate_decomposition.check_test_target(curd)
        assert err is not None
        assert "chain" in err.lower() or "split" in err.lower()

    def test_semicolon_chained_commands_fail(
        self, validate_decomposition: ModuleType
    ) -> None:
        curd = {"id": 1, "test_target": "pytest a; pytest b"}
        err = validate_decomposition.check_test_target(curd)
        assert err is not None

    def test_missing_fails(self, validate_decomposition: ModuleType) -> None:
        curd = {"id": 1, "test_target": ""}
        err = validate_decomposition.check_test_target(curd)
        assert err is not None


# ---------------------------------------------------------------------------
# Criterion 4: file disjointness (HARD CONSTRAINT)
# ---------------------------------------------------------------------------


class TestFileDisjointness:
    def test_disjoint_curds_pass(self, validate_decomposition: ModuleType) -> None:
        curds = _curds(3)
        errors = validate_decomposition.check_file_disjointness(curds)
        assert errors == []

    def test_shared_file_fails(self, validate_decomposition: ModuleType) -> None:
        curds = _curds(2)
        # Force a collision.
        curds[1]["files"] = curds[0]["files"][:1] + ["src/feature_1.test.ts"]
        errors = validate_decomposition.check_file_disjointness(curds)
        assert errors, "expected a file-disjointness error"
        assert any("file-disjoint" in e or "appears in curd" in e for e in errors)

    def test_missing_files_field_fails(self, validate_decomposition: ModuleType) -> None:
        curds = _curds(1)
        curds[0].pop("files")
        errors = validate_decomposition.check_file_disjointness(curds)
        assert any("missing or empty 'files'" in e for e in errors)


# ---------------------------------------------------------------------------
# Wiring DAG: no cycles, references known ids
# ---------------------------------------------------------------------------


class TestWiringDag:
    def test_acyclic_dag_passes(self, validate_decomposition: ModuleType) -> None:
        wiring = [
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": []},
            {"id": "W2", "type": "di_registration", "file": "b.ts", "depends_on": ["W1"]},
            {"id": "W3", "type": "route_wiring", "file": "c.ts", "depends_on": ["W1", "W2"]},
        ]
        errors = validate_decomposition.check_wiring_dag(wiring)
        assert errors == []

    def test_cycle_is_detected(self, validate_decomposition: ModuleType) -> None:
        wiring = [
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": ["W2"]},
            {"id": "W2", "type": "di_registration", "file": "b.ts", "depends_on": ["W1"]},
        ]
        errors = validate_decomposition.check_wiring_dag(wiring)
        assert any("cycle" in e for e in errors)

    def test_unknown_dependency_id_fails(self, validate_decomposition: ModuleType) -> None:
        wiring = [
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": ["W999"]},
        ]
        errors = validate_decomposition.check_wiring_dag(wiring)
        assert any("unknown id" in e for e in errors)

    def test_self_loop_is_detected(self, validate_decomposition: ModuleType) -> None:
        # A node that lists itself in depends_on is a degenerate cycle. Cook's
        # spec named "no cycles" as a hard rule — a self-loop is a cycle of
        # length one and must not be missed.
        wiring = [
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": ["W1"]},
        ]
        errors = validate_decomposition.check_wiring_dag(wiring)
        assert any("cycle" in e for e in errors), errors
        # The reported cycle must name the offending node.
        assert any("W1" in e for e in errors), errors

    def test_multi_component_graph_reports_one_cycle(
        self, validate_decomposition: ModuleType
    ) -> None:
        # Two disconnected sub-graphs, each a cycle. The validator's contract
        # is "one cycle report is enough" (script comment line 147), so we
        # must still get at least one — the user fixes & re-runs.
        wiring = [
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": ["W2"]},
            {"id": "W2", "type": "di_registration", "file": "b.ts", "depends_on": ["W1"]},
            {"id": "W3", "type": "route_wiring", "file": "c.ts", "depends_on": ["W4"]},
            {"id": "W4", "type": "event_subscription", "file": "d.ts", "depends_on": ["W3"]},
        ]
        errors = validate_decomposition.check_wiring_dag(wiring)
        cycle_errs = [e for e in errors if "cycle" in e]
        assert cycle_errs, "expected at least one cycle report"

    def test_disconnected_acyclic_components_pass(
        self, validate_decomposition: ModuleType
    ) -> None:
        # Two acyclic sub-graphs with no shared nodes — must validate clean.
        wiring = [
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": []},
            {"id": "W2", "type": "di_registration", "file": "b.ts", "depends_on": ["W1"]},
            {"id": "W3", "type": "route_wiring", "file": "c.ts", "depends_on": []},
            {"id": "W4", "type": "event_subscription", "file": "d.ts", "depends_on": ["W3"]},
        ]
        assert validate_decomposition.check_wiring_dag(wiring) == []

    def test_diamond_dependency_is_acyclic(self, validate_decomposition: ModuleType) -> None:
        # Diamond: W4 depends on W2 and W3, both of which depend on W1.
        # This is a valid DAG (no back-edges) and must not be flagged.
        wiring = [
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": []},
            {"id": "W2", "type": "di_registration", "file": "b.ts", "depends_on": ["W1"]},
            {"id": "W3", "type": "route_wiring", "file": "c.ts", "depends_on": ["W1"]},
            {"id": "W4", "type": "event_subscription", "file": "d.ts", "depends_on": ["W2", "W3"]},
        ]
        assert validate_decomposition.check_wiring_dag(wiring) == []

    def test_three_node_transitive_cycle_is_detected(
        self, validate_decomposition: ModuleType
    ) -> None:
        # W1 → W2 → W3 → W1 — a non-trivial transitive cycle. The reported
        # path must include all three nodes so the user can fix the right edge.
        wiring = [
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": ["W2"]},
            {"id": "W2", "type": "di_registration", "file": "b.ts", "depends_on": ["W3"]},
            {"id": "W3", "type": "route_wiring", "file": "c.ts", "depends_on": ["W1"]},
        ]
        errors = validate_decomposition.check_wiring_dag(wiring)
        cycle_errs = [e for e in errors if "cycle" in e]
        assert cycle_errs, errors
        # All three node ids must appear in the cycle report.
        report = cycle_errs[0]
        assert "W1" in report and "W2" in report and "W3" in report, report


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
        # A junk entry in curds[] (None, a string, a number) must produce a
        # validation error string — not an uncaught AttributeError. The
        # validator is a user-facing CLI; a stack trace on garbage input is
        # a usability defect.
        curds = _curds(5) + [None, "string-not-dict", 42]  # type: ignore[list-item]
        manifest = _manifest(curds=curds)  # type: ignore[arg-type]
        errors = validate_decomposition.validate_manifest(manifest)
        # Every non-dict entry must be flagged.
        non_dict_errors = [e for e in errors if "non-dict" in e]
        assert len(non_dict_errors) >= 3, f"expected 3 non-dict errors, got: {errors}"

    def test_missing_id_curd_does_not_crash(
        self, validate_decomposition: ModuleType
    ) -> None:
        # An curd missing its 'id' field must surface as an error string,
        # not raise. The CLI prefers structured failure over a crash.
        curds = _curds(5)
        del curds[0]["id"]
        manifest = _manifest(curds=curds)
        # validate_manifest must return — not raise.
        validate_decomposition.validate_manifest(manifest)

    def test_non_dict_wiring_entry_does_not_crash(
        self, validate_decomposition: ModuleType
    ) -> None:
        # Parallel to test_non_dict_curd_entry_does_not_crash: a junk entry
        # in wiring[] (None, a string, a number) must not raise AttributeError
        # from a .get() on a non-dict — check_wiring_dag is called directly
        # from validate_manifest with whatever the manifest supplies. The
        # validator is a user-facing CLI; a stack trace on garbage input is
        # a usability defect (matches the check_file_disjointness defense).
        wiring = [
            None,
            "string-not-dict",
            42,
            {"id": "W1", "type": "barrel_export", "file": "a.ts", "depends_on": []},
        ]
        # Direct call must return cleanly — no raise.
        errors = validate_decomposition.check_wiring_dag(wiring)  # type: ignore[arg-type]
        # The valid W1 entry has no cycles / unknown deps, so no errors expected.
        assert errors == [], f"expected clean wiring result, got: {errors}"

        # End-to-end via validate_manifest must also not raise.
        manifest = _manifest(wiring=wiring)  # type: ignore[arg-type]
        validate_decomposition.validate_manifest(manifest)


# ---------------------------------------------------------------------------
# CLI: exit codes and stderr signalling
# ---------------------------------------------------------------------------


SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "skills"
    / "cheese-factory"
    / "scripts"
    / "validate_decomposition.py"
)


class TestCLI:
    def test_exits_zero_on_valid_manifest(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(manifest_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_exits_nonzero_on_invalid_manifest(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(json.dumps(_manifest(curds=_curds(2))), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(manifest_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "ultracook" in result.stderr.lower()

    def test_exits_nonzero_on_missing_file(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(tmp_path / "nope.json")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_reads_from_stdin_when_no_arg(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=json.dumps(_manifest()),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
