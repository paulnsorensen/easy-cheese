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

Decision rule: goal count and blast radius provide an advisory Cook wave-mode
hint. Curd-count is sizing-only: it names the recommended skill, reports
landing and signals, and never authorizes execution or constructs a handoff.
Finalization is the sole authority publisher; it decides whether a canonical
Cook handoff is ready.

`/ultracook` is retired. The count is a signal, not a verdict: the decomposer
confirms file-disjointness before parallel fan-out runs.
"""
from __future__ import annotations

# Cyclopts exposes its application result as Any at the invocation boundary.
# pyright: reportAny=false, reportUnusedCallResult=false

import json

from cyclopts import App, Parameter
from cyclopts.exceptions import CycloptsError
import re
import sys
from pathlib import Path
from typing import Annotated

from easy_cheese.shared.fanout.mode import PARALLEL_THRESHOLD
from easy_cheese.shared import cli
from easy_cheese.shared.taste_test import (
    ApplicabilityError,
    TasteTestError,
    is_new_mold_spec,
    parse_gate_applicability,
    parse_landing,
    read_spec_text,
)
from easy_cheese_schemas.contracts import Landing, LandingShape, landing_mapping

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
        + f"blast radius {radius or 'unknown'}",
    )


class SpecReadError(Exception):
    pass


def _read_spec(spec_path: Path) -> str:
    try:
        return read_spec_text(spec_path)
    except UnicodeDecodeError as exc:
        raise SpecReadError(
            f"spec is not valid UTF-8 ({exc.reason} at byte {exc.start})"
        ) from exc
    except OSError as exc:
        raise SpecReadError(f"could not read spec: {exc.strerror or exc}") from exc



def _gate_applicability_warnings(body: str) -> list[str]:
    """Report a malformed ``gate_applicability`` block as a sizing warning.

    Curd-count sizes work and never gates it, so a bad declaration changes no
    recommendation here.  Reporting it names the problem the finalize gate
    raises later, while the spec is still open.
    """
    try:
        _ = parse_gate_applicability(body, require_ui_surface=True)
    except ApplicabilityError as exc:
        if exc.problems == (
            "gate-applicability-declaration-required",
        ) and not is_new_mold_spec(body):
            return []
        return [f"gate-applicability:{problem}" for problem in exc.problems]
    except TasteTestError as exc:
        return [f"gate-applicability:{exc}"]
    return []


def analyze(spec_path: Path, blast_radius: str | None) -> dict[str, object]:
    body = _read_spec(spec_path)
    goals = _count_bullets(_extract_section(body, GOALS_HEADINGS))
    quality_gates = _count_bullets(_extract_section(body, QUALITY_GATES_HEADINGS))
    candidate_curds = goals
    decisions = _count_bullets(_extract_section(body, DECISIONS_HEADINGS))

    recommended, mode, rationale = _recommend(candidate_curds, blast_radius)
    try:
        declared_landing = parse_landing(body) or Landing(shape=LandingShape.SINGLE)
    except ApplicabilityError as exc:
        raise SpecReadError(f"invalid landing: {exc}") from exc
    landing = landing_mapping(declared_landing)

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
        "landing": landing,
        "warnings": _gate_applicability_warnings(body),
        "mode": mode,
        "rationale": rationale,
        "notes": [
            "Count is a signal, not a verdict.",
            "candidate_curds = goals only; acceptance-criteria / quality-gate count does not drive it (issue #111).",
            "Confirm curd independence (criterion 4: file-disjoint) before /cook fans out in parallel waves.",
        ],
    }


def _command(
    spec_path: Path,
    blast_radius: Annotated[
        str | None, Parameter(name="--blast-radius", choices=("low", "medium", "high"))
    ] = None,
) -> int:

    if not spec_path.exists():
        print(f"error: spec not found: {spec_path}", file=sys.stderr)
        return 2
    if not spec_path.is_file():
        print(f"error: not a file: {spec_path}", file=sys.stderr)
        return 2

    try:
        digest = analyze(spec_path, blast_radius)
    except SpecReadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    json.dump(digest, sys.stdout, indent=2)
    _ = sys.stdout.write("\n")
    return 0


app = App(name="curd-count")
_ = app.default(_command)


def main(argv: list[str] | None = None) -> int:
    tokens = list(sys.argv[1:] if argv is None else argv)
    try:
        canonical = cli.repair_argv(app, tokens)
        result = app(
            canonical,
            print_error=False,
            exit_on_error=False,
            help_on_error=False,
            result_action="return_value",
        )
    except CycloptsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    return 0 if result is None else int(result)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
