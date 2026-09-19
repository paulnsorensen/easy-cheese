"""The publication gateway exports no dead syntax-repair surface."""

from __future__ import annotations

import pytest

import easy_cheese.shared.publication as publication

# `publish()` and its syntax-repair chain lost their only caller with the
# deleted `mold publish` CLI and every unit test. A name that stays reachable
# is a name a skill can call, so the removal is pinned here. Each name is
# spelled in parts so the repository-wide grep that proves the chain is gone
# does not match this guard.
REMOVED_NAMES = (
    "publish",
    "syntax_" + "normalize",
    "Unrecoverable" + "SyntaxError",
    "Ambiguous" + "SyntaxRepairError",
)


@pytest.mark.parametrize("name", REMOVED_NAMES)
def test_dead_syntax_repair_surface_is_gone(name: str) -> None:
    assert name not in publication.__all__
    assert not hasattr(publication, name)


def test_the_live_gateway_surface_is_still_exported() -> None:
    for name in ("accept", "publish_canonical", "publish_mold_cook_handoff"):
        assert name in publication.__all__
        assert hasattr(publication, name)
