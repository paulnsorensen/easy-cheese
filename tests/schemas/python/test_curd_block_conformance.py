"""CurdBlock: src/fanout/curd_block.py vs easy_cheese_schemas.CurdBlock.

No divergence remains. The last one — an empty `curds` list passing
`validate_curd_block` while `CurdBlock` refused it — was judged a defect in the
*validator* rather than a rule the types had not caught up to, and was fixed
there; the row below now pins agreement.
"""

from __future__ import annotations

from typing import Any

import pytest
from easy_cheese_schemas import CurdBlock
from schema_conformance import (
    Case,
    Validator,
    agreed_invalid,
    agreed_valid,
    agreeing,
    assert_conforms,
    assert_table_is_honest,
    curd_block,
    divergent,
    ids,
    planned_curd,
)

ALPHA = planned_curd("alpha", ["src/alpha.ts"])
BETA = planned_curd("beta", ["src/beta.ts"])


def curd_without(key: str) -> dict[str, Any]:
    curd = planned_curd("alpha", ["src/alpha.ts"])
    del curd[key]
    return curd


def solo(**fields: Any) -> dict[str, Any]:
    """A one-curd block whose single curd carries `fields`."""
    curd = planned_curd("alpha", ["src/alpha.ts"])
    curd.update(fields)
    return curd_block([curd], [["alpha"]])


def with_decomposer(**fields: Any) -> dict[str, Any]:
    block = curd_block([ALPHA], [["alpha"]])
    block["decomposer"].update(fields)
    return block


CASES: list[Case] = [
    agreed_valid("valid two-curd block", curd_block([ALPHA, BETA], [["alpha", "beta"]])),
    agreed_invalid(
        "two curds sharing a file",
        curd_block(
            [ALPHA, planned_curd("beta", ["src/alpha.ts"])], [["alpha", "beta"]]
        ),
    ),
    agreed_invalid("wave referencing an unknown slug", curd_block([ALPHA], [["gamma"]])),
    agreed_invalid(
        "wave wider than MAX_WAVE_SIZE",
        curd_block(
            [planned_curd(f"c{index}", [f"src/c{index}.ts"]) for index in range(5)],
            [[f"c{index}" for index in range(5)]],
        ),
    ),
    agreed_invalid("curd below MIN_CURD_SURFACE", solo(est_edit_lines=5)),
    agreed_invalid("est_edit_lines zero", solo(est_edit_lines=0)),
    agreed_invalid("est_edit_lines as a bool", solo(est_edit_lines=True)),
    agreed_invalid("unknown decomposer source", with_decomposer(source="vibes")),
    agreed_invalid("missing seed key", curd_block([curd_without("seed")], [["alpha"]])),
    agreed_invalid("waves as a bare string", curd_block([ALPHA], "alpha")),
    agreed_invalid("curd files as a bare string", solo(files="src/alpha.ts")),
    agreed_invalid("block with no curds", curd_block([], [])),
]


def test_divergence_table_is_honest() -> None:
    assert_table_is_honest(CASES)


@pytest.mark.parametrize("case", agreeing(CASES), ids=ids(agreeing(CASES)))
def test_validator_and_type_agree(case: Case, curd_block_validator: Validator) -> None:
    assert_conforms(case, curd_block_validator, CurdBlock)


def test_no_known_divergence_remains() -> None:
    """Asserted rather than left to the empty-parameter skip below, so a
    divergence that opens later has to be added to the table deliberately."""
    assert divergent(CASES) == []


@pytest.mark.parametrize("case", divergent(CASES), ids=ids(divergent(CASES)))
def test_known_divergence_still_holds(
    case: Case, curd_block_validator: Validator
) -> None:
    assert_conforms(case, curd_block_validator, CurdBlock)
