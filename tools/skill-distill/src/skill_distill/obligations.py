"""Signed behavioral obligations with exact source provenance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ObligationCategory(StrEnum):
    TRIGGER = "trigger"
    ROUTING = "routing"
    TOOL = "tool"
    WRITE = "write"
    FALLBACK = "fallback"
    HALT = "halt"
    ARTIFACT = "artifact"
    OUTPUT_FIELD = "output-field"
    VERIFICATION = "verification"
    PROHIBITION = "prohibition"


class Polarity(StrEnum):
    REQUIRED = "required"
    PROHIBITED = "prohibited"


@dataclass(frozen=True)
class SourceSpan:
    path: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("source span path is required")
        if self.start < 1 or self.end < self.start:
            raise ValueError("source span must be a non-empty inclusive range")


@dataclass(frozen=True)
class ObligationAtomV1:
    category: ObligationCategory
    polarity: Polarity
    action: str
    object: str
    condition: str
    order: int
    source_span: SourceSpan
    schema_version: str = "obligation-atom-v1"

    def __post_init__(self) -> None:
        if not self.action or not self.object:
            raise ValueError("obligation action and object are required")
        if self.order < 0:
            raise ValueError("obligation order must be non-negative")
