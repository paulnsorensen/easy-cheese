"""Tests for skills/cheez-search/scripts/pick_kind.py.

Covers the decision table (each kind, escalate, imports hint), the
CLI entry (subprocess with --json), and the missing --query path.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import build_pyz  # noqa: E402

BUNDLE = build_pyz.cached_bundle("cheez-search")


class TestDecideSymbol:
    def test_pure_snake_case_identifier(self, pick_kind: ModuleType) -> None:
        assert pick_kind.decide("foo_bar") == {"query": "foo_bar", "kind": "symbol"}

    def test_camel_case_class_name(self, pick_kind: ModuleType) -> None:
        assert pick_kind.decide("MyClass") == {"query": "MyClass", "kind": "symbol"}

    def test_identifier_with_digits(self, pick_kind: ModuleType) -> None:
        assert pick_kind.decide("handle42") == {"query": "handle42", "kind": "symbol"}

    def test_leading_underscore_identifier(self, pick_kind: ModuleType) -> None:
        assert pick_kind.decide("_private") == {"query": "_private", "kind": "symbol"}


class TestDecideContent:
    def test_double_quoted_literal_phrase(self, pick_kind: ModuleType) -> None:
        result = pick_kind.decide('"some literal phrase"')
        assert result == {"query": "some literal phrase", "kind": "content"}

    def test_single_quoted_literal_phrase(self, pick_kind: ModuleType) -> None:
        result = pick_kind.decide("'TODO: fix this'")
        assert result == {"query": "TODO: fix this", "kind": "content"}

    def test_unquoted_sentence_with_spaces(self, pick_kind: ModuleType) -> None:
        result = pick_kind.decide("invalid token format")
        assert result == {"query": "invalid token format", "kind": "content"}


class TestDecideRegex:
    def test_slashed_regex_strips_delimiters(self, pick_kind: ModuleType) -> None:
        assert pick_kind.decide("/regex.*/") == {"query": "regex.*", "kind": "regex"}

    def test_slashed_regex_with_flags(self, pick_kind: ModuleType) -> None:
        result = pick_kind.decide("/FIXME.*/i")
        assert result == {"query": "FIXME.*", "kind": "regex"}

    def test_bare_regex_with_backslash_d(self, pick_kind: ModuleType) -> None:
        result = pick_kind.decide(r"rate\d+limit")
        assert result == {"query": r"rate\d+limit", "kind": "regex"}

    def test_bare_regex_with_negated_class(self, pick_kind: ModuleType) -> None:
        result = pick_kind.decide("[^abc]xyz")
        assert result == {"query": "[^abc]xyz", "kind": "regex"}


class TestDecideCallers:
    def test_callers_of_phrasing(self, pick_kind: ModuleType) -> None:
        result = pick_kind.decide("callers of validateToken")
        assert result == {"query": "validateToken", "kind": "callers"}

    def test_who_calls_phrasing(self, pick_kind: ModuleType) -> None:
        result = pick_kind.decide("who calls handleAuth")
        assert result == {"query": "handleAuth", "kind": "callers"}

    def test_what_calls_phrasing_case_insensitive(self, pick_kind: ModuleType) -> None:
        result = pick_kind.decide("What Calls Refresh")
        assert result == {"query": "Refresh", "kind": "callers"}


class TestDecideEscalate:
    def test_ast_metavar_with_dollar_x(self, pick_kind: ModuleType) -> None:
        result = pick_kind.decide("$X.method()")
        assert result["escalate"] is True
        assert result["query"] == "$X.method()"
        assert result["reason"].startswith("ast-shape")

    def test_ast_metavar_named(self, pick_kind: ModuleType) -> None:
        result = pick_kind.decide("$FOO.bar($$$ARGS)")
        assert result["escalate"] is True
        assert result["reason"].startswith("ast-shape")

    def test_ast_triple_dollar_body(self, pick_kind: ModuleType) -> None:
        result = pick_kind.decide("function $NAME() { $$$BODY }")
        assert result["escalate"] is True
        assert result["reason"].startswith("ast-shape")

    def test_ast_takes_priority_over_regex(self, pick_kind: ModuleType) -> None:
        # `$X` plus regex metacharacters — AST escalation wins because
        # ast-grep is the correct tool for metavariable patterns.
        result = pick_kind.decide(r"$X\d+")
        assert result["escalate"] is True


class TestDecideImportsHint:
    def test_imports_of_emits_scope_and_glob(self, pick_kind: ModuleType) -> None:
        result = pick_kind.decide("imports of cli")
        assert result == {
            "query": "cli",
            "kind": "content",
            "scope": "files-with-imports",
            "glob": "**/*.py",
        }


class TestDecideErrors:
    def test_empty_query_raises_cli_error(self, pick_kind: ModuleType) -> None:
        with pytest.raises(pick_kind.cli.CliError):
            pick_kind.decide("")

    def test_whitespace_only_raises_cli_error(self, pick_kind: ModuleType) -> None:
        with pytest.raises(pick_kind.cli.CliError):
            pick_kind.decide("   \t  ")


# ---------------------------------------------------------------------------
# CLI entrypoint tests via subprocess (cli.run calls sys.exit, so we can't
# invoke it in-process without trapping SystemExit on every call).
# ---------------------------------------------------------------------------


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BUNDLE), "pick_kind", *args],
        capture_output=True,
        text=True,
    )


class TestCli:
    def test_symbol_query_json_shape(self) -> None:
        result = _run_cli("--query", "foo_bar", "--json")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload == {"query": "foo_bar", "kind": "symbol"}

    def test_content_query_quoted_phrase(self) -> None:
        result = _run_cli("--query", '"some literal phrase"', "--json")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload == {"query": "some literal phrase", "kind": "content"}

    def test_regex_query_slashed(self) -> None:
        result = _run_cli("--query", "/regex.*/", "--json")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload == {"query": "regex.*", "kind": "regex"}

    def test_ast_query_escalates_with_reason(self) -> None:
        result = _run_cli("--query", "$X.method()", "--json")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["escalate"] is True
        assert payload["reason"].startswith("ast-shape")

    def test_missing_query_exits_2(self) -> None:
        result = _run_cli("--json")
        assert result.returncode == 2
        assert "--query" in result.stderr

    def test_callers_query_extracts_target(self) -> None:
        result = _run_cli("--query", "callers of validateToken", "--json")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload == {"query": "validateToken", "kind": "callers"}

    def test_default_output_is_json_for_dict(self) -> None:
        # cli.emit always dumps dicts as JSON, even without --json.
        result = _run_cli("--query", "foo_bar")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["kind"] == "symbol"
