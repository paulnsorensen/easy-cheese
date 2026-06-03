#!/usr/bin/env python3
"""Pick the right Tavily tool + depth + filters for a /briesearch question.

Decision table (lowest-cost rung that fits, per
`skills/briesearch/references/routing.md`):

  URL provided                        -> tavily-extract  (url filter)
  "map the docs at <URL>"             -> tavily-map      (url filter)
  "crawl <URL>"                       -> tavily-crawl    (url filter)
  "compare X vs Y" / "deep research"  -> tavily-research advanced
  "opinion on X" / "review of X"      -> tavily-search   advanced
  "latest X" / "this week" / "recent" -> tavily-search   basic    (time_range=week)
  default factual question            -> tavily-search   basic    (no filters)

Output is the rung digest:

  {"tool": str, "depth": str | None, "filters": dict, "question": str}

`depth` is `None` for extract / map / crawl (rungs that take no `search_depth`).
"""
from __future__ import annotations

import re

import cli  # noqa: E402

URL_RE = re.compile(r"https?://\S+")
MAP_RE = re.compile(r"\bmap\b.*\bat\s+(https?://\S+)", re.IGNORECASE)
CRAWL_RE = re.compile(r"\bcrawl\b\s+(https?://\S+)", re.IGNORECASE)
COMPARE_RE = re.compile(r"\bcompare\b.*\bvs\.?\b|\bdeep research\b", re.IGNORECASE)
OPINION_RE = re.compile(r"\b(opinion|review)\s+(on|of)\b", re.IGNORECASE)
RECENT_RE = re.compile(r"\b(latest|recent|this week)\b", re.IGNORECASE)


def pick(question: str) -> dict:
    """Return the rung digest for `question`."""
    q = (question or "").strip()
    if not q:
        raise cli.CliError("--question must not be empty")

    if m := MAP_RE.search(q):
        return {"tool": "tavily-map", "depth": None,
                "filters": {"url": m.group(1)}, "question": q}
    if m := CRAWL_RE.search(q):
        return {"tool": "tavily-crawl", "depth": None,
                "filters": {"url": m.group(1)}, "question": q}
    if m := URL_RE.search(q):
        return {"tool": "tavily-extract", "depth": None,
                "filters": {"url": m.group(0)}, "question": q}
    if COMPARE_RE.search(q):
        return {"tool": "tavily-research", "depth": "advanced",
                "filters": {}, "question": q}
    if OPINION_RE.search(q):
        return {"tool": "tavily-search", "depth": "advanced",
                "filters": {}, "question": q}
    if RECENT_RE.search(q):
        return {"tool": "tavily-search", "depth": "basic",
                "filters": {"time_range": "week"}, "question": q}
    return {"tool": "tavily-search", "depth": "basic",
            "filters": {}, "question": q}


def _cmd(args) -> None:
    if args.question is None:
        raise cli.CliError("--question is required")
    cli.emit(pick(args.question), json_mode=args.json_mode)


def _setup(parser) -> None:
    parser.description = "Pick Tavily tool + depth + filters for a question."
    parser.add_argument("--question", help="The /briesearch question text.")
    parser.set_defaults(func=_cmd)


if __name__ == "__main__":
    cli.run(_setup)
