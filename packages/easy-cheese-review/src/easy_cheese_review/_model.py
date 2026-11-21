"""Value types for review evidence: hits, facts, and the scan result."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

FactValue = Literal["yes", "no", "unknown"]

# The four review dimensions that a deterministic fact powers.
FACT_NAMES: tuple[str, ...] = ("compat", "dependencies", "tests", "scope")


@dataclass(frozen=True)
class Fact:
    """One deterministic answer for a review dimension, with its detail."""

    value: FactValue
    detail: Mapping[str, object]

    def to_json(self) -> dict[str, object]:
        return {"value": self.value, "detail": dict(self.detail)}


@dataclass(frozen=True)
class Hit:
    """One rule match on a changed file. Lines are 1-based and inclusive."""

    rule_id: str
    dimension: str
    base: str
    path: str
    line: int
    end_line: int
    message: str

    def to_json(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "dimension": self.dimension,
            "base": self.base,
            "path": self.path,
            "line": self.line,
            "end_line": self.end_line,
            "message": self.message,
        }


@dataclass(frozen=True)
class Evidence:
    """The scan result: `status` is `ok` or `failed:<reason>`."""

    status: str
    hits: tuple[Hit, ...]
    facts: Mapping[str, Fact]

    def to_json(self) -> dict[str, object]:
        return {
            "scan": {"status": self.status},
            "hits": [hit.to_json() for hit in self.hits],
            "facts": {name: fact.to_json() for name, fact in self.facts.items()},
        }
