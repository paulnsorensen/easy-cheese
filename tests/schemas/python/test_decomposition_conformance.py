"""Decomposition: src/fanout/validate_decomposition.py vs Decomposition.

A decomposition is written before any run exists, so `Decomposition` reads
`DecomposedCurd` -- behaviour, acceptance criterion, files, test target -- and
leaves the dispatch lifecycle to `CurdRecord`. The pre-run case below pins that:
an artifact with no id/status/retry_count is what the validator sees, and the
type now reads it too.
"""

from __future__ import annotations

import pytest
from easy_cheese_schemas import Decomposition
from schema_conformance import (
    Case,
    Validator,
    agreed_invalid,
    agreed_valid,
    agreeing,
    as_list,
    assert_conforms,
    assert_table_is_honest,
    curd_records,
    divergent,
    ids,
    wiring_row,
)

LIFECYCLE_KEYS = ("id", "status", "retry_count")


def decomposition(
    curds: list[dict[str, object]], wiring: list[dict[str, object]] | None = None
) -> dict[str, object]:
    return {"curds": curds, "wiring": list(wiring or [])}


def pre_run_curds(count: int) -> list[dict[str, object]]:
    """The curds as a decomposition writes them: no dispatch lifecycle yet."""
    return [
        {key: value for key, value in curd.items() if key not in LIFECYCLE_KEYS}
        for curd in curd_records(count)
    ]


def lone_curd(**fields: object) -> list[dict[str, object]]:
    curds = curd_records(1)
    curds[0].update(fields)
    return curds


def lone_curd_without(key: str) -> list[dict[str, object]]:
    curds = curd_records(1)
    del curds[0][key]
    return curds


def shared_files() -> list[dict[str, object]]:
    curds = curd_records(2)
    curds[1]["files"] = list(as_list(curds[0]["files"]))
    return curds


CASES: list[Case] = [
    agreed_valid("three disjoint curds", decomposition(curd_records(3))),
    agreed_valid("lone curd", decomposition(curd_records(1))),
    agreed_valid(
        "pre-run curds carrying no dispatch lifecycle",
        decomposition(pre_run_curds(3)),
    ),
    agreed_invalid("zero curds", decomposition([])),
    agreed_invalid("two curds sharing a file", decomposition(shared_files())),
    agreed_invalid(
        "two-verb behavior",
        decomposition(lone_curd(behavior="Adds a parser and removes the old one")),
    ),
    agreed_invalid(
        "missing acceptance_criterion",
        decomposition(lone_curd_without("acceptance_criterion")),
    ),
    agreed_invalid(
        "wiring depends_on an unknown W-id",
        decomposition(curd_records(1), [wiring_row("W1", ["W9"])]),
    ),
    agreed_invalid(
        "wiring DAG cycle",
        decomposition(
            curd_records(1), [wiring_row("W1", ["W2"]), wiring_row("W2", ["W1"])]
        ),
    ),
    agreed_invalid("lone curd missing files", decomposition(lone_curd_without("files"))),
    agreed_invalid(
        "lone curd with files as a bare string", decomposition(lone_curd(files="src/a.ts"))
    ),
]


def test_divergence_table_is_honest() -> None:
    assert_table_is_honest(CASES)


@pytest.mark.parametrize("case", agreeing(CASES), ids=ids(agreeing(CASES)))
def test_validator_and_type_agree(
    case: Case, decomposition_validator: Validator
) -> None:
    assert_conforms(case, decomposition_validator, Decomposition)


def test_no_known_divergence_remains() -> None:
    """Asserted rather than left to the empty-parameter skip below, so a
    divergence that opens later has to be added to the table deliberately."""
    assert divergent(CASES) == []


@pytest.mark.parametrize("case", divergent(CASES), ids=ids(divergent(CASES)))
def test_known_divergence_still_holds(
    case: Case, decomposition_validator: Validator
) -> None:
    assert_conforms(case, decomposition_validator, Decomposition)
