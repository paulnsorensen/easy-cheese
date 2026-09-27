"""Two-objective scoring and the graduation gate for /cook candidates.

This module is pure and stdlib-only. It never runs an agent and never calls
tilth's benchmark harness; the caller injects an `evaluate` function that
returns rows shaped like tilth's `benchmark/run.py` JSONL rows. The optimizer
wiring (GEPA, the `agent_lab.py` CLI) lives in another module and imports
these functions; it does not duplicate the scoring or the graduation logic.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import json
from pathlib import Path
from typing import cast

from agent_lab_candidate import path_escapes
from agent_lab_candidate import write_components as _write_component_files


# The 2,000,000-byte cap mirrors prompt_lab.write_json's artifact size limit;
# this module stays import-free of prompt_lab (see the module docstring), so
# the cap is kept here instead of shared.
MAX_ARTIFACT_BYTES = 2_000_000

# A guard-violation vector must lose a Pareto comparison against every real
# run, however token-hungry that run is. Real token totals seen in practice
# stay well under this sentinel.
GUARD_TOKEN_PENALTY = 10_000_000.0

TOKEN_FIELDS = ("input_tokens", "output_tokens", "cache_creation_tokens", "cache_read_tokens")

Row = Mapping[str, object]
Vector = tuple[float, float]
Components = Mapping[str, str]
Evaluate = Callable[[Components, str], Sequence[Row]]


class ScoringError(Exception):
    """A scoring or graduation input is malformed."""


def token_total(row: Row) -> float:
    """Return the token objective: input plus output plus both cache fields."""
    return sum(float(cast(float, row.get(field, 0) or 0)) for field in TOKEN_FIELDS)


def score_vector(row: Row) -> Vector:
    """Return the two-objective vector `(correct, -tokens)` for one row.

    A guard-violation row (a row that carries a `guard` name) gets a fixed
    dominated vector instead of its measured tokens, so a guard violation can
    never win a Pareto comparison against a real run.
    """
    if row.get("guard"):
        return (0.0, -GUARD_TOKEN_PENALTY)
    if "correct" not in row:
        raise ScoringError("row is missing 'correct'")
    return (float(cast(float, row["correct"])), -token_total(row))


def side_info_scores(row: Row) -> dict[str, float]:
    """Build the `side_info['scores']` dict GEPA reads for one task row."""
    correct, neg_tokens = score_vector(row)
    return {"correct": correct, "neg_tokens": neg_tokens}


def dominates(a: Vector, b: Vector) -> bool:
    """Return True when vector `a` dominates vector `b`.

    `a` dominates `b` when it is at least as good on both axes and strictly
    better on at least one axis.
    """
    at_least_as_good = a[0] >= b[0] and a[1] >= b[1]
    strictly_better = a[0] > b[0] or a[1] > b[1]
    return at_least_as_good and strictly_better


def pareto_front(points: Sequence[tuple[str, Vector]]) -> list[str]:
    """Return the labels of the non-dominated points, in input order."""
    vectors = [vector for _, vector in points]
    front: list[str] = []
    for index, (label, vector) in enumerate(points):
        dominated = any(
            dominates(other, vector)
            for other_index, other in enumerate(vectors)
            if other_index != index
        )
        if not dominated:
            front.append(label)
    return front


def mean_vector(vectors: Sequence[Vector]) -> Vector:
    """Return the elementwise mean of `vectors`; public so `agent_lab.py`'s
    optimize CLI shares this instead of keeping its own copy.
    """
    count = len(vectors)
    return (
        sum(vector[0] for vector in vectors) / count,
        sum(vector[1] for vector in vectors) / count,
    )


def paired_comparison(
    seed_rows: Sequence[Row],
    candidate_rows: Sequence[Row],
    *,
    id_key: str = "task",
) -> tuple[Vector, Vector]:
    """Return the (seed, candidate) mean vectors over the shared task ids.

    Only task ids present in both row sets count, so an added or dropped task
    on one side never skews the comparison.
    """
    seed_by_id = {row[id_key]: row for row in seed_rows}
    candidate_by_id = {row[id_key]: row for row in candidate_rows}
    shared_ids = sorted(set(seed_by_id) & set(candidate_by_id), key=str)
    if not shared_ids:
        raise ScoringError("seed and candidate rows share no task ids")
    seed_vectors = [score_vector(seed_by_id[task_id]) for task_id in shared_ids]
    candidate_vectors = [score_vector(candidate_by_id[task_id]) for task_id in shared_ids]
    return mean_vector(seed_vectors), mean_vector(candidate_vectors)


def _validate_components(components: Components, *, label: str) -> None:
    for rel_path in components:
        if path_escapes(rel_path):
            raise ScoringError(
                f"{label} component path escapes the output directory: {rel_path}"
            )


def _write_components(root: Path, components: Components) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _write_component_files(root, dict(components))


def _write_json(path: Path, value: object) -> None:
    encoded = json.dumps(value, indent=2, sort_keys=True)
    if len(encoded) > MAX_ARTIFACT_BYTES:
        raise ScoringError("artifact exceeds output size limit")
    _ = path.write_text(encoded + "\n", encoding="utf-8")


def graduate(
    seed: Components,
    candidate: Components,
    *,
    evaluate: Evaluate,
    models: Sequence[str],
    output_dir: Path,
) -> dict[str, object]:
    """Evaluate seed and candidate on the holdout at each model and verdict them.

    `evaluate(components, model)` runs the sealed holdout, one rep, and
    returns tilth benchmark rows. The verdict is `promote` only when the
    candidate is non-dominated on every model, strictly better on at
    least one axis on at least one model, and never has a lower paired
    mean accuracy than the seed on any model -- a token-cheaper accuracy
    regression on one model must never be masked by a gain elsewhere;
    otherwise the verdict is `hold`. The returned `models` dict carries a
    `reason` per model that names which of these checks decided it. A
    `promote` writes the candidate components under
    `<output_dir>/best_candidate/` plus `<output_dir>/graduation.json`, and
    never writes anywhere else.
    """
    if not models:
        raise ScoringError("models must not be empty")
    _validate_components(seed, label="seed")
    _validate_components(candidate, label="candidate")
    per_model: dict[str, object] = {}
    non_dominated_everywhere = True
    better_somewhere = False
    accuracy_regressed = False
    for model in models:
        seed_rows = evaluate(seed, model)
        candidate_rows = evaluate(candidate, model)
        seed_vector, candidate_vector = paired_comparison(seed_rows, candidate_rows)
        model_dominated = dominates(seed_vector, candidate_vector)
        model_better = candidate_vector[0] > seed_vector[0] or candidate_vector[1] > seed_vector[1]
        model_regressed = candidate_vector[0] < seed_vector[0]
        if model_dominated:
            non_dominated_everywhere = False
        if model_better:
            better_somewhere = True
        if model_regressed:
            accuracy_regressed = True
            reason = "candidate accuracy is lower than seed accuracy"
        elif model_dominated:
            reason = "seed dominates candidate on both axes"
        elif model_better:
            reason = "candidate strictly improves on at least one axis"
        else:
            reason = "seed and candidate are equal on both axes"
        per_model[model] = {
            "seed": list(seed_vector),
            "candidate": list(candidate_vector),
            "reason": reason,
        }
    verdict = (
        "promote"
        if non_dominated_everywhere and better_somewhere and not accuracy_regressed
        else "hold"
    )
    result: dict[str, object] = {"verdict": verdict, "models": per_model}
    if verdict == "promote":
        _write_components(output_dir / "best_candidate", candidate)
        _write_json(output_dir / "graduation.json", result)
    return result
