"""The run ledger as a spend gate (#549).

`references/budgets.md` gives an invocation a soft call budget and exactly one
way past it — record the evidence gap that forces the extra calls. These pin the
five checks that make that prose mechanical: a run may not re-issue a search it
already ran, re-extract a URL it already stored, cite the debris of a failed
call, invent an extension reason, or overspend silently.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.skills.briesearch import budget
from easy_cheese.skills.briesearch.ledger import (
    EVIDENCE_GAPS,
    LedgerError,
    parse_ledger,
)


def _search(query: str, **overrides: object) -> dict[str, object]:
    call: dict[str, object] = {
        "kind": "search",
        "provider": "tavily",
        "tool": "tavily_search",
        "query": query,
        "status": "ok",
    }
    call.update(overrides)
    return call


def _extract(url: str, **overrides: object) -> dict[str, object]:
    call: dict[str, object] = {
        "kind": "extract",
        "provider": "tavily",
        "tool": "tavily_extract",
        "url": url,
        "file": "raw/01-example.md",
        "status": "ok",
    }
    call.update(overrides)
    return call


def _findings(document: object) -> list[tuple[str, str]]:
    report = budget.check_ledger(parse_ledger(document))
    return [(f.kind, f.message) for f in report.findings]


def _kinds(document: object) -> list[str]:
    return [kind for kind, _ in _findings(document)]


def _metrics(document: object) -> dict[str, object]:
    return budget.check_ledger(parse_ledger(document)).metrics


# --- DUPLICATE_SEARCH -------------------------------------------------------


def test_identical_search_repeated_is_a_duplicate() -> None:
    kinds = _kinds({"calls": [_search("rrf fusion k"), _search("rrf fusion k")]})
    assert kinds == ["DUPLICATE_SEARCH"]


def test_duplicate_search_names_the_call_it_repeats() -> None:
    findings = _findings(
        {"calls": [_search("a"), _search("b"), _search("a")]}
    )
    assert len(findings) == 1
    assert "call 3 (tavily tavily_search) repeats call 1" in findings[0][1]


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("rrf fusion k", "RRF Fusion K"),
        ("rrf fusion k", "  rrf   fusion\tk "),
    ],
)
def test_case_and_whitespace_do_not_make_a_query_new(first: str, second: str) -> None:
    assert _kinds({"calls": [_search(first), _search(second)]}) == ["DUPLICATE_SEARCH"]


def test_filters_are_compared_by_value_not_key_order() -> None:
    document = {
        "calls": [
            _search("q", filters={"days": 30, "depth": "advanced"}),
            _search("q", filters={"depth": "advanced", "days": 30}),
        ]
    }
    assert _kinds(document) == ["DUPLICATE_SEARCH"]


def test_different_filters_make_the_same_query_a_different_search() -> None:
    document = {
        "calls": [
            _search("q", filters={"days": 30}),
            _search("q", filters={"days": 7}),
        ]
    }
    assert _kinds(document) == []


def test_empty_filters_match_absent_filters() -> None:
    assert _kinds({"calls": [_search("q", filters={}), _search("q")]}) == [
        "DUPLICATE_SEARCH"
    ]


def test_a_different_provider_running_the_same_query_is_not_a_duplicate() -> None:
    document = {
        "calls": [_search("q"), _search("q", provider="exa", tool="web_search_exa")]
    }
    assert _kinds(document) == []


def test_retrying_a_failed_search_is_not_a_duplicate() -> None:
    """Both calls must have succeeded: a retry after a timeout is the run
    recovering, not the run repeating itself."""
    document = {"calls": [_search("q", status="timeout"), _search("q")]}
    assert _kinds(document) == []


# --- DUPLICATE_EXTRACT ------------------------------------------------------


def test_re_extracting_a_stored_url_is_a_duplicate() -> None:
    document = {
        "calls": [_extract("https://example.com/a"), _extract("https://example.com/a")]
    }
    assert _kinds(document) == ["DUPLICATE_EXTRACT"]


def test_duplicate_extract_sees_through_url_spellings() -> None:
    document = {
        "calls": [
            _extract("https://Example.com/a"),
            _extract("https://example.com/a/#top"),
        ]
    }
    assert _kinds(document) == ["DUPLICATE_EXTRACT"]


def test_a_declared_refresh_is_not_a_duplicate() -> None:
    document = {
        "calls": [
            _extract("https://example.com/a"),
            _extract("https://example.com/a", refresh=True),
        ]
    }
    assert _kinds(document) == []


def test_distinct_urls_are_not_duplicates() -> None:
    document = {
        "calls": [_extract("https://example.com/a"), _extract("https://example.com/b")]
    }
    assert _kinds(document) == []


# --- FAILED_EVIDENCE --------------------------------------------------------


def test_a_failed_call_that_stored_a_body_is_reported() -> None:
    findings = _findings(
        {"calls": [_extract("https://example.com/a", status="403")]}
    )
    assert [kind for kind, _ in findings] == ["FAILED_EVIDENCE"]
    assert "raw/01-example.md" in findings[0][1]


def test_a_failed_call_with_no_stored_body_is_clean() -> None:
    document = {"calls": [_extract("https://example.com/a", status="403", file="")]}
    assert _kinds(document) == []
    assert _metrics(document)["failed"] == 1


# --- EXTENSION_GAP ----------------------------------------------------------


@pytest.mark.parametrize("gap", sorted(EVIDENCE_GAPS))
def test_every_recognised_gap_is_accepted(gap: str) -> None:
    assert _kinds({"extensions": [{"gap": gap, "note": "why"}]}) == []


def test_an_unrecognised_gap_is_reported() -> None:
    findings = _findings({"extensions": [{"gap": "wanted-more-sources"}]})
    assert [kind for kind, _ in findings] == ["EXTENSION_GAP"]
    assert "no-primary-source" in findings[0][1]


def test_an_extension_without_a_gap_is_a_corrupt_manifest() -> None:
    with pytest.raises(LedgerError, match="extensions\\[0\\] is missing required field 'gap'"):
        _ = parse_ledger({"extensions": [{"note": "why"}]})


# --- BUDGET -----------------------------------------------------------------


def test_overspending_with_no_extension_is_reported() -> None:
    document = {
        "budget": {"search": 1},
        "calls": [_search("a"), _search("b")],
    }
    findings = _findings(document)
    assert [kind for kind, _ in findings] == ["BUDGET"]
    assert "2 search call(s) against a declared budget of 1" in findings[0][1]


def test_spending_exactly_the_budget_is_clean() -> None:
    document = {"budget": {"search": 2}, "calls": [_search("a"), _search("b")]}
    assert _kinds(document) == []


def test_a_recognised_extension_buys_the_overspend() -> None:
    document = {
        "budget": {"search": 1},
        "extensions": [{"gap": "unresolved-contradiction", "note": "docs disagree"}],
        "calls": [_search("a"), _search("b")],
    }
    assert _kinds(document) == []


def test_an_unrecognised_gap_buys_nothing() -> None:
    """The escape hatch has to name one of the five, or it is just free text
    that would defeat the budget it claims to extend."""
    document = {
        "budget": {"search": 1},
        "extensions": [{"gap": "wanted-more-sources"}],
        "calls": [_search("a"), _search("b")],
    }
    assert _kinds(document) == ["EXTENSION_GAP", "BUDGET"]


def test_the_budget_is_per_kind() -> None:
    document = {
        "budget": {"search": 1, "extract": 1},
        "calls": [_search("a"), _search("b"), _extract("https://example.com/a")],
    }
    assert _kinds(document) == ["BUDGET"]


# --- metrics ----------------------------------------------------------------


def test_metrics_report_the_whole_run() -> None:
    document = {
        "invocation": "sidechain",
        "budget": {"search": 1},
        "extensions": [{"gap": "missing-freshness", "note": "all 2023"}],
        "calls": [
            _search("a"),
            _search("a"),
            _search("b", cached=True),
            _extract("https://example.com/a"),
            _extract("https://example.com/a"),
            _extract("https://example.com/b", status="403", file=""),
            {"kind": "spawn", "provider": "researcher", "status": "ok"},
        ],
    }
    assert _metrics(document) == {
        "invocation": "sidechain",
        "calls": {"extract": 3, "search": 3, "spawn": 1},
        "duplicates": {"search": 1, "extract": 1},
        "cached": 1,
        "failed": 1,
        "budget": {"search": 1},
        "extensions": [{"gap": "missing-freshness", "note": "all 2023"}],
    }


def test_an_empty_ledger_reports_zeroed_metrics() -> None:
    assert _metrics({}) == {
        "invocation": "top-level",
        "calls": {"extract": 0, "search": 0, "spawn": 0},
        "duplicates": {"search": 0, "extract": 0},
        "cached": 0,
        "failed": 0,
        "budget": {},
        "extensions": [],
    }


# --- ledger trust boundary --------------------------------------------------


def test_filters_must_be_an_object() -> None:
    with pytest.raises(LedgerError, match="field 'filters' must be a JSON object"):
        _ = parse_ledger({"calls": [_search("q", filters=["days"])]})


def test_cached_must_be_a_boolean() -> None:
    with pytest.raises(LedgerError, match="field 'cached' must be true or false"):
        _ = parse_ledger({"calls": [_search("q", cached="yes")]})


# --- CLI --------------------------------------------------------------------


def _write_manifest(directory: Path, document: object) -> Path:
    _ = (directory / "manifest.json").write_text(
        json.dumps(document), encoding="utf-8"
    )
    return directory


def test_main_accepts_the_research_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _ = _write_manifest(tmp_path, {"calls": [_search("q")]})
    assert budget.main([str(tmp_path)]) == 0
    metrics = cast("dict[str, object]", json.loads(capsys.readouterr().out))
    assert metrics["calls"] == {"extract": 0, "search": 1, "spawn": 0}


def test_main_accepts_the_manifest_file(tmp_path: Path) -> None:
    _ = _write_manifest(tmp_path, {"calls": [_search("q")]})
    assert budget.main([str(tmp_path / "manifest.json")]) == 0


def test_main_fails_on_a_violation_but_still_prints_metrics(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _ = _write_manifest(tmp_path, {"calls": [_search("q"), _search("q")]})
    assert budget.main([str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out)["duplicates"]["search"] == 1
    assert "ERROR DUPLICATE_SEARCH" in captured.err


def test_main_rejects_an_untrusted_manifest(tmp_path: Path) -> None:
    _ = _write_manifest(tmp_path, {"calls": [{"kind": "conjure", "provider": "x"}]})
    assert budget.main([str(tmp_path)]) == 1


def test_main_reports_a_missing_manifest_as_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert budget.main([str(tmp_path)]) == 2
    assert "no manifest.json found" in capsys.readouterr().err
