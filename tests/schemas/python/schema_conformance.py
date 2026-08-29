"""The conformance harness: one verdict pair per fixture, and the payload
builders every contract's case table is written against.

The core assertion each contract's suite makes is a biconditional -- a payload
the fan-out validator accepts must structure cleanly through the matching attrs
type, and one it rejects must fail to structure. A `Case` records both verdicts
explicitly, so the tables double as the ledger of how far the two sources of
truth have drifted: any case whose two verdicts differ must name the divergence
it pins, and any case that names one must actually diverge.

The payload builders are lifted from tests/fanout/python/test_validate_manifest.py
and test_curd_block.py rather than invented here, so both suites argue about the
same documents.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from easy_cheese_schemas import load

Validator = Callable[[dict[str, object]], list[str]]


def as_dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value)


def as_list(value: object) -> list[object]:
    return cast(list[object], value)


@dataclass(frozen=True)
class Case:
    """One fixture and the verdict each source of truth returns for it."""

    name: str
    payload: dict[str, object]
    validator_accepts: bool
    structures: bool
    divergence: str | None = None

    @property
    def diverges(self) -> bool:
        return self.validator_accepts != self.structures


def agreed_valid(name: str, payload: dict[str, object]) -> Case:
    """Both sides accept."""
    return Case(name, payload, validator_accepts=True, structures=True)


def agreed_invalid(name: str, payload: dict[str, object]) -> Case:
    """Both sides reject."""
    return Case(name, payload, validator_accepts=False, structures=False)


def looser(name: str, payload: dict[str, object], gap: str) -> Case:
    """The validator rejects and the attrs type does not: a rule the types do
    not carry yet. `gap` names the missing rule."""
    return Case(name, payload, validator_accepts=False, structures=True, divergence=gap)


def stricter(name: str, payload: dict[str, object], gap: str) -> Case:
    """The attrs type rejects and the validator does not: a rule only the types
    carry. `gap` names the extra rule."""
    return Case(name, payload, validator_accepts=True, structures=False, divergence=gap)


def assert_conforms(case: Case, validator: Validator, cls: type[object]) -> None:
    """Pin both verdicts. A verdict that moves is drift between the two sources
    of truth, whether it closes a divergence or opens one."""
    errors = validator(case.payload)
    loaded = load(case.payload, cls, strict=True)

    assert (errors == []) is case.validator_accepts, (
        f"{case.name}: validator verdict moved; errors={errors}"
    )
    assert (loaded.value is not None) is case.structures, (
        f"{case.name}: {cls.__name__} verdict moved; problems={loaded.problems}"
    )
    if case.structures:
        assert loaded.problems == (), (
            f"{case.name}: {cls.__name__} structured but still reported "
            f"{loaded.problems}"
        )
    else:
        assert loaded.problems, (
            f"{case.name}: {cls.__name__} refused the payload without saying why"
        )


def assert_table_is_honest(cases: list[Case]) -> None:
    """Every divergent case names its gap and every named gap is real, so the
    divergence list cannot rot into decoration."""
    mislabelled = [
        case.name for case in cases if case.diverges != (case.divergence is not None)
    ]
    assert mislabelled == [], (
        f"cases whose divergence label disagrees with their verdicts: {mislabelled}"
    )
    names = [case.name for case in cases]
    assert len(set(names)) == len(names), f"duplicate case names in table: {names}"


def ids(cases: list[Case]) -> list[str]:
    return [case.name for case in cases]


def agreeing(cases: list[Case]) -> list[Case]:
    return [case for case in cases if not case.diverges]


def divergent(cases: list[Case]) -> list[Case]:
    return [case for case in cases if case.diverges]


# ---------------------------------------------------------------------------
# Payload builders (harvested from tests/fanout/python/)
# ---------------------------------------------------------------------------


def curd_records(count: int = 5) -> list[dict[str, object]]:
    return [
        {
            "id": index + 1,
            "behavior": f"Implement feature {index + 1}",
            "acceptance_criterion": f"AC {index + 1}",
            "files": [f"src/feature_{index}.ts"],
            "test_target": f"pytest src/feature_{index}.ts",
            "status": "pending",
            "retry_count": 0,
        }
        for index in range(count)
    ]


def wiring_row(id_: str = "W1", depends_on: list[str] | None = None) -> dict[str, object]:
    return {
        "id": id_,
        "type": "barrel_export",
        "file": f"src/index_{id_}.ts",
        "depends_on": list(depends_on or []),
        "status": "pending",
    }


def review_context() -> dict[str, object]:
    return {
        "base_commit": "a" * 40,
        "reviewed_tree_oid": "B" * 64,
        "diff_hash": "sha256:" + "c" * 64,
        "scope": ["src/feature.ts"],
    }


def baseline() -> dict[str, object]:
    return {
        "captured_at": "2026-05-14T10:00:00Z",
        "gates": [
            {
                "cmd": "just check",
                "failures": [
                    {
                        "suite": "pytest",
                        "test_id": "tests/test_foo.py::test_bar",
                        "signature": "AssertionError: expected 1 got 2",
                    }
                ],
            }
        ],
    }


def run_manifest() -> dict[str, object]:
    return {
        "slug": "feature-name",
        "spec_path": ".cheese/specs/feature-name.md",
        "created": "2026-05-14T10:00:00Z",
        "phase": "gate_approved",
        "quality_gates": ["just check"],
        "host_capabilities": {"gh": True},
        "agent_resolution": {
            "request": {
                "work": "test",
                "preferred_types": ["planner"],
                "required_tools": ["read"],
                "permissions": "read-only",
                "isolation": "fresh-context",
                "minimum_power": "powerful",
                "effort": "high",
            },
            "attempts": [
                {
                    "type": "planner",
                    "model": "test",
                    "power": "powerful",
                    "result": "accepted",
                    "reason": "exact",
                }
            ],
            "resolved": {
                "type": "planner",
                "model": "test",
                "power": "powerful",
                "effort": "high",
                "topology": "sequential",
            },
            "fallback_reason": None,
            "degraded": False,
            "permission_enforcement": "tool-restricted",
        },
        "seed": {"items": []},
        "curds": curd_records(),
        "wiring": [wiring_row()],
    }


def pr_plan() -> dict[str, object]:
    return {
        "shape": "single",
        "groups": [
            {
                "branch": "ultracook/feature-name/pr-1",
                "title": "feat(feature): ship",
                "base": "main",
                "commits": ["abc1234"],
                "depends_on": [],
            }
        ],
    }


def pr_group(branch: str, base: str = "main") -> dict[str, object]:
    return {
        "branch": branch,
        "title": f"feat: {branch}",
        "base": base,
        "commits": ["abc1234"],
        "depends_on": [],
    }


def planned_curd(slug: str, files: object, est_edit_lines: int = 25) -> dict[str, object]:
    return {
        "slug": slug,
        "contract": f"Implement {slug}.",
        "files": files,
        "test_target": f"pytest tests/test_{slug}.py",
        "acceptance": [f"{slug} behaves correctly"],
        "seed": [],
        "est_edit_lines": est_edit_lines,
    }


def curd_block(curds: object, waves: object) -> dict[str, object]:
    return {
        "curds": curds,
        "waves": waves,
        "decomposer": {
            "source": "cook",
            "model": "claude-sonnet-5",
            "prompt_version": "abc123",
        },
    }
