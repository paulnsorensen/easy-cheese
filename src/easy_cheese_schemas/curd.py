"""Curd block: the spec-locked decomposition a decomposer emits.

This is a *distinct* concept from the run-manifest curd in `manifest.py`
(id / status / retry_count), which tracks an in-flight dispatch once a run
exists. The curd block is the artifact /mold's curdle step or /cook's fallback
decompose gate produces *before* any run manifest exists. Field names
intentionally do not overlap, and the two types are not merged.

Two numbers make the block dispatchable rather than merely well-formed:
a wave wider than `MAX_WAVE_SIZE` outruns what one orchestrator can supervise,
and a curd smaller than `MIN_CURD_SURFACE` costs more to dispatch than to
absorb into a sibling.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from attrs import Attribute, define, field, validators

MAX_WAVE_SIZE = 4
MIN_CURD_SURFACE = 25


class DecomposerSource(str, Enum):
    """Which gate produced the block."""

    MOLD = "mold"
    COOK = "cook"


def _non_empty_string(_instance: object, attribute: Attribute[Any], value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{attribute.name} must be a non-empty string")


def _string_list(_instance: object, attribute: Attribute[Any], value: object) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{attribute.name} must be a list")
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{attribute.name}[{index}] must be a non-empty string")


def _non_empty_string_list(
    instance: object, attribute: Attribute[Any], value: object
) -> None:
    _string_list(instance, attribute, value)
    if not value:
        raise ValueError(f"{attribute.name} must be a non-empty list")


def _surface_floor(_instance: object, attribute: Attribute[Any], value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{attribute.name} must be a positive integer")
    if value < MIN_CURD_SURFACE:
        raise ValueError(
            f"{attribute.name}={value} is below the surface floor of "
            f"{MIN_CURD_SURFACE} -- this curd is a MERGE CANDIDATE: merge it "
            "into a sibling curd rather than dispatch a fresh coder for it"
        )


@define(frozen=True)
class Decomposer:
    """Provenance of the block, so a bad decomposition is traceable to the
    model and prompt that wrote it."""

    source: DecomposerSource
    model: str = field(validator=_non_empty_string)
    prompt_version: str = field(validator=_non_empty_string)


@define(frozen=True)
class PlannedCurd:
    """One dispatchable unit: a contract, the files it may touch, and how its
    completion is proved."""

    slug: str = field(validator=_non_empty_string)
    contract: str = field(validator=_non_empty_string)
    files: list[str] = field(validator=_non_empty_string_list)
    test_target: str = field(validator=_non_empty_string)
    acceptance: list[str] = field(validator=_non_empty_string_list)
    # Frozen interfaces this curd implements; a curd may depend on none, but
    # the key is declared either way.
    seed: list[str] = field(validator=_string_list)
    est_edit_lines: int = field(validator=_surface_floor)


@define(frozen=True)
class CurdBlock:
    """The locked decomposition: curds, the waves they dispatch in, and who
    decomposed them."""

    curds: list[PlannedCurd] = field(validator=validators.min_len(1))
    waves: list[list[str]] = field()
    decomposer: Decomposer = field()

    def __attrs_post_init__(self) -> None:
        self._reject_shared_files()
        self._reject_unschedulable_waves()

    def _reject_shared_files(self) -> None:
        owner: dict[str, str] = {}
        for curd in self.curds:
            for path in curd.files:
                if path in owner:
                    raise ValueError(
                        f"file {path!r} appears in curd {owner[path]!r} and curd "
                        f"{curd.slug!r} -- curd files must be pairwise disjoint"
                    )
                owner[path] = curd.slug

    def _reject_unschedulable_waves(self) -> None:
        known = {curd.slug for curd in self.curds}
        for index, wave in enumerate(self.waves, start=1):
            if len(wave) > MAX_WAVE_SIZE:
                raise ValueError(
                    f"waves[{index}] has {len(wave)} slugs, exceeding the max "
                    f"of {MAX_WAVE_SIZE}"
                )
            for slug in wave:
                if slug not in known:
                    raise ValueError(
                        f"waves[{index}] references unknown slug {slug!r}"
                    )
