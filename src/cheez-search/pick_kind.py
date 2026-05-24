#!/usr/bin/env python3
"""Decision-table router: pick the `tilth_search` kind for a query string.

Encodes the routing rules cheez-search/SKILL.md applies per-query so the LLM
does not have to redo the classification each call. Pure stdlib.

Decision rules (first match wins):

  1. AST-shape metavariables ($X, $$$BODY)               -> escalate (ast-grep)
  2. "callers of X" / "who calls X" / "what calls X"     -> kind=callers
  3. Slashed regex (/.../) or regex metacharacters       -> kind=regex
  4. Quoted string or sentence (whitespace present)      -> kind=content
  5. Pure identifier (default)                           -> kind=symbol

`scope` and `glob` are emitted only when the routing rule has an opinion
(currently the import-of hint).
"""
from __future__ import annotations

import argparse
import re

import cli  # noqa: E402


# Identifier: pure name-shaped token (letters, digits, underscore; no leading digit).
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# AST-shape metavariable: $X, $NAME, $$$BODY (ast-grep syntax).
AST_METAVAR_RE = re.compile(r"\$[A-Za-z_]|\$\$\$")

# Slashed regex: /pattern/ or /pattern/flags.
SLASHED_REGEX_RE = re.compile(r"^/.+/[a-z]*$")

# Regex metacharacters that indicate the user wants regex semantics, not literal.
REGEX_METACHAR_RE = re.compile(r"\\[dwsDWSb]|\[\^|\.\*|\.\+|\(\?[:=!]")

# Callers phrasing: "callers of foo", "who calls foo", "what calls foo".
CALLERS_RE = re.compile(
    r"^(?:callers?\s+of\s+|who\s+calls\s+|what\s+calls\s+)(\S+)\s*$",
    re.IGNORECASE,
)

# Imports-of phrasing: "imports of foo" / "files importing foo".
IMPORTS_RE = re.compile(
    r"^(?:imports?\s+of\s+|files?\s+importing\s+)(\S+)\s*$",
    re.IGNORECASE,
)


def _strip_quotes(query: str) -> tuple[str, bool]:
    """Return (inner, was_quoted). Recognises matching ASCII single/double quotes."""
    if len(query) >= 2 and query[0] == query[-1] and query[0] in ('"', "'"):
        return query[1:-1], True
    return query, False


def decide(raw_query: str) -> dict:
    """Map a raw query string to a tilth_search routing decision (or escalate)."""
    query = raw_query.strip()
    if not query:
        raise cli.CliError("--query must be a non-empty string")

    # Rule 1: AST-shape metavariables route to ast-grep, not tilth.
    if AST_METAVAR_RE.search(query):
        return {
            "query": query,
            "escalate": True,
            "reason": "ast-shape pattern; use ast-grep (sg) — tilth_search cannot express metavariables",
        }

    # Rule 2: callers phrasing — extract the target symbol.
    if (m := CALLERS_RE.match(query)):
        return {"query": m.group(1), "kind": "callers"}

    # Imports-of hint: scope=files-with-imports, glob defaults to Python here.
    if (m := IMPORTS_RE.match(query)):
        return {
            "query": m.group(1),
            "kind": "content",
            "scope": "files-with-imports",
            "glob": "**/*.py",
        }

    # Rule 3a: slashed regex — strip delimiters, route to regex.
    if SLASHED_REGEX_RE.match(query):
        inner = query[1:].rsplit("/", 1)[0]
        return {"query": inner, "kind": "regex"}

    # Rule 3b: bare regex with metacharacters.
    if REGEX_METACHAR_RE.search(query):
        return {"query": query, "kind": "regex"}

    # Rule 4: quoted literal or sentence -> content.
    inner, was_quoted = _strip_quotes(query)
    if was_quoted or " " in query:
        return {"query": inner if was_quoted else query, "kind": "content"}

    # Rule 5: pure identifier -> symbol.
    if IDENTIFIER_RE.match(query):
        return {"query": query, "kind": "symbol"}

    # Fallback: treat as content so the caller still gets a usable result.
    return {"query": query, "kind": "content"}


def _handle(args: argparse.Namespace) -> None:
    if args.query is None:
        raise cli.CliError("--query is required")
    result = decide(args.query)
    cli.emit(result, json_mode=args.json_mode)


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Pick the tilth_search kind for a query string."
    parser.add_argument("--query", help="Raw user query to classify.")
    parser.set_defaults(func=_handle)


if __name__ == "__main__":
    cli.run(_setup)
