"""Deterministic behavior-matrix gates for rewrite variants."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .contracts import BehaviorScorecard


@dataclass(frozen=True)
class ScenarioBehavior:
    scenario: str
    critical_distortions: int
    original_noncritical_rate: float | None
    noncritical_rate: float | None
    allowed_degradation: float | None
    passed: bool


@dataclass(frozen=True)
class BehaviorGate:
    scenarios: tuple[ScenarioBehavior, ...]

    @property
    def passed(self) -> bool:
        return bool(self.scenarios) and all(scenario.passed for scenario in self.scenarios)


def _validate_matrix(rows: list[BehaviorScorecard]) -> None:
    by_obligation: dict[str, list[BehaviorScorecard]] = defaultdict(list)
    for row in rows:
        if row.passed != (row.expected == row.observed):
            raise ValueError(f"inconsistent scorecard row {row.matrix_id}:{row.obligation_id}")
        by_obligation[row.obligation_id].append(row)
    for obligation_id, obligation_rows in by_obligation.items():
        coordinates = {(row.phrasing, row.repetition) for row in obligation_rows}
        phrasings = {row.phrasing for row in obligation_rows}
        if len(obligation_rows) != 9 or len(phrasings) != 3 or {row.repetition for row in obligation_rows} != {1, 2, 3} or len(coordinates) != 9:
            raise ValueError(f"{obligation_id} does not form a 3-by-3 matrix")


def _obligation_signature(rows: list[BehaviorScorecard]) -> dict[str, bool]:
    signature: dict[str, bool] = {}
    for row in rows:
        classification = signature.setdefault(row.obligation_id, row.critical)
        if classification != row.critical:
            raise ValueError(f"{row.obligation_id} has inconsistent critical classification")
    return signature


def _rate(rows: list[BehaviorScorecard]) -> float | None:
    noncritical = [row.passed for row in rows if not row.critical]
    return sum(noncritical) / len(noncritical) if noncritical else None


def evaluate_behavior(
    original_rows: Iterable[BehaviorScorecard],
    variant_rows: Iterable[BehaviorScorecard],
) -> BehaviorGate:
    """Compare two original matrices with one variant matrix per scenario."""
    grouped_original: dict[str, dict[str, list[BehaviorScorecard]]] = defaultdict(lambda: defaultdict(list))
    grouped_variant: dict[str, dict[str, list[BehaviorScorecard]]] = defaultdict(lambda: defaultdict(list))
    for row in original_rows:
        grouped_original[row.scenario][row.matrix_id].append(row)
    for row in variant_rows:
        grouped_variant[row.scenario][row.matrix_id].append(row)
    if set(grouped_original) != set(grouped_variant) or not grouped_original:
        raise ValueError("original and variant scenarios must match")

    results = []
    for scenario in sorted(grouped_original):
        originals = grouped_original[scenario]
        variants = grouped_variant[scenario]
        if len(originals) != 2 or len(variants) != 1:
            raise ValueError(f"scenario {scenario} requires two original matrices and one variant matrix")
        for rows in (*originals.values(), *variants.values()):
            _validate_matrix(rows)
        if any(not row.passed for rows in originals.values() for row in rows if row.critical):
            raise ValueError(f"scenario {scenario} has an invalid critical baseline")
        signatures = [_obligation_signature(rows) for rows in (*originals.values(), *variants.values())]
        if any(signature != signatures[0] for signature in signatures[1:]):
            raise ValueError(f"scenario {scenario} obligation signatures differ")

        variant = next(iter(variants.values()))
        critical_distortions = sum(not row.passed for row in variant if row.critical)
        original_rates = [_rate(rows) for rows in originals.values()]
        variant_rate = _rate(variant)
        if all(rate is None for rate in original_rates):
            baseline_rate = allowed = None
            noncritical_passed = variant_rate is None
        elif any(rate is None for rate in original_rates) or variant_rate is None:
            raise ValueError(f"scenario {scenario} non-critical fixtures differ")
        else:
            first, second = original_rates
            assert first is not None and second is not None and variant_rate is not None
            baseline_rate = (first + second) / 2
            allowed = min(abs(first - second), 0.05)
            noncritical_passed = baseline_rate - variant_rate <= allowed + 1e-12
        results.append(
            ScenarioBehavior(
                scenario,
                critical_distortions,
                baseline_rate,
                variant_rate,
                allowed,
                critical_distortions == 0 and noncritical_passed,
            )
        )
    return BehaviorGate(tuple(results))
