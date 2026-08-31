"""The stored writer-output corpus, its loader, and the weekly report."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import contract_benchmarks  # noqa: E402
from easy_cheese_schemas.benchmarks import (  # noqa: E402
    BenchmarkReport,
    benchmark_contracts,
)

CORPUS = ROOT / "benchmarks" / "contracts"


def _committed_case(name: str) -> dict[str, object]:
    document = cast(
        object, json.loads((CORPUS / f"{name}.json").read_text(encoding="utf-8"))
    )
    assert isinstance(document, dict)
    return cast("dict[str, object]", document)


def _write(root: Path, filename: str, case: dict[str, object]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _ = (root / filename).write_text(json.dumps(case), encoding="utf-8")


def _valid_case(**overrides: object) -> dict[str, object]:
    return _committed_case("review-result-clean") | overrides


def _invalid_case(**overrides: object) -> dict[str, object]:
    return _committed_case("review-result-host-owned-field") | overrides


def _run(
    root: Path,
) -> tuple[tuple[contract_benchmarks.CorpusCase, ...], BenchmarkReport]:
    cases = contract_benchmarks.load_corpus(root)
    return cases, benchmark_contracts(case.benchmark_input for case in cases)


def test_committed_corpus_replays_to_its_recorded_expectations() -> None:
    """The backward-compat canary: a contract change may not flip stored payloads."""
    cases = contract_benchmarks.load_corpus(CORPUS)
    report = benchmark_contracts(case.benchmark_input for case in cases)

    assert [case.name for case in cases] == [
        "planner-result-complete",
        "planner-result-partial",
        "review-result-clean",
        "review-result-host-owned-field",
    ]
    assert contract_benchmarks.expectation_mismatches(cases, report) == ()
    assert [record.first_pass_valid for record in report.records] == [
        True,
        True,
        True,
        False,
    ]
    assert report.first_pass_validity == 0.75
    assert report.repair_rate == 1.0
    assert contract_benchmarks.corpus_problems(cases, report) == ()


def test_expectation_mismatch_names_the_case_and_both_verdicts(tmp_path: Path) -> None:
    _write(tmp_path, "flipped.json", _valid_case(expect_first_pass_valid=False))
    cases, report = _run(tmp_path)

    assert contract_benchmarks.expectation_mismatches(cases, report) == (
        "review-result-clean: recorded expect_first_pass_valid=false, "
        + "replay produced true",
    )
    assert contract_benchmarks.corpus_problems(cases, report) == (
        "review-result-clean: recorded expect_first_pass_valid=false, "
        + "replay produced true",
    )


def test_budget_is_measured_over_captured_cases_only(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "a-synthetic-invalid.json",
        _invalid_case(name="synthetic-invalid", provenance="synthetic"),
    )
    _write(
        tmp_path,
        "b-captured-valid.json",
        _valid_case(name="captured-valid", provenance="captured"),
    )
    cases, report = _run(tmp_path)

    assert report.first_pass_validity == 0.5
    assert contract_benchmarks.captured_invalid_rate(cases, report) == 0.0
    assert contract_benchmarks.corpus_problems(cases, report) == ()


def test_captured_invalid_rate_is_none_without_captured_cases(tmp_path: Path) -> None:
    _write(tmp_path, "only-synthetic.json", _valid_case())
    cases, report = _run(tmp_path)

    assert contract_benchmarks.captured_invalid_rate(cases, report) is None


def test_captured_breach_over_budget_is_a_problem(tmp_path: Path) -> None:
    for index in range(9):
        _write(
            tmp_path,
            f"valid-{index}.json",
            _valid_case(name=f"captured-valid-{index}", provenance="captured"),
        )
    _write(
        tmp_path,
        "z-invalid.json",
        _invalid_case(name="captured-invalid", provenance="captured"),
    )
    cases, report = _run(tmp_path)

    assert contract_benchmarks.captured_invalid_rate(cases, report) == pytest.approx(0.1)
    assert contract_benchmarks.corpus_problems(cases, report) == ()

    _write(
        tmp_path,
        "z-invalid-2.json",
        _invalid_case(name="captured-invalid-2", provenance="captured"),
    )
    cases, report = _run(tmp_path)

    assert contract_benchmarks.captured_invalid_rate(cases, report) == pytest.approx(
        2 / 11
    )
    assert contract_benchmarks.corpus_problems(cases, report) == (
        "captured first-pass invalid rate 18.2% exceeds the 10% budget",
    )


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ({"surprise": 1}, "unknown keys: surprise"),
        ({"provenance": "guessed"}, "provenance must be one of captured, synthetic"),
        ({"expect_first_pass_valid": "yes"}, "expect_first_pass_valid must be a boolean"),
        ({"name": "   "}, "name must be a non-empty string"),
        ({"invocation": []}, "invocation must be an object"),
        ({"repair_view": {}}, "repair_view is unreachable"),
    ],
)
def test_malformed_cases_are_rejected_before_the_harness(
    tmp_path: Path, case: dict[str, object], message: str
) -> None:
    _write(tmp_path, "case.json", _valid_case(**case))

    with pytest.raises(contract_benchmarks.CorpusError) as error:
        _ = contract_benchmarks.load_corpus(tmp_path)

    assert message in str(error.value)
    assert str(error.value).startswith("case.json: ")


def test_missing_keys_are_named_in_the_rejection(tmp_path: Path) -> None:
    _write(tmp_path, "case.json", {"name": "sparse", "provenance": "synthetic"})

    with pytest.raises(contract_benchmarks.CorpusError) as error:
        _ = contract_benchmarks.load_corpus(tmp_path)

    assert str(error.value) == (
        "case.json: missing keys: expect_first_pass_valid, invocation, source, "
        "writer_view"
    )


def test_duplicate_case_names_are_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "one.json", _valid_case(name="twin"))
    _write(tmp_path, "two.json", _valid_case(name="twin"))

    with pytest.raises(contract_benchmarks.CorpusError) as error:
        _ = contract_benchmarks.load_corpus(tmp_path)

    assert str(error.value) == "duplicate case names: twin"


def test_invalid_json_and_empty_directories_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(contract_benchmarks.CorpusError) as empty:
        _ = contract_benchmarks.load_corpus(tmp_path)
    assert str(empty.value) == f"corpus directory holds no cases: {tmp_path}"

    missing = tmp_path / "absent"
    with pytest.raises(contract_benchmarks.CorpusError) as gone:
        _ = contract_benchmarks.load_corpus(missing)
    assert str(gone.value) == f"corpus directory not found: {missing}"

    _ = (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    with pytest.raises(contract_benchmarks.CorpusError) as broken:
        _ = contract_benchmarks.load_corpus(tmp_path)
    assert str(broken.value).startswith("broken.json: invalid JSON: ")


def test_report_states_the_budget_status_and_every_case(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "a-captured.json",
        _invalid_case(name="captured-invalid", provenance="captured"),
    )
    _write(tmp_path, "b-synthetic.json", _valid_case(name="synthetic-valid"))
    cases, report = _run(tmp_path)

    rendered = contract_benchmarks.render_report(cases, report, tmp_path)

    assert rendered.startswith("## Contract validity benchmark\n")
    assert f"Corpus: `{tmp_path}` — 2 cases (1 captured, 1 synthetic)" in rendered
    assert "| First-pass validity (all cases) | 50.0% |" in rendered
    assert "| Repair success among attempts | 100.0% |" in rendered
    assert "| Largest canonical payload | 267 bytes |" in rendered
    assert "Budget: captured writer output stays under 10% first-pass invalid." in rendered
    assert (
        "Status: NOT MET — 100.0% of 1 captured cases were first-pass invalid"
        in rendered
    )
    assert "| captured-invalid | captured | invalid | repaired | 99 | 267 |" in rendered
    assert "| synthetic-valid | synthetic | valid | — | 73 | 267 |" in rendered
    assert rendered.endswith(
        "### Problems\n\n"
        + "- captured first-pass invalid rate 100.0% exceeds the 10% budget\n"
    )


def test_report_reports_no_repairs_and_no_captured_cases(tmp_path: Path) -> None:
    _write(tmp_path, "only.json", _valid_case())
    cases, report = _run(tmp_path)

    rendered = contract_benchmarks.render_report(cases, report, tmp_path)

    assert "| Repair success among attempts | n/a (none attempted) |" in rendered
    assert (
        "Status: not measurable — the corpus holds no captured cases yet "
        + "(easy-cheese#406)" in rendered
    )
    assert "### Problems" not in rendered


def test_main_publishes_the_committed_report_and_exits_clean(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert contract_benchmarks.main([]) == 0

    captured = capsys.readouterr()
    assert "Corpus: `benchmarks/contracts` — 4 cases (0 captured, 4 synthetic)" in (
        captured.out
    )
    assert "| First-pass validity (all cases) | 75.0% |" in captured.out
    assert "| Largest canonical payload | 2,070 bytes |" in captured.out
    assert captured.err == ""


def test_main_exits_one_on_a_problem_and_two_on_a_broken_corpus(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, "flipped.json", _valid_case(expect_first_pass_valid=False))

    assert contract_benchmarks.main(["--corpus", str(tmp_path)]) == 1
    problem = capsys.readouterr()
    assert "### Problems" in problem.out
    assert problem.err == (
        "contract_benchmarks: review-result-clean: recorded "
        "expect_first_pass_valid=false, replay produced true\n"
    )

    assert contract_benchmarks.main(["--corpus", str(tmp_path / "absent")]) == 2
    broken = capsys.readouterr()
    assert broken.out == ""
    assert broken.err.startswith("contract_benchmarks: corpus directory not found: ")
