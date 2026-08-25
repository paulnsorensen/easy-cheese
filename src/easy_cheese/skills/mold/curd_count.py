#!/usr/bin/env python3
"""Count candidate curds in a mold-generated spec and recommend the next skill.

Reads a mold-generated spec — the path `mold.pyz artifact-path specs <slug>`
resolves (`.cheese/specs/<slug>.md` by default) — counts distinct behavioural
goals under `## Goals`, and emits a JSON digest naming the recommended downstream skill
based on that count plus the shape-check blast-radius verdict. The `## Quality
gates` (acceptance criteria) and `## Decisions` bullets are reported as signals
but do NOT drive the count: they are facets of one coherent change, not
independent file-disjoint curds, so counting them inflates the recommendation
toward fan-out for specs that are emphatically not decomposable (issue #111).

Decision rule: goal count and blast radius still select the eventual Cook wave
mode. Gate applicability selects the immediate skill: `red-required` routes to
`/cut`, whose receipt then unlocks Cook; closed `not-applicable` and legacy
specs route directly to `/cook`. Mold provenance markers require the explicit
`gate_applicability.ui_surface` classification; unmarked legacy specs remain
compatible with Cut. `--auto` remains a user-selected menu choice.

`/ultracook` is retired. The count is a signal, not a verdict: the decomposer
confirms file-disjointness before parallel fan-out runs.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from easy_cheese_schemas.decomposition import PARALLEL_THRESHOLD
from easy_cheese.skills.mold.taste_test import (
    ApplicabilityError,
    RedRequired,
    auto_handoff,
    is_new_mold_spec,
    parse_gate_applicability,
)

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


def _recommend(
    candidate_curds: int, blast_radius: str | None
) -> tuple[str, str | None, str]:
    """Return (recommended_skill, mode, rationale).

    `mode` is "parallel" or "linear" as an internal wave-plan hint, else
    None (no fan-out signal for this pick)."""
    if candidate_curds >= PARALLEL_THRESHOLD:
        return (
            "/cook",
            "parallel",
            f"{candidate_curds} candidate curds >= {PARALLEL_THRESHOLD} threshold; parallel fan-out",
        )
    radius = (blast_radius or "").lower()
    if radius == "high":
        return (
            "/cook",
            "linear",
            f"{candidate_curds} candidate curds < {PARALLEL_THRESHOLD}; blast radius high; linear chain",
        )
    return (
        "/cook",
        None,
        f"{candidate_curds} candidate curds < {PARALLEL_THRESHOLD}; "
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


def _gate_handoff(spec_path: Path, body: str) -> dict[str, Any] | None:
    if (
        not re.search(r"(?m)^gate_applicability:\s*(?:\{|$)", body)
        and not is_new_mold_spec(body)
    ):
        return None
    try:
        applicability = parse_gate_applicability(
            body,
            require_ui_surface=is_new_mold_spec(body),
        )
    except ApplicabilityError as exc:
        raise SpecReadError(f"invalid gate applicability: {exc}") from exc
    if isinstance(applicability, RedRequired):
        return auto_handoff(spec_path, applicability)
    return None


def analyze(spec_path: Path, blast_radius: str | None) -> dict:
    body = _read_spec(spec_path)
    goals = _count_bullets(_extract_section(body, GOALS_HEADINGS))
    quality_gates = _count_bullets(_extract_section(body, QUALITY_GATES_HEADINGS))
    candidate_curds = goals
    decisions = _count_bullets(_extract_section(body, DECISIONS_HEADINGS))

    recommended, mode, rationale = _recommend(candidate_curds, blast_radius)
    handoff = _gate_handoff(spec_path, body)
    if handoff is not None:
        recommended = str(handoff["command"][0])
        rationale = f"red-required outer gate precedes {rationale}"

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
        "threshold": PARALLEL_THRESHOLD,
        "decomposable": candidate_curds >= PARALLEL_THRESHOLD,
        "recommended_skill": recommended,
        "handoff": handoff,
        "mode": mode,
        "rationale": rationale,
        "notes": [
            "Count is a signal, not a verdict.",
            "candidate_curds = goals only; acceptance-criteria / quality-gate count does not drive it (issue #111).",
            "Confirm curd independence (criterion 4: file-disjoint) before /cook fans out in parallel waves.",
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
