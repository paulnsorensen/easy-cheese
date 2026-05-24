#!/usr/bin/env python3
"""Apply the /briesearch confidence cap to a routed source list.

Reads a JSON list of sources (file path or `-` for stdin) and emits the
overall confidence label and a one-line justification per the rubric in
`skills/briesearch/references/synthesis.md`.

Canonical confidence vocabulary (from synthesis.md): `certain`,
`speculating`, `don't know` — written verbatim, never synonyms.

Source JSON shape:
    [
      {"url": "...", "quality": "high|medium|low",
       "age_days": 30, "concordance": "agrees|conflicts|neutral"}
    ]

Rubric (applied in order; first match wins):
  - empty list                                    -> CliError
  - any conflicts                                 -> don't know
  - any low quality OR all stale (>365 days)
      OR single source                            -> don't know
  - >=3 concordant + all high quality + all recent -> certain
  - otherwise                                     -> speculating
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cli  # noqa: E402

RECENCY_DAYS = 365
CONFIDENCE_CERTAIN = "certain"
CONFIDENCE_SPECULATING = "speculating"
CONFIDENCE_UNKNOWN = "don't know"

VALID_QUALITY = {"high", "medium", "low"}
VALID_CONCORDANCE = {"agrees", "conflicts", "neutral"}


def _load_sources(path: str) -> list[dict]:
    if path == "-":
        raw = sys.stdin.read()
    else:
        try:
            raw = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise cli.CliError(f"could not read sources: {exc.strerror or exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise cli.CliError(f"invalid JSON: {exc.msg} at line {exc.lineno}") from exc
    if not isinstance(data, list):
        raise cli.CliError(f"sources must be a JSON list, got {type(data).__name__}")
    return data


def _validate(sources: list[dict]) -> None:
    for i, src in enumerate(sources):
        if not isinstance(src, dict):
            raise cli.CliError(f"source[{i}] must be an object, got {type(src).__name__}")
        q = src.get("quality")
        if q not in VALID_QUALITY:
            raise cli.CliError(f"source[{i}].quality must be one of high|medium|low, got {q!r}")
        c = src.get("concordance")
        if c not in VALID_CONCORDANCE:
            raise cli.CliError(f"source[{i}].concordance must be one of agrees|conflicts|neutral, got {c!r}")
        age = src.get("age_days")
        if not isinstance(age, int) or age < 0:
            raise cli.CliError(f"source[{i}].age_days must be a non-negative integer, got {age!r}")


def cap(sources: list[dict]) -> dict:
    """Return {confidence, justification} for the source list."""
    if not sources:
        raise cli.CliError("no sources provided")
    _validate(sources)

    n = len(sources)
    qualities = [s["quality"] for s in sources]
    ages = [s["age_days"] for s in sources]
    concords = [s["concordance"] for s in sources]

    has_conflict = any(c == "conflicts" for c in concords)
    all_high = all(q == "high" for q in qualities)
    any_low = any(q == "low" for q in qualities)
    all_stale = all(a > RECENCY_DAYS for a in ages)
    all_recent = all(a <= RECENCY_DAYS for a in ages)
    concordant_count = sum(1 for c in concords if c == "agrees")

    if has_conflict:
        return {
            "confidence": CONFIDENCE_UNKNOWN,
            "justification": f"{n} source(s) include conflicting evidence; the cap surfaces disagreement rather than averaging.",
        }
    if n == 1:
        return {
            "confidence": CONFIDENCE_UNKNOWN,
            "justification": "single source per claim caps below certain; with no corroboration the rubric drops to don't know.",
        }
    if any_low:
        return {
            "confidence": CONFIDENCE_UNKNOWN,
            "justification": f"{n} source(s) include at least one low-quality entry; one weak link caps the cohort at don't know.",
        }
    if all_stale:
        return {
            "confidence": CONFIDENCE_UNKNOWN,
            "justification": f"all {n} source(s) are older than {RECENCY_DAYS} days; staleness caps the cohort at don't know.",
        }
    if concordant_count >= 3 and all_high and all_recent:
        return {
            "confidence": CONFIDENCE_CERTAIN,
            "justification": f"{concordant_count} concordant high-quality source(s), all within {RECENCY_DAYS} days; meets the 3+ agree rule for certain.",
        }
    return {
        "confidence": CONFIDENCE_SPECULATING,
        "justification": f"{n} source(s) with mixed quality/recency/concordance; meets the 2+ agree rule but not the cap for certain.",
    }


def _cmd(args) -> None:
    sources = _load_sources(args.sources)
    result = cap(sources)
    if args.json_mode:
        cli.emit(result, json_mode=True)
    else:
        cli.emit(f"confidence: {result['confidence']}")
        cli.emit(f"justification: {result['justification']}")


def _setup(parser) -> None:
    parser.add_argument(
        "--sources",
        required=True,
        help="Path to JSON file listing sources, or '-' to read from stdin.",
    )
    parser.set_defaults(func=_cmd)


if __name__ == "__main__":
    cli.run(_setup)
