"""The suite is worthless if either side is the wrong copy.

Three things have to be true before a conformance verdict means anything, and
none of them is visible in a passing case table: the attrs types must come from
`src/` (not the copy ultracook.pyz vendors), the validators must come from the
built bundle (the artifact /ultracook actually runs), and attrs/cattrs must come
from `vendor/` -- which is only true if the repo-root conftest ran before this
directory's conftest prepended the .pyz. `pytest tests/schemas/python` is a
supported invocation, so that ordering is asserted rather than assumed.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import attrs
import cattrs
import easy_cheese_schemas

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_schema_types_come_from_src() -> None:
    assert easy_cheese_schemas.__file__ is not None
    assert Path(easy_cheese_schemas.__file__).is_relative_to(REPO_ROOT / "src"), (
        f"easy_cheese_schemas resolved to {easy_cheese_schemas.__file__}, not src/ "
        "-- the bundle's vendored copy is shadowing the package under test"
    )


def test_validators_come_from_the_built_bundle(bundle: Path) -> None:
    # curd_block is absent: demoted to a direct src/ module when its dead
    # ultracook registration was pruned (spec pyz-pipeline-contracts).
    for name in (
        "validate_manifest",
        "validate_decomposition",
        "validate_pr_plan",
    ):
        module = importlib.import_module(name)
        assert module.__file__ is not None
        assert module.__file__.startswith(str(bundle)), (
            f"{name} resolved to {module.__file__}, not the ultracook bundle"
        )


def test_attrs_and_cattrs_come_from_the_vendor_tree() -> None:
    for module in (attrs, cattrs):
        assert module.__file__ is not None
        assert Path(module.__file__).is_relative_to(REPO_ROOT / "vendor"), (
            f"{module.__name__} resolved to {module.__file__}, not vendor/ -- the "
            "repo-root conftest did not bind it before a .pyz joined sys.path"
        )
