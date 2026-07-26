"""Deterministically prepare the fixed semantic-distillation pilot dataset."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .contracts import DatasetV1
from .io import (
    ReportValidationError,
    findings_for_adversarial_controls,
    pair_from_finding,
    read_adversarial_controls,
    read_overlap_report,
    report_block_threshold,
    report_review_threshold,
    sha256_bytes,
    write_canonical_json,
)

BLOCK_PAIR_COUNT = 181
REVIEW_SAMPLE_COUNT = 200
ADVERSARIAL_CONTROL_COUNT = 40
PILOT_PAIR_COUNT = BLOCK_PAIR_COUNT + REVIEW_SAMPLE_COUNT + ADVERSARIAL_CONTROL_COUNT
_PREPROCESSING_VERSION = b"skill-distill-prepare-v2:controls-block-review"


def prepare_dataset(report_path: Path, controls_path: Path) -> DatasetV1:
    """Select the fixed 181/200/40 pilot composition without changing the report."""
    report, source_digest = read_overlap_report(report_path)
    block = report_block_threshold(report)
    review = report_review_threshold(report)
    controls = read_adversarial_controls(controls_path)
    selected_controls = findings_for_adversarial_controls(
        report["findings"], controls
    )
    findings = {finding["id"]: finding for finding in report["findings"]}
    control_ids = {finding["id"] for finding in selected_controls}

    block_findings = sorted(
        (
            finding
            for finding in findings.values()
            if finding["id"] not in control_ids and _is_block(finding, block)
        ),
        key=_block_rank,
    )
    if len(block_findings) < BLOCK_PAIR_COUNT:
        raise ReportValidationError(
            f"expected at least {BLOCK_PAIR_COUNT} unique non-control block-band pairs, "
            f"found {len(block_findings)}"
        )
    block_findings = block_findings[:BLOCK_PAIR_COUNT]
    block_ids = {finding["id"] for finding in block_findings}

    review_findings = [
        finding
        for finding in findings.values()
        if _is_review(finding, review, block)
        and finding["id"] not in control_ids
        and finding["id"] not in block_ids
    ]
    selected_review = _stratified_review_sample(review_findings)
    if len(selected_review) != REVIEW_SAMPLE_COUNT:
        raise ReportValidationError(
            f"expected at least {REVIEW_SAMPLE_COUNT} non-control review-band pairs, "
            f"found {len(selected_review)}"
        )

    pairs = tuple(
        [
            pair_from_finding(finding, "block")
            for finding in sorted(block_findings, key=lambda item: item["id"])
        ]
        + [pair_from_finding(finding, "review") for finding in selected_review]
        + [
            pair_from_finding(finding, "adversarial")
            for finding in selected_controls
        ]
    )
    if (
        len(pairs) != PILOT_PAIR_COUNT
        or len({pair.pair_id for pair in pairs}) != PILOT_PAIR_COUNT
    ):
        raise ReportValidationError("prepared pilot does not contain 421 unique pairs")
    return DatasetV1(
        source_digest, sha256_bytes(_PREPROCESSING_VERSION), pairs
    )


def prepare_to_path(
    report_path: Path, controls_path: Path, output_path: Path
) -> DatasetV1:
    dataset = prepare_dataset(report_path, controls_path)
    write_canonical_json(output_path, _dataset_dict(dataset))
    return dataset


def _dataset_dict(dataset: DatasetV1) -> dict:
    return {
        "source_report_digest": dataset.source_report_digest,
        "preprocessing_digest": dataset.preprocessing_digest,
        "pairs": [
            {
                "pair_id": pair.pair_id,
                "left": _plain(pair.left),
                "right": _plain(pair.right),
                "lane": pair.lane,
                "detector": pair.detector,
                "kind": pair.kind,
                "graph": _plain(pair.graph),
                "cosine": pair.cosine,
                "duplicate_tokens_estimate": pair.duplicate_tokens_estimate,
                "disposition": pair.disposition,
                "selection": pair.selection,
                "score_decile": pair.score_decile,
                "graph_class": pair.graph_class,
                "skill_family": pair.skill_family,
                "schema_version": pair.schema_version,
            }
            for pair in dataset.pairs
        ],
        "schema_version": dataset.schema_version,
    }


def _plain(value):
    if isinstance(value, dict) or hasattr(value, "items"):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _block_rank(finding: dict) -> tuple[bool, float, str]:
    score = finding["cosine"] if finding["cosine"] is not None else 0.0
    return finding["kind"] != "exact", -score, finding["id"]


def _is_block(finding: dict, block: float) -> bool:
    return finding["kind"] == "exact" or (
        finding["kind"] == "semantic" and finding["cosine"] >= block
    )


def _is_review(finding: dict, review: float, block: float) -> bool:
    return (
        finding["kind"] == "semantic"
        and review <= finding["cosine"] < block
    )


def _stratified_review_sample(findings: list[dict]) -> list[dict]:
    strata: dict[tuple[int, str, str], list[dict]] = {}
    for finding in findings:
        pair = pair_from_finding(finding, "review")
        key = (pair.score_decile or 0, pair.graph_class, pair.skill_family)
        strata.setdefault(key, []).append(finding)
    for key, members in strata.items():
        members.sort(key=lambda finding: _stable_rank(key, finding["id"]))
    selected: list[dict] = []
    while len(selected) < REVIEW_SAMPLE_COUNT:
        progressed = False
        for key in sorted(strata):
            if strata[key]:
                selected.append(strata[key].pop(0))
                progressed = True
                if len(selected) == REVIEW_SAMPLE_COUNT:
                    break
        if not progressed:
            break
    return selected


def _stable_rank(
    stratum: tuple[int, str, str], pair_id: str
) -> tuple[str, str]:
    encoded = "\x1f".join(
        (str(stratum[0]), stratum[1], stratum[2], pair_id)
    ).encode()
    return hashlib.sha256(encoded).hexdigest(), pair_id
