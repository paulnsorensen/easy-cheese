#!/usr/bin/env python3
"""Count candidate curds in a mold-generated spec and recommend the next skill.

Reads `.cheese/specs/<slug>.md`, counts behavioural curd candidates from the
`## Goals` and `## Quality gates` sections, and emits a JSON digest naming
the recommended downstream skill based on the count plus the shape-check
blast-radius verdict.

Decision rule (recommended slot only — `--auto` variants are user-opt-in
alternatives surfaced by the Handoff menu, not picks the script makes):

  candidate_curds = max(goals_bullets, quality_gates_bullets)
  candidate_curds >= 5                   -> /cheese-factory
  candidate_curds <  5 and blast == high -> /ultracook
  candidate_curds <  5 (else)            -> /cook

The count is a signal, not a verdict — mold and the user must confirm
file-disjointness (criterion 4) before dispatching /cheese-factory.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CURD_THRESHOLD = 5

HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
BULLET_RE = re.compile(r"^\s*[-*+]\s+\S", re.MULTILINE)

GOALS_HEADINGS = {"goals", "goal"}
QUALITY_GATES_HEADINGS = {
    "quality gates",
    "quality gate",
    "acceptance criteria",
    "acceptance",
}
DECISIONS_HEADINGS = {"decisions", "decision"}


def _extract_section(body: str, headings: set[str]) -> str | None:
    matches = list(HEADING_RE.finditer(body))
    for i, match in enumerate(matches):
        if match.group(1).strip().lower() in headings:
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
            return body[start:end]
    return None


def _count_bullets(section: str | None) -> int:
    if not section:
        return 0
    return sum(1 for _ in BULLET_RE.finditer(section))


def _recommend(candidate_curds: int, blast_radius: str | None) -> tuple[str, str]:
    if candidate_curds >= CURD_THRESHOLD:
        return (
            "/cheese-factory",
            f"{candidate_curds} candidate curds >= {CURD_THRESHOLD} threshold",
        )
    radius = (blast_radius or "").lower()
    if radius == "high":
        return (
            "/ultracook",
            f"{candidate_curds} candidate curds < {CURD_THRESHOLD}; blast radius high",
        )
    return (
        "/cook",
        f"{candidate_curds} candidate curds < {CURD_THRESHOLD}; "
        f"blast radius {radius or 'unknown'}",
    )


class SpecReadError(Exception):
    pass


def _read_spec(spec_path: Path) -> str:
    try:
        return spec_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise SpecReadError(
            f"spec is not valid UTF-8 ({exc.reason} at byte {exc.start})"
        ) from exc
    except OSError as exc:
        raise SpecReadError(f"could not read spec: {exc.strerror or exc}") from exc


def analyze(spec_path: Path, blast_radius: str | None) -> dict:
    body = _read_spec(spec_path)
    goals = _count_bullets(_extract_section(body, GOALS_HEADINGS))
    quality_gates = _count_bullets(_extract_section(body, QUALITY_GATES_HEADINGS))
    decisions = _count_bullets(_extract_section(body, DECISIONS_HEADINGS))

    candidate_curds = max(goals, quality_gates)
    recommended, rationale = _recommend(candidate_curds, blast_radius)

    return {
        "spec_path": str(spec_path),
        "slug": spec_path.stem,
        "blast_radius": blast_radius,
        "candidate_curds": candidate_curds,
        "signals": {
            "goals": goals,
            "quality_gates": quality_gates,
            "decisions": decisions,
        },
        "threshold": CURD_THRESHOLD,
        "decomposable": candidate_curds >= CURD_THRESHOLD,
        "recommended_skill": recommended,
        "rationale": rationale,
        "notes": [
            "Count is a signal, not a verdict.",
            "Confirm curd independence (criterion 4: file-disjoint) before dispatching /cheese-factory.",
        ],
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "").splitlines()[0],
    )
    parser.add_argument(
        "spec_path",
        type=Path,
        help="Path to the spec markdown file (typically .cheese/specs/<slug>.md).",
    )
    parser.add_argument(
        "--blast-radius",
        choices=["low", "medium", "high"],
        help="Verdict from mold's shape-check; drives the recommendation when curds < threshold.",
    )
    args = parser.parse_args(argv)

    if not args.spec_path.exists():
        print(f"error: spec not found: {args.spec_path}", file=sys.stderr)
        return 2
    if not args.spec_path.is_file():
        print(f"error: not a file: {args.spec_path}", file=sys.stderr)
        return 2

    try:
        digest = analyze(args.spec_path, args.blast_radius)
    except SpecReadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    json.dump(digest, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
