from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.skills.plate.diagram_trigger import (
    FLOW_DIAGRAM,
    Change,
    DiagramNeed,
    decide,
    parse_name_status,
)

_PLATE = Path(__file__).resolve().parents[2] / "skills" / "plate"
_NAME_STATUS = "$ git diff --name-status --find-renames main...HEAD\n"


def _z(lines: str) -> str:
    """Encode tab-separated name-status lines as `git diff --name-status -z` prints them."""
    return "".join(f"{field}\0" for line in lines.splitlines() for field in line.split("\t"))


def _need(lines: str, shape: str | None = "single") -> DiagramNeed:
    return decide(parse_name_status(_z(lines)), shape=shape)


def _eval_changes(name: str) -> list[Change]:
    evals = cast(dict[str, list[dict[str, object]]], json.loads((_PLATE / "evals" / "evals.json").read_text()))
    case = next(case for case in evals["evals"] if case["name"] == name)
    fixture = (_PLATE / cast(list[str], case["files"])[0]).read_text()
    block = fixture.split(_NAME_STATUS, 1)[1].split("\n\n", 1)[0]
    return parse_name_status(_z(block))


@pytest.mark.parametrize(
    ("name", "shape", "kind"),
    [
        ("diagram-cross-module-flow", "single", FLOW_DIAGRAM),
        ("diagram-sequence-protocol", "single", None),
        ("single-small-fix", "single", None),
        ("body-concise-docs", "single", None),
        ("independent-unrelated", "orthogonal_flat", None),
    ],
)
def test_plate_evals_fire_only_on_the_cross_module_flow(name: str, shape: str, kind: str | None) -> None:
    assert decide(_eval_changes(name), shape=shape).kind == kind


@pytest.mark.parametrize(
    "first",
    ["A\tsrc/pkg/router.py", "D\tsrc/pkg/router.py", "R087\tsrc/pkg/route.py\tsrc/pkg/router.py"],
)
def test_flowchart_when_three_modules_change_and_one_is_added_removed_or_renamed(first: str) -> None:
    need = _need(f"{first}\nM\tsrc/pkg/cache.py\nM\tsrc/pkg/report.py\n")

    assert need == DiagramNeed(FLOW_DIAGRAM, "code modules: 3 changed, 1 added, removed, or renamed")


@pytest.mark.parametrize(
    ("lines", "shape", "reason"),
    [
        ("", "single", "the diff is empty"),
        ("M\tsrc/melt/status.py\nM\ttests/test_status.py\n", "single", "1 changed, 0 added"),
        ("A\tsrc/pkg/router.py\nA\tsrc/pkg/probe.py\n", "single", "2 changed, 2 added, removed, or renamed; a flow diagram needs 3 or more"),
        ("M\tsrc/a.py\nM\tsrc/b.ts\nM\tsrc/c.go\n", "single", "needs one added, removed, or renamed"),
        ("M\tREADME.md\nA\tdocs/guide.md\nM\tskills/melt/SKILL.md\n", "single", "docs-only change"),
        ("A\tsrc/a.py\nA\tsrc/b.py\nA\tsrc/c.py\n", "orthogonal_flat", "independent PR"),
        (
            "A\ttests/test_router.py\nA\tsrc/pkg/fixtures/data.py\nA\tvendor/lib.py\n"
            + "A\tweb/assets/app.3f2a.js\nA\tpkg/router_test.go\nA\tui/app.spec.ts\nM\tsrc/pkg/cache.py\n",
            None,
            "1 changed",
        ),
    ],
)
def test_no_diagram_for_a_small_fix_docs_independent_pr_or_non_modules(
    lines: str, shape: str | None, reason: str
) -> None:
    need = _need(lines, shape)

    assert need.kind is None
    assert reason in need.reason


def test_parse_name_status_keeps_the_new_path_of_a_rename() -> None:
    assert parse_name_status("R100\0old.py\0new.py\0M\0a.md\0") == [Change("R", "new.py"), Change("M", "a.md")]


@pytest.mark.parametrize("output", ["M\0", "R100\0old.py\0"])
def test_parse_name_status_rejects_a_truncated_record(output: str) -> None:
    with pytest.raises(ValueError, match="malformed git name-status record"):
        _ = parse_name_status(output)
