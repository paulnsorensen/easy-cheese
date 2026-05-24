#!/usr/bin/env python3
"""Route a /briesearch question to the right tool rung.

Encodes the decision table from skills/briesearch/references/routing.md so the
skill stops freelancing routing decisions in prose. Stdlib-only.

Rules (first match wins):
  doc-shaped       ("how do I use X", "X SDK API")           -> context7
  recency-shaped   ("latest", "recent", "this week")         -> tavily-search basic
  comparative      ("compare X vs Y", "best practices")      -> tavily-research advanced
  local-codebase   ("where does X happen in this repo")      -> cheez-search
  github-examples  ("examples of X on GitHub")               -> gh

`--prefer-docs` biases ties toward context7; `--prefer-recency` biases ties
toward tavily-search basic. Output: a one-paragraph routing block to stdout
plus a sidecar JSON at `<out-dir>/<slug>.json` (default `.cheese/briesearch/`).
`--json` swaps the routing block for the JSON body on stdout.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import cli  # noqa: E402


# Pattern groups, ordered by priority. The first group with a hit wins.
DOC_PATTERNS = (
    r"\bhow do i use\b",
    r"\bsdk api\b",
    r"\bapi for\b",
    r"\blibrary api\b",
    r"\bdocumentation for\b",
    r"\bdocs for\b",
    r"\bhow to (?:use|call|configure)\b",
)
RECENCY_PATTERNS = (
    r"\blatest\b",
    r"\brecent(?:ly)?\b",
    r"\bthis week\b",
    r"\btoday\b",
    r"\bnewest\b",
    r"\bcurrent\b",
)
COMPARATIVE_PATTERNS = (
    r"\bcompare\b.*\bvs\b",
    r"\b\w+\s+vs\.?\s+\w+",
    r"\bbest practices?\b",
    r"\bdeep research\b",
    r"\bmarket analysis\b",
    r"\blit(?:erature)? review\b",
)
LOCAL_PATTERNS = (
    r"\bin this repo\b",
    r"\bin our codebase\b",
    r"\bin the codebase\b",
    r"\bshow me callers\b",
    r"\bwhere does \w+ happen\b",
    r"\bwhere is \w+ defined\b",
)
GITHUB_PATTERNS = (
    r"\bexamples? of .+ on github\b",
    r"\bon github\b",
    r"\bgithub examples?\b",
    r"\boss precedent\b",
)


def _matches(question: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, question, re.IGNORECASE) for p in patterns)


def _slugify(question: str, max_len: int = 40) -> str:
    lowered = question.strip().lower()
    kebab = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if not kebab:
        return "untitled"
    return kebab[:max_len].rstrip("-") or "untitled"


def classify(
    question: str,
    *,
    prefer_docs: bool = False,
    prefer_recency: bool = False,
) -> dict:
    """Return the routing dict for `question`. Pure function, no I/O."""
    if not question or not question.strip():
        raise cli.CliError("question must be non-empty")

    is_doc = _matches(question, DOC_PATTERNS)
    is_recency = _matches(question, RECENCY_PATTERNS)
    is_compare = _matches(question, COMPARATIVE_PATTERNS)
    is_local = _matches(question, LOCAL_PATTERNS)
    is_github = _matches(question, GITHUB_PATTERNS)

    # Tie-breakers fire before normal priority so they can override.
    if prefer_docs and is_doc:
        return _result("context7", "library docs (prefer-docs bias)", None, question)
    if prefer_recency and is_recency:
        return _result(
            "tavily-search",
            "current/recent web facts (prefer-recency bias)",
            "basic",
            question,
        )

    if is_doc:
        return _result("context7", "library/API documentation question", None, question)
    if is_recency:
        return _result(
            "tavily-search",
            "current or recent factual question",
            "basic",
            question,
        )
    if is_compare:
        return _result(
            "tavily-research",
            "comparative or deep-research question",
            "advanced",
            question,
        )
    if is_local:
        return _result(
            "cheez-search",
            "local codebase pattern question",
            None,
            question,
        )
    if is_github:
        return _result(
            "gh",
            "GitHub real-world example question",
            None,
            question,
        )

    # Default: when nothing matches, fall through to tavily-search basic
    # (the routing.md default for any factual question without a clearer fit).
    return _result(
        "tavily-search",
        "no rule matched; defaulting to general web search",
        "basic",
        question,
    )


def _result(tool: str, rationale: str, depth: str | None, question: str) -> dict:
    return {
        "tool": tool,
        "rationale": rationale,
        "depth": depth,
        "question": question,
    }


def _routing_block(decision: dict) -> str:
    tool = decision["tool"]
    rationale = decision["rationale"]
    depth = decision["depth"]
    depth_str = f" (depth: {depth})" if depth else ""
    return (
        f"ROUTING DECISION: {tool}{depth_str} — {rationale}. "
        f"Question: {decision['question']!r}."
    )


def _write_sidecar(decision: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(decision["question"])
    path = out_dir / f"{slug}.json"
    path.write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")
    return path


def _cmd(args) -> None:
    if not args.question:
        raise cli.CliError("--question is required")
    decision = classify(
        args.question,
        prefer_docs=args.prefer_docs,
        prefer_recency=args.prefer_recency,
    )
    out_dir = Path(args.out_dir) if args.out_dir else Path(".cheese/briesearch")
    _write_sidecar(decision, out_dir)
    if args.json_mode:
        cli.emit(decision, json_mode=True)
    else:
        cli.emit(_routing_block(decision))


def _setup(parser) -> None:
    parser.add_argument("--question", help="The research question to route.")
    parser.add_argument(
        "--prefer-docs",
        action="store_true",
        help="Bias toward Context7 when the question matches doc patterns.",
    )
    parser.add_argument(
        "--prefer-recency",
        action="store_true",
        help="Bias toward Tavily basic when the question matches recency patterns.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Override sidecar JSON output directory (default .cheese/briesearch/).",
    )
    parser.set_defaults(func=_cmd)


if __name__ == "__main__":
    cli.run(_setup)
