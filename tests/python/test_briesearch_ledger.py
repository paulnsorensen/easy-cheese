"""The capture manifest as a machine-read ledger (#493).

`references/context-isolation.md` always told /briesearch to write a
`manifest.json` beside a deep report, but nothing read it back, so "verify then
cite" was unauditable: a URL that only appeared in a search result list could be
cited as though a provider retrieval tool had opened it. These pin the parser's
trust boundary and the ground-check REMOTE rule built on it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from easy_cheese.skills.briesearch import ground_check
from easy_cheese.skills.briesearch.ledger import (
    Call,
    Ledger,
    LedgerError,
    canonical_url,
    find_ledger,
    load_ledger,
    parse_ledger,
    render_url,
    url_digest,
)


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


@pytest.mark.parametrize(
    ("written", "cited"),
    [
        ("https://Example.COM/a", "https://example.com/a"),
        ("https://example.com", "https://example.com/"),
        ("http://example.com:80/a", "http://example.com/a"),
        ("https://example.com/a#section", "https://example.com/a"),
    ],
)
def test_canonical_url_collapses_spellings_of_one_resource(
    written: str, cited: str
) -> None:
    assert canonical_url(written) == canonical_url(cited)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("https://example.com/a", "https://example.com/a/"),
        ("https://example.com/a", "https://example.com/b"),
        ("https://example.com/a?v=1", "https://example.com/a?v=2"),
        ("https://example.com/a", "http://example.com/a"),
        ("https://example.com/a", "https://www.example.com/a"),
    ],
)
def test_canonical_url_keeps_distinct_resources_distinct(left: str, right: str) -> None:
    # Dedup that merged these would merge distinct evidence — the #549 non-goal.
    assert canonical_url(left) != canonical_url(right)


def test_parse_ledger_rejects_unknown_call_kind() -> None:
    with pytest.raises(LedgerError, match="unknown kind 'crawl'"):
        _ = parse_ledger({"calls": [{"kind": "crawl", "provider": "tavily"}]})


def test_parse_ledger_requires_url_on_an_extraction() -> None:
    with pytest.raises(LedgerError, match="calls\\[0\\] is missing required .*'url'"):
        _ = parse_ledger(
            {"calls": [{"kind": "extract", "provider": "exa", "tool": "contents"}]}
        )


def test_parse_ledger_rejects_url_user_information() -> None:
    with pytest.raises(LedgerError, match="user information"):
        _ = parse_ledger(
            {"calls": [_extract("https://alice:secret@example.com/private")]}
        )


def test_parse_ledger_rejects_persisted_query_values() -> None:
    raw = "https://example.com/private?token=secret#details"
    with pytest.raises(LedgerError, match="must omit query values"):
        _ = parse_ledger({"calls": [_extract(raw, url_digest=url_digest(raw))]})


def test_redacted_url_and_full_digest_correlate(tmp_path: Path) -> None:
    raw = "https://example.com/a?token=secret"
    safe = render_url(raw)
    ledger = parse_ledger(
        {"calls": [_extract(safe, url_digest=url_digest(raw))]}
    )
    call = ledger.calls[0]
    assert call.url == safe
    assert call.url_digest == url_digest(raw)
    assert url_digest(safe) in ledger.retrieved()
    violations, tables = ground_check.check_report(
        _REPORT, tmp_path, tmp_path, ledger
    )
    assert tables == 1
    assert violations == []


def test_parse_ledger_requires_the_provider_tool_that_ran() -> None:
    # #493's core: "Tavily" is not evidence of anything; `tavily_extract` is.
    with pytest.raises(LedgerError, match="calls\\[0\\] is missing required .*'tool'"):
        _ = parse_ledger(
            {"calls": [{"kind": "search", "provider": "tavily", "query": "rrf"}]}
        )


def test_parse_ledger_rejects_unknown_invocation_class() -> None:
    with pytest.raises(LedgerError, match="must be sidechain or top-level"):
        _ = parse_ledger({"invocation": "nested", "calls": []})


def test_parse_ledger_rejects_non_array_calls() -> None:
    with pytest.raises(LedgerError, match="'calls' must be a JSON array"):
        _ = parse_ledger({"calls": {"kind": "search"}})


def test_retrieved_excludes_failed_and_search_only_urls() -> None:
    ledger = parse_ledger(
        {
            "calls": [
                _extract("https://ok.example/a"),
                _extract("https://dead.example/b", status="error", file=""),
                {
                    "kind": "search",
                    "provider": "tavily",
                    "tool": "tavily_search",
                    "query": "rrf fusion",
                },
            ]
        }
    )
    assert set(ledger.retrieved()) == {url_digest("https://ok.example/a")}


def test_load_ledger_rejects_malformed_json(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    _ = manifest.write_text("{not json", encoding="utf-8")
    with pytest.raises(LedgerError, match="not valid JSON"):
        _ = load_ledger(manifest)


def test_find_ledger_returns_none_without_a_manifest(tmp_path: Path) -> None:
    assert find_ledger(tmp_path) is None


_REPORT = """## Research: q

| Claim | Evidence | Confidence |
| --- | --- | --- |
| A holds | [^s1] | certain |

## References
[^s1]: https://example.com/a (fetched 2026-08-30).
"""


def _kinds(violations: list[ground_check.Violation]) -> list[tuple[str, str]]:
    return [(v.level, v.kind) for v in violations]


def test_cited_url_absent_from_the_ledger_is_an_error(tmp_path: Path) -> None:
    ledger = parse_ledger({"calls": [_extract("https://example.com/other")]})
    violations, tables = ground_check.check_report(_REPORT, tmp_path, tmp_path, ledger)
    assert tables == 1
    assert _kinds(violations) == [("error", "REMOTE")]
    assert "https://example.com/a" in violations[0].message


def test_cited_url_retrieved_by_a_provider_tool_passes(tmp_path: Path) -> None:
    # URL identity ignores host case but preserves the resource path.
    ledger = parse_ledger({"calls": [_extract("https://Example.com/a")]})
    violations, _ = ground_check.check_report(_REPORT, tmp_path, tmp_path, ledger)
    assert violations == []


def test_url_only_discovered_by_search_does_not_count_as_retrieved(
    tmp_path: Path,
) -> None:
    """A search result list is discovery, not inspection — routing.md § Verify then
    cite requires the provider's retrieval tool to have opened the page."""
    ledger = parse_ledger(
        {
            "calls": [
                {
                    "kind": "search",
                    "provider": "tavily",
                    "tool": "tavily_search",
                    "query": "example a",
                    "url": "https://example.com/a",
                }
            ]
        }
    )
    violations, _ = ground_check.check_report(_REPORT, tmp_path, tmp_path, ledger)
    assert _kinds(violations) == [("error", "REMOTE")]


def test_failed_retrieval_cannot_ground_a_citation(tmp_path: Path) -> None:
    ledger = parse_ledger(
        {"calls": [_extract("https://example.com/a", status="timeout", file="")]}
    )
    violations, _ = ground_check.check_report(_REPORT, tmp_path, tmp_path, ledger)
    assert _kinds(violations) == [("error", "REMOTE")]


def test_missing_manifest_degrades_to_one_advisory(tmp_path: Path) -> None:
    """Short-form reports have no capture directory; the gate must stay usable and
    say plainly that the remote citations went unverified."""
    violations, _ = ground_check.check_report(_REPORT, tmp_path, tmp_path, None)
    assert _kinds(violations) == [("advisory", "MANIFEST")]
    assert "1 remote URL citation(s)" in violations[0].message


def test_local_only_report_gets_no_manifest_advisory(tmp_path: Path) -> None:
    _ = (tmp_path / "source.py").write_text("x\n" * 20, encoding="utf-8")
    body = (
        "## Research: q\n\n| Claim | Evidence | Confidence |\n| --- | --- | --- |\n"
        "| A holds | source.py:12 | certain |\n"
    )
    violations, _ = ground_check.check_report(body, tmp_path, tmp_path, None)
    assert violations == []


def test_main_reads_the_manifest_beside_the_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "slug.md"
    _ = report.write_text(_REPORT, encoding="utf-8")
    _ = (tmp_path / "manifest.json").write_text(
        json.dumps({"calls": [_extract("https://example.com/a")]}), encoding="utf-8"
    )
    assert ground_check.main([str(report)]) == 0
    assert "MANIFEST" not in capsys.readouterr().err


def test_main_fails_on_an_unreadable_manifest(tmp_path: Path) -> None:
    report = tmp_path / "slug.md"
    _ = report.write_text(_REPORT, encoding="utf-8")
    _ = (tmp_path / "manifest.json").write_text("[]", encoding="utf-8")
    assert ground_check.main([str(report)]) == 1


def test_citation_scanner_keeps_balanced_parentheses(tmp_path: Path) -> None:
    url = "https://example.com/wiki/Foo_(bar)"
    report = (
        "## Research: q\n\n| Claim | Evidence | Confidence |\n| --- | --- | --- |\n"
        f"| A holds | {url} | certain |\n"
    )
    ledger = parse_ledger({"calls": [_extract(url)]})
    violations, tables = ground_check.check_report(report, tmp_path, tmp_path, ledger)
    assert tables == 1
    assert violations == []


def test_citation_scanner_rejects_url_user_information(tmp_path: Path) -> None:
    report = (
        "## Research: q\n\n| Claim | Evidence | Confidence |\n| --- | --- | --- |\n"
        "| A holds | https://alice:secret@example.com/private?token=secret | certain |\n"
    )
    violations, _ = ground_check.check_report(report, tmp_path, tmp_path, None)
    assert any(v.kind == "REMOTE" and v.level == "error" for v in violations)
    rendered = "\n".join(v.render() for v in violations)
    assert "alice" not in rendered
    assert "secret" not in rendered


def test_report_builds_retrieved_map_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ledger = parse_ledger({"calls": [_extract("https://example.com/a")]})
    calls = 0
    original = Ledger.retrieved

    def counted(current: Ledger) -> dict[str, Call]:
        nonlocal calls
        calls += 1
        return original(current)

    monkeypatch.setattr(Ledger, "retrieved", counted)
    report = _REPORT.replace(
        "| A holds | [^s1] | certain |",
        "| A holds | [^s1] | certain |\n| B holds | [^s1] | certain |",
    )
    _ = ground_check.check_report(report, tmp_path, tmp_path, ledger)
    assert calls == 1


def test_main_fails_on_a_mismatched_adjacent_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "slug.md"
    _ = report.write_text(_REPORT, encoding="utf-8")
    _ = (tmp_path / "manifest.json").write_text(
        json.dumps({"calls": [_extract("https://example.com/other")]}),
        encoding="utf-8",
    )
    assert ground_check.main([str(report)]) == 1
    assert "REMOTE" in capsys.readouterr().err


def test_main_reports_manifest_missing_from_report_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    report = report_dir / "slug.md"
    _ = report.write_text(_REPORT, encoding="utf-8")
    _ = (tmp_path / "manifest.json").write_text(
        json.dumps({"calls": [_extract("https://example.com/a")]}),
        encoding="utf-8",
    )
    assert ground_check.main([str(report)]) == 0
    assert "MANIFEST" in capsys.readouterr().err


def _table(evidence: str, confidence: str = "certain", freshness: str = "") -> str:
    """One evidence table, with the optional Freshness column when asked."""
    if freshness:
        return (
            "## Research: q\n\n"
            "| Claim | Evidence | Freshness | Confidence |\n"
            "| --- | --- | --- | --- |\n"
            f"| A holds | {evidence} | {freshness} | {confidence} |\n"
        )
    return (
        "## Research: q\n\n"
        "| Claim | Evidence | Confidence |\n| --- | --- | --- |\n"
        f"| A holds | {evidence} | {confidence} |\n"
    )


@pytest.mark.parametrize(
    ("cited", "part"),
    [
        ("https://example.com/a?token=secret", "query value"),
        ("https://user:pw@example.com/a", "user information"),
        ("https://example.com/a#tail", "fragment"),
    ],
)
def test_a_signed_citation_is_rejected_before_the_digest_match(
    tmp_path: Path, cited: str, part: str
) -> None:
    """`safety.md` § Protect URL credentials forbids a persisted query value. The
    manifest digest covers the full URL, so a digest match alone would accept a
    signed URL into the report."""
    ledger = parse_ledger({"calls": [_extract("https://example.com/a")]})
    violations, _ = ground_check.check_report(_table(cited), tmp_path, tmp_path, ledger)
    assert _kinds(violations) == [("error", "REMOTE")]
    assert part in violations[0].message
    assert "secret" not in violations[0].message


def test_a_raw_capture_anchor_uses_the_hash_l_form(tmp_path: Path) -> None:
    """`context-isolation.md` § The recipe cites `raw/NN-host.md#Lstart-end`."""
    raw = tmp_path / "raw"
    raw.mkdir()
    _ = (raw / "01-example.md").write_text("a\nb\nc\n", encoding="utf-8")
    violations, _ = ground_check.check_report(
        _table("raw/01-example.md#L1-2"), tmp_path, tmp_path, None
    )
    assert violations == []


def test_an_out_of_range_raw_anchor_is_an_error(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    _ = (raw / "01-example.md").write_text("a\nb\n", encoding="utf-8")
    violations, _ = ground_check.check_report(
        _table("raw/01-example.md#L1-9"), tmp_path, tmp_path, None
    )
    assert _kinds(violations) == [("error", "LOCAL_PATH")]


def test_an_inline_path_that_does_not_exist_is_an_error(tmp_path: Path) -> None:
    violations, _ = ground_check.check_report(
        _table("missing.py:999999"), tmp_path, tmp_path, None
    )
    assert _kinds(violations) == [("error", "LOCAL_PATH")]
    assert "missing.py" in violations[0].message


def test_an_inline_path_outside_the_invocation_root_is_an_error(
    tmp_path: Path,
) -> None:
    inner = tmp_path / "inner"
    inner.mkdir()
    violations, _ = ground_check.check_report(
        _table("../outside.py:1"), inner, inner, None
    )
    assert _kinds(violations) == [("error", "LOCAL_PATH")]
    assert "outside allowed root" in violations[0].message


def test_a_url_path_is_not_read_as_a_local_file(tmp_path: Path) -> None:
    ledger = parse_ledger({"calls": [_extract("https://example.com/pkg/mod.py")]})
    violations, _ = ground_check.check_report(
        _table("https://example.com/pkg/mod.py"), tmp_path, tmp_path, ledger
    )
    assert violations == []


def test_an_escaped_pipe_does_not_shift_the_confidence_column(tmp_path: Path) -> None:
    """A claim that contains an escaped pipe must keep its own confidence cell."""
    body = (
        "## Research: q\n\n"
        "| Claim | Evidence | Confidence |\n| --- | --- | --- |\n"
        "| A \\| B holds | https://example.com/a | certain |\n"
    )
    ledger = parse_ledger({"calls": [_extract("https://example.com/a")]})
    violations, _ = ground_check.check_report(body, tmp_path, tmp_path, ledger)
    assert violations == []


def test_a_case_variant_confidence_label_is_rejected(tmp_path: Path) -> None:
    """`synthesis.md` calls these exact label values."""
    ledger = parse_ledger({"calls": [_extract("https://example.com/a")]})
    violations, _ = ground_check.check_report(
        _table("https://example.com/a", confidence="CERTAIN"),
        tmp_path,
        tmp_path,
        ledger,
    )
    assert _kinds(violations) == [("error", "CONFIDENCE")]


def test_a_manifest_slug_must_name_its_own_report(tmp_path: Path) -> None:
    ledger = parse_ledger(
        {"slug": "another-run-entirely-here", "calls": [_extract("https://e.com/a")]}
    )
    violations, _ = ground_check.check_report(
        _table("https://e.com/a"), tmp_path, tmp_path, ledger, "this-report-slug"
    )
    assert _kinds(violations) == [("error", "MANIFEST")]
    assert "another-run-entirely-here" in violations[0].message


def test_a_successful_capture_must_store_a_confined_raw_body(tmp_path: Path) -> None:
    ledger = parse_ledger({"calls": [_extract("https://example.com/a", file="")]})
    violations, _ = ground_check.check_report(
        _table("https://example.com/a"), tmp_path, tmp_path, ledger
    )
    assert _kinds(violations) == [("error", "MANIFEST")]
    assert "stored no raw body" in violations[0].message


def test_a_capture_stored_outside_the_raw_directory_is_an_error(
    tmp_path: Path,
) -> None:
    ledger = parse_ledger(
        {"calls": [_extract("https://example.com/a", file="../escape.md")]}
    )
    violations, _ = ground_check.check_report(
        _table("https://example.com/a"), tmp_path, tmp_path, ledger
    )
    assert _kinds(violations) == [("error", "MANIFEST")]
    assert "outside the raw capture" in violations[0].message


def test_a_row_date_must_match_the_manifest_fetch_date(tmp_path: Path) -> None:
    ledger = parse_ledger(
        {"calls": [_extract("https://example.com/a", fetched="2020-01-01")]}
    )
    violations, _ = ground_check.check_report(
        _table("https://example.com/a", freshness="2026-08-30"),
        tmp_path,
        tmp_path,
        ledger,
    )
    assert _kinds(violations) == [("error", "FRESHNESS")]
    assert "2020-01-01" in violations[0].message


def test_a_row_date_equal_to_the_fetch_date_passes(tmp_path: Path) -> None:
    ledger = parse_ledger(
        {"calls": [_extract("https://example.com/a", fetched="2026-08-30")]}
    )
    violations, _ = ground_check.check_report(
        _table("https://example.com/a", freshness="2026-08-30"),
        tmp_path,
        tmp_path,
        ledger,
    )
    assert violations == []


def test_parse_ledger_rejects_an_unparsable_fetch_date() -> None:
    with pytest.raises(LedgerError, match="ISO YYYY-MM-DD"):
        _ = parse_ledger({"calls": [_extract("https://e.com/a", fetched="Aug 2026")]})


def test_parse_ledger_retains_the_slug_title_and_fetch_date() -> None:
    ledger = parse_ledger(
        {
            "slug": "hybrid-retrieval-fusion-study",
            "calls": [_extract("https://e.com/a", title="A", fetched="2026-08-30")],
        }
    )
    assert ledger.slug == "hybrid-retrieval-fusion-study"
    assert (ledger.calls[0].title, ledger.calls[0].fetched) == ("A", "2026-08-30")
