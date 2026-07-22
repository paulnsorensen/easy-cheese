"""Tests for src/fanout/baseline.py -- classify() baseline diff classifier.

Covers the taxonomy /ultracook's baseline-aware quality gate (#298) needs:
an unchanged baseline must let the run continue (no false regressions), and
a new regression must still surface as `new` so the three-way policy can
bound-fix or halt on it. `baseline.py` is not yet registered in ultracook.pyz's
SKILLS map (a separate wiring task), so these tests import the module
directly from src/fanout/ rather than through the built bundle.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "shared" / "scripts"))  # cli.py
sys.path.insert(0, str(REPO_ROOT / "src" / "fanout"))

import baseline  # noqa: E402


def _record(suite: str, test_id: str, signature: str) -> baseline.FailureRecord:
    return {"suite": suite, "test_id": test_id, "signature": signature}


class TestUnchangedBaselineContinues:
    """A current run identical to the baseline must classify everything as
    `identical` with no `new` entries -- the three-way policy needs this to
    record+continue rather than mistake steady-state noise for a regression."""

    def test_same_failures_are_identical(self) -> None:
        run = [_record("unit", "test_a", "AssertionError: boom")]
        result = baseline.classify(run, run)
        assert result["identical"] == run
        assert result["new"] == []
        assert result["changed"] == []
        assert result["resolved"] == []

    def test_multiple_unchanged_failures_all_identical(self) -> None:
        run = [
            _record("unit", "test_a", "AssertionError: boom"),
            _record("unit", "test_b", "ValueError: nope"),
        ]
        result = baseline.classify(run, run)
        assert result["identical"] == run
        assert result["new"] == []


class TestNewRegressionHalts:
    """A failure absent from the baseline is `new` -- the signal the
    three-way policy uses to trigger a bounded fix, halt as last resort."""

    def test_failure_not_in_baseline_is_new(self) -> None:
        baseline_run = [_record("unit", "test_a", "AssertionError: boom")]
        current_run = baseline_run + [_record("unit", "test_c", "TypeError: unexpected")]
        result = baseline.classify(baseline_run, current_run)
        assert result["new"] == [_record("unit", "test_c", "TypeError: unexpected")]
        assert result["identical"] == baseline_run

    def test_entirely_new_failure_set(self) -> None:
        result = baseline.classify([], [_record("unit", "test_z", "RuntimeError: fresh regression")])
        assert result["new"] == [_record("unit", "test_z", "RuntimeError: fresh regression")]


class TestChangedSignature:
    def test_same_test_different_signature_is_changed(self) -> None:
        baseline_run = [_record("unit", "test_a", "AssertionError: old message")]
        current_run = [_record("unit", "test_a", "AssertionError: new message")]
        result = baseline.classify(baseline_run, current_run)
        assert result["changed"] == current_run
        assert result["identical"] == []
        assert result["new"] == []


class TestResolved:
    def test_baseline_entry_absent_from_current_is_resolved(self) -> None:
        baseline_run = [
            _record("unit", "test_a", "AssertionError: boom"),
            _record("unit", "test_b", "ValueError: nope"),
        ]
        current_run = [_record("unit", "test_a", "AssertionError: boom")]
        result = baseline.classify(baseline_run, current_run)
        assert result["resolved"] == [_record("unit", "test_b", "ValueError: nope")]
        assert result["identical"] == current_run


class TestEmptyInputs:
    def test_empty_baseline_all_current_are_new(self) -> None:
        current_run = [_record("unit", "test_a", "AssertionError: boom")]
        result = baseline.classify([], current_run)
        assert result["new"] == current_run
        assert result["identical"] == []
        assert result["resolved"] == []

    def test_empty_current_all_baseline_resolved(self) -> None:
        baseline_run = [_record("unit", "test_a", "AssertionError: boom")]
        result = baseline.classify(baseline_run, [])
        assert result["resolved"] == baseline_run
        assert result["identical"] == []
        assert result["new"] == []

    def test_both_empty(self) -> None:
        result = baseline.classify([], [])
        assert result == {"identical": [], "new": [], "changed": [], "resolved": []}


class TestNormalizeSignature:
    """The approved signature rule: first line, whitespace-normalized."""

    def test_takes_first_line_only(self) -> None:
        message = "AssertionError: boom\n  at line 42\n  more trace"
        assert baseline.normalize_signature(message) == "AssertionError: boom"

    def test_collapses_internal_whitespace(self) -> None:
        message = "AssertionError:   boom    happened"
        assert baseline.normalize_signature(message) == "AssertionError: boom happened"

    def test_collapses_tabs_and_mixed_whitespace(self) -> None:
        message = "AssertionError:\tboom\t happened"
        assert baseline.normalize_signature(message) == "AssertionError: boom happened"

    def test_strips_surrounding_whitespace(self) -> None:
        message = "  AssertionError: boom  \nmore"
        assert baseline.normalize_signature(message) == "AssertionError: boom"

    def test_empty_message_yields_empty_signature(self) -> None:
        assert baseline.normalize_signature("") == ""


class TestSuiteScopedIdentity:
    """(suite, test_id) is the identity key -- the same test_id in two
    different suites must not collide into one bucket."""

    def test_same_test_id_in_different_suites_are_independent(self) -> None:
        baseline_run = [_record("unit", "test_a", "AssertionError: boom")]
        current_run = [_record("integration", "test_a", "AssertionError: boom")]
        result = baseline.classify(baseline_run, current_run)
        assert result["new"] == current_run
        assert result["resolved"] == baseline_run
        assert result["identical"] == []


class TestDuplicateRecordsInInput:
    """A baseline or current list with a repeated (suite, test_id) key
    collapses to the last occurrence -- classify() must not raise or split
    the record across two buckets."""

    def test_duplicate_current_records_last_one_wins(self) -> None:
        current_run = [
            _record("unit", "test_a", "AssertionError: old"),
            _record("unit", "test_a", "AssertionError: new"),
        ]
        result = baseline.classify([], current_run)
        assert result["new"] == [_record("unit", "test_a", "AssertionError: new")]

    def test_duplicate_baseline_records_last_one_wins(self) -> None:
        baseline_run = [
            _record("unit", "test_a", "AssertionError: old"),
            _record("unit", "test_a", "AssertionError: new"),
        ]
        current_run = [_record("unit", "test_a", "AssertionError: new")]
        result = baseline.classify(baseline_run, current_run)
        assert result["identical"] == current_run
        assert result["changed"] == []


class TestBucketsAreMutuallyExclusiveAndOrdered:
    """A single mixed batch spanning all four buckets must partition cleanly
    with no record counted twice, and output order must follow input order --
    the CLI's JSON consumers depend on deterministic ordering."""

    def test_mixed_batch_partitions_and_preserves_order(self) -> None:
        baseline_run = [
            _record("unit", "test_a", "AssertionError: boom"),
            _record("unit", "test_b", "ValueError: nope"),
            _record("unit", "test_c", "KeyError: missing"),
        ]
        current_run = [
            _record("unit", "test_c", "KeyError: missing"),
            _record("unit", "test_a", "AssertionError: boom"),
            _record("unit", "test_b", "ValueError: changed"),
            _record("unit", "test_d", "TypeError: unexpected"),
        ]
        result = baseline.classify(baseline_run, current_run)
        assert result["identical"] == [
            _record("unit", "test_c", "KeyError: missing"),
            _record("unit", "test_a", "AssertionError: boom"),
        ]
        assert result["changed"] == [_record("unit", "test_b", "ValueError: changed")]
        assert result["new"] == [_record("unit", "test_d", "TypeError: unexpected")]
        assert result["resolved"] == []
        seen = [
            (r["suite"], r["test_id"])
            for bucket in ("identical", "changed", "new", "resolved")
            for r in result[bucket]
        ]
        assert len(seen) == len(set(seen))


class TestCmdClassify:
    """The CLI seam (`_cmd_classify`) has no coverage until the wiring curd
    registers baseline.py in the .pyz bundle -- lock the stdin-JSON-in /
    JSON-out contract directly here so that wiring lands against a tested
    seam."""

    def test_reads_stdin_and_emits_classification_json(self, monkeypatch, capsys) -> None:
        payload = {
            "baseline": [_record("unit", "test_a", "AssertionError: boom")],
            "current": [_record("unit", "test_a", "AssertionError: boom")],
        }
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        baseline._cmd_classify(argparse.Namespace())
        emitted = json.loads(capsys.readouterr().out)
        assert emitted == baseline.classify(payload["baseline"], payload["current"])

    def test_missing_keys_default_to_empty_lists(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
        baseline._cmd_classify(argparse.Namespace())
        emitted = json.loads(capsys.readouterr().out)
        assert emitted == {"identical": [], "new": [], "changed": [], "resolved": []}

    def test_malformed_stdin_raises_cli_error(self, monkeypatch) -> None:
        # Invalid JSON must hit the same CliError -> exit-2 contract every
        # other seam honours, not a raw traceback.
        monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
        with pytest.raises(baseline.cli.CliError, match="expected a JSON object"):
            baseline._cmd_classify(argparse.Namespace())

    def test_non_object_stdin_raises_cli_error(self, monkeypatch) -> None:
        # A top-level list/scalar parses as valid JSON but has no .get --
        # must still surface as CliError, not an AttributeError traceback.
        monkeypatch.setattr(sys, "stdin", io.StringIO("[1, 2, 3]"))
        with pytest.raises(baseline.cli.CliError, match="expected a JSON object"):
            baseline._cmd_classify(argparse.Namespace())