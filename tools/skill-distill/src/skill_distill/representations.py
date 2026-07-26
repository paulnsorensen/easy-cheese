"""Invocation-loaded representation selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class RepresentationCandidate:
    name: str
    loaded_tokens: int
    behavior_passed: bool
    static_bytes: int | None = None

    def __post_init__(self) -> None:
        if not self.name or self.loaded_tokens < 0:
            raise ValueError("representation requires a name and non-negative token count")


@dataclass(frozen=True)
class RepresentationChoice:
    name: str
    loaded_tokens: int
    loaded_token_savings: int


def choose_representation(
    original_loaded_tokens: int,
    candidates: Iterable[RepresentationCandidate],
) -> RepresentationChoice:
    """Choose the lowest-cost passing variant when it saves loaded tokens."""
    if original_loaded_tokens < 0:
        raise ValueError("original token count must be non-negative")
    eligible = [
        candidate
        for candidate in candidates
        if candidate.behavior_passed and candidate.loaded_tokens < original_loaded_tokens
    ]
    if not eligible:
        raise ValueError("no passing representation has positive invocation-loaded savings")
    chosen = min(eligible, key=lambda candidate: (candidate.loaded_tokens, candidate.name))
    return RepresentationChoice(
        chosen.name,
        chosen.loaded_tokens,
        original_loaded_tokens - chosen.loaded_tokens,
    )


select_representation = choose_representation
