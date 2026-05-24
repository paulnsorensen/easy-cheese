#!/usr/bin/env python3
"""Deterministic classifier for /cheese dispatch routing.

Confirmation-bias killer: the /cheese skill freelances classification in prose.
This script gives it a deterministic verdict so reviewers can compare against
the LLM's choice and catch silent misroutes.

Reads `--input "<text>"` and emits JSON of shape:

    {
      "intent": "cook | age | mold | melt | debug | research | rubber-duck |
                 age-then-cure | cheese-factory | unknown",
      "confidence": "low | medium | high",
      "signals": ["..."],
      "target_skill": "cook | age | mold | ..."
    }

Rules are a keyword + path-pattern table; the highest-scoring intent wins.
Below medium confidence (no strong signal hit) the verdict is `unknown`
routed to `cheese`.
"""
from __future__ import annotations

import re

import cli  # noqa: E402

# Each rule: (intent, target_skill, [(weight, signal_label, regex), ...]).
# Weights: 3 = unambiguous signal (e.g. spec path, PR url, conflict marker),
#          2 = strong verb match, 1 = weak verb match. A score >=3 is `high`,
#          ==2 is `medium`, ==1 is `low`. `unknown` returns when total < 2.
RULES: list[tuple[str, str, list[tuple[int, str, re.Pattern[str]]]]] = [
    (
        "melt",
        "melt",
        [
            (3, "conflict-marker", re.compile(r"<{7}|>{7}|={7}")),
            (3, "git-conflict-line", re.compile(r"\bCONFLICT\s*\(", re.I)),
            (2, "fix-the-merge", re.compile(r"\bfix(?:ing)?\s+(?:the\s+)?(?:merge|rebase|cherry[- ]?pick)\b", re.I)),
            (2, "merge-conflicts-phrase", re.compile(r"\bmerge\s+conflicts?\b", re.I)),
        ],
    ),
    (
        "age-then-cure",
        "age",
        [
            (3, "review-and-fix", re.compile(r"\breview\s+(?:and|then|&)\s+fix\b", re.I)),
            (3, "find-and-fix", re.compile(r"\bfind\s+(?:and|then|&)\s+fix\b", re.I)),
            (2, "age-report-path", re.compile(r"\.cheese/age/[^\s]+\.md\b")),
        ],
    ),
    (
        "age",
        "age",
        [
            (3, "pr-url", re.compile(r"https?://github\.com/[^\s/]+/[^\s/]+/pull/\d+")),
            (3, "pr-ref", re.compile(r"\bPR\s*#?\s*\d+\b", re.I)),
            (3, "issue-ref-with-review", re.compile(r"#\d+.*\breview\b", re.I)),
            (2, "review-verb", re.compile(r"\breview(?:ing|s)?\b", re.I)),
            (2, "find-bugs", re.compile(r"\bfind\s+bugs?\b", re.I)),
            (2, "safe-to-merge", re.compile(r"\bsafe\s+to\s+merge\b", re.I)),
            (2, "check-for-slop", re.compile(r"\bcheck\s+for\s+slop\b", re.I)),
        ],
    ),
    (
        "debug",
        "pasteurize",
        [
            (3, "stack-trace", re.compile(r"\bTraceback \(most recent call last\):|^\s*at\s+\S+\(.*\):\d+", re.M)),
            (3, "exception-line", re.compile(r"\b[A-Z][A-Za-z]*(?:Error|Exception):\s")),
            (2, "failing-test", re.compile(r"\b(?:failing|fails?)\s+test\b", re.I)),
            (2, "why-is-broken", re.compile(r"\bwhy\s+is\s+\S+\s+broken\b", re.I)),
            (2, "whats-wrong", re.compile(r"\bwhat'?s\s+wrong\s+with\b", re.I)),
        ],
    ),
    (
        "cook",
        "cook",
        [
            (3, "spec-path", re.compile(r"\.cheese/specs/[^\s]+\.md\b")),
            (2, "implement-verb", re.compile(r"\bimplement(?:ing|s)?\b", re.I)),
            (2, "build-this", re.compile(r"\bbuild\s+(?:this|the|a)\b", re.I)),
            (2, "write-the-code", re.compile(r"\bwrite\s+the\s+code\b", re.I)),
            (2, "make-it-work", re.compile(r"\bmake\s+it\s+work\b", re.I)),
            (2, "fix-this-bug", re.compile(r"\bfix\s+(?:this|the)\s+bug\b", re.I)),
            (1, "ship-it", re.compile(r"\bship\s+it\b", re.I)),
        ],
    ),
    (
        "mold",
        "mold",
        [
            (2, "design-verb", re.compile(r"\bdesign(?:ing)?\b(?!\s+pattern)", re.I)),
            (2, "shape-into-spec", re.compile(r"\bshape\s+(?:this\s+)?into\s+a\s+spec\b", re.I)),
            (2, "lets-design", re.compile(r"\blet'?s\s+design\b", re.I)),
            (2, "spec-for", re.compile(r"\bspec\s+(?:for|out|this)\b", re.I)),
            (2, "what-should-api", re.compile(r"\bwhat\s+should\s+the\s+(?:api|interface)\b", re.I)),
            (1, "add-feature", re.compile(r"\badd\s+(?:a\s+)?(?:new\s+)?feature\b", re.I)),
            (1, "thinking-about", re.compile(r"\bI'?m\s+thinking\s+about\b", re.I)),
        ],
    ),
    (
        "research",
        "briesearch",
        [
            (2, "best-library", re.compile(r"\bbest\s+\S+\s+(?:library|lib|crate|package|framework)\b", re.I)),
            (2, "compare-libs", re.compile(r"\bcompare\s+\S+\s+(?:vs|versus|with)\b", re.I)),
            (2, "research-verb", re.compile(r"\bresearch(?:ing)?\b", re.I)),
            (2, "look-up", re.compile(r"\blook\s+up\b", re.I)),
            (2, "before-implement", re.compile(r"\bbefore\s+I\s+implement\b", re.I)),
            (2, "still-maintained", re.compile(r"\bstill\s+maintained\b", re.I)),
        ],
    ),
    (
        "rubber-duck",
        "culture",
        [
            (3, "rubber-duck-phrase", re.compile(r"\brubber[- ]?duck(?:ing)?\b", re.I)),
            (3, "help-me-think", re.compile(r"\bhelp\s+me\s+think\s+(?:through|about)\b", re.I)),
            (3, "lets-talk-about", re.compile(r"\blet'?s\s+talk\s+about\b", re.I)),
            (2, "just-thinking", re.compile(r"\bjust\s+thinking\b", re.I)),
        ],
    ),
    (
        "cheese-factory",
        "cheese-factory",
        [
            (3, "factory-phrase", re.compile(r"\bcheese[- ]?factory\b", re.I)),
            (2, "send-through-factory", re.compile(r"\bsend\s+through\s+the\s+factory\b", re.I)),
            (2, "fan-out", re.compile(r"\bfan[- ]?out\b", re.I)),
            (2, "parallelize", re.compile(r"\bparallel(?:ize|ise)\s+(?:this|the)\b", re.I)),
        ],
    ),
]

CONFIDENCE_THRESHOLDS = {"high": 3, "medium": 2, "low": 1}


def _score(intent_rules: list[tuple[int, str, re.Pattern[str]]], text: str) -> tuple[int, list[str]]:
    score = 0
    matched: list[str] = []
    for weight, label, pattern in intent_rules:
        if pattern.search(text):
            score += weight
            matched.append(label)
    return score, matched


def _bucket_confidence(score: int) -> str:
    if score >= CONFIDENCE_THRESHOLDS["high"]:
        return "high"
    if score >= CONFIDENCE_THRESHOLDS["medium"]:
        return "medium"
    return "low"


def classify(text: str) -> dict:
    """Return the verdict dict; never raises on empty input."""
    if not text.strip():
        return {
            "intent": "unknown",
            "confidence": "low",
            "signals": [],
            "target_skill": "cheese",
        }
    scored: list[tuple[int, str, str, list[str]]] = []
    for intent, target_skill, rules in RULES:
        score, matched = _score(rules, text)
        if score > 0:
            scored.append((score, intent, target_skill, matched))
    if not scored:
        return {
            "intent": "unknown",
            "confidence": "low",
            "signals": [],
            "target_skill": "cheese",
        }
    scored.sort(key=lambda row: row[0], reverse=True)
    best_score, intent, target_skill, signals = scored[0]
    confidence = _bucket_confidence(best_score)
    if confidence == "low":
        # Single weak match isn't enough to commit to a route.
        return {
            "intent": "unknown",
            "confidence": "low",
            "signals": signals,
            "target_skill": "cheese",
        }
    return {
        "intent": intent,
        "confidence": confidence,
        "signals": signals,
        "target_skill": target_skill,
    }


def _cmd_classify(args) -> None:
    # --input is required at the parser level; argparse exits 2 if missing.
    verdict = classify(args.input)
    cli.emit(verdict, json_mode=True)


def _setup(parser) -> None:
    parser.add_argument("--input", required=True, help="The text to classify (user $ARGUMENTS).")
    parser.set_defaults(func=_cmd_classify)


if __name__ == "__main__":
    cli.run(_setup)
