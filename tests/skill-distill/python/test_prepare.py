"""Preparation tests for the fixed, deterministic 421-pair pilot."""

from __future__ import annotations

import hashlib
import json
import os
import struct
from pathlib import Path

import pytest

from skill_distill.cli import main
from skill_distill.io import (
    ReportValidationError,
    findings_for_adversarial_controls,
    read_adversarial_controls,
)
from skill_distill.prepare import prepare_to_path


PR_322_REPORT_SHA256 = "3a660e94a52855dcf08b6e8c1a1435fc78cf44a7bf991cefc5f9b8ac1c27f274"


def _endpoint(index: int, side: str, family: str) -> dict:
    return {
        "path": f"skills/{family}/{side}-{index}.md",
        "heading_path": [family, f"Heading {index}"],
        "part": 0,
        "source_hash": f"hash-{side}-{index}",
        "span": {"start": 1, "end": 2},
        "original_excerpt": f"{side} excerpt {index}",
        "token_count": 10,
    }


def _finding(
    identifier: str,
    score: float,
    family: str,
    graph_index: int,
    disposition: str,
) -> dict:
    graph_types = (
        {
            "directly_linked": True,
            "directed_distance": 1,
            "undirected_distance": 1,
            "same_component": True,
            "same_skill": False,
            "disconnected": False,
        },
        {
            "directly_linked": False,
            "directed_distance": None,
            "undirected_distance": 2,
            "same_component": True,
            "same_skill": True,
            "disconnected": False,
        },
        {
            "directly_linked": False,
            "directed_distance": None,
            "undirected_distance": 3,
            "same_component": True,
            "same_skill": False,
            "disconnected": False,
        },
        {
            "directly_linked": False,
            "directed_distance": None,
            "undirected_distance": None,
            "same_component": False,
            "same_skill": False,
            "disconnected": True,
        },
    )
    return {
        "id": identifier,
        "lane": "semantic",
        "detector": "embedding",
        "kind": "semantic",
        "left": _endpoint(graph_index, "left", family),
        "right": _endpoint(graph_index, "right", f"peer-{family}"),
        "graph": graph_types[graph_index % len(graph_types)],
        "cosine": score,
        "duplicate_tokens_estimate": 12,
        "disposition": disposition,
    }


def _control(finding: dict) -> dict:
    return {
        "category": "high-overlap",
        "evidence": {
            side: {
                key: finding[side][key]
                for key in ("path", "heading_path", "part", "source_hash", "span")
            }
            for side in ("left", "right")
        },
        "predicates": {
            key: finding[key]
            for key in ("lane", "detector", "kind", "disposition")
        },
    }


def _report() -> dict:
    high = [
        _finding(
            f"high-{index:03}",
            0.95,
            f"family-{index % 5}",
            index,
            "advisory",
        )
        for index in range(181)
    ]
    fill = [
        _finding(
            f"fill-{index:03}",
            0.899 - index / 100_000,
            f"family-{index % 5}",
            index,
            "advisory",
        )
        for index in range(18)
    ]
    review = [
        _finding(
            f"review-{index:03}",
            0.80 + (index % 9) / 100,
            f"family-{index % 7}",
            index,
            "advisory",
        )
        for index in range(240)
    ]
    exact_control = _finding("adversarial-exact", 0.0, "controls", 0, "unaccepted")
    exact_control.update({"kind": "exact", "detector": "normalized", "cosine": None})
    controls = [exact_control]
    controls.extend(
        _finding(
            f"adversarial-high-{index:03}", 0.96, "controls", index, "advisory"
        )
        for index in range(1, 14)
    )
    controls.extend(
        _finding(
            f"adversarial-low-{index:03}", 0.20, "controls", index, "advisory"
        )
        for index in range(14, 40)
    )
    return {
        "format": 1,
        "detector": {
            "version": "1",
            "model_lock_digest": "lock",
            "chunker": "h2-h3-v2",
            "pooling": "cls",
            "normalization": "l2",
        },
        "mode": "calibrate",
        "findings": high + fill + review + controls,
        "duplicate_components": [
            {
                "id": "component",
                "endpoints": ["left", "right"],
                "finding_ids": ["high-000"],
                "redundant_tokens_estimate": 12,
            }
        ],
        "frontmatter": [
            {
                "left": "skills/left.md",
                "right": "skills/right.md",
                "field": "description",
                "left_value": "left",
                "right_value": "right",
                "score": 0.5,
            }
        ],
        "trends": {
            "groups": [
                {
                    "lane": "semantic",
                    "graph_class": "disconnected",
                    "disposition": "advisory",
                    "current_findings": 1,
                    "baseline_findings": 0,
                    "current_estimated_duplicate_tokens": 12,
                    "baseline_estimated_duplicate_tokens": 0,
                }
            ]
        },
        "calibration": {
            "score_distribution": [
                {"min_score": -1.0, "max_score": 0.5, "count": 26},
                {"min_score": 0.5, "max_score": 0.7, "count": 0},
                {"min_score": 0.7, "max_score": 0.8, "count": 0},
                {"min_score": 0.8, "max_score": 0.9, "count": 258},
                {"min_score": 0.9, "max_score": 1.0, "count": 176},
            ],
            "samples": [
                {"left": "left", "right": "right", "score": 0.5, "label": "review"}
            ],
        },
    }


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    report = _report()
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    controls_path = tmp_path / "controls.yaml"
    controls_path.write_text(
        json.dumps(
            {
                "schema_version": "adversarial-controls-v1",
                "controls": [_control(finding) for finding in report["findings"][-40:]],
            }
        ),
        encoding="utf-8",
    )
    return report_path, controls_path


def test_prepare_is_byte_stable_and_preserves_the_source_report(
    tmp_path: Path,
) -> None:
    report_path, controls_path = _write_inputs(tmp_path)
    source_before = report_path.read_bytes()
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"

    first = prepare_to_path(report_path, controls_path, first_path)
    second = prepare_to_path(report_path, controls_path, second_path)

    assert report_path.read_bytes() == source_before
    assert first_path.read_bytes() == second_path.read_bytes()
    assert [pair.pair_id for pair in first.pairs] == [
        pair.pair_id for pair in second.pairs
    ]


def test_cli_prepare_executes_the_real_dataset_pipeline(tmp_path: Path) -> None:
    report_path, controls_path = _write_inputs(tmp_path)
    output_path = tmp_path / ".context" / "cli-dataset.json"

    assert main(
        [
            "prepare",
            "--report",
            str(report_path),
            "--adversarial-controls",
            str(controls_path),
            "--out",
            str(output_path),
        ]
    ) == 0

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "dataset-v1"
    assert len(payload["pairs"]) == 421
    assert {pair["selection"] for pair in payload["pairs"]} == {
        "block",
        "review",
        "adversarial",
    }

def test_cli_prepare_preserves_an_existing_human_frozen_run(tmp_path: Path) -> None:
    report_path, controls_path = _write_inputs(tmp_path)
    context = tmp_path / ".context"
    run_path = context / "run.json"
    labels_path = tmp_path / "human-labels.json"
    labels_path.write_text(
        json.dumps([{"pair_id": "pair", "relation": "conflict", "reviewer": "human"}]),
        encoding="utf-8",
    )
    from skill_distill.lifecycle import freeze_labels, initialize_run

    initialize_run(run_path, "frozen-run")
    freeze_labels(run_path, labels_path, "2026-07-26T12:00:00Z")
    run_before = run_path.read_bytes()
    output_path = context / "replacement-dataset.json"

    with pytest.raises(SystemExit) as error:
        main([
            "prepare",
            "--report", str(report_path),
            "--adversarial-controls", str(controls_path),
            "--out", str(output_path),
            "--run", str(run_path),
            "--run-id", "replacement-run",
        ])

    assert error.value.code == 2
    assert run_path.read_bytes() == run_before
    assert not output_path.exists()

def test_prepare_has_the_fixed_unique_composition(tmp_path: Path) -> None:
    report_path, controls_path = _write_inputs(tmp_path)
    dataset = prepare_to_path(report_path, controls_path, tmp_path / "dataset.json")

    assert len(dataset.pairs) == 421
    assert len({pair.pair_id for pair in dataset.pairs}) == 421
    assert [pair.selection for pair in dataset.pairs].count("block") == 181
    assert [pair.selection for pair in dataset.pairs].count("review") == 200
    assert [pair.selection for pair in dataset.pairs].count("adversarial") == 40
    assert {pair.score_decile for pair in dataset.pairs if pair.selection == "review"} >= {
        8,
    }
    assert len(
        {pair.graph_class for pair in dataset.pairs if pair.selection == "review"}
    ) == 4
    assert len(
        {pair.skill_family for pair in dataset.pairs if pair.selection == "review"}
    ) == 7


def test_prepare_reserves_controls_and_never_fills_block_from_review_band(
    tmp_path: Path,
) -> None:
    report_path, controls_path = _write_inputs(tmp_path)
    dataset = prepare_to_path(report_path, controls_path, tmp_path / "dataset.json")
    selections = {pair.pair_id: pair.selection for pair in dataset.pairs}

    assert selections["adversarial-exact"] == "adversarial"
    assert selections["adversarial-high-001"] == "adversarial"
    assert all(selections.get(f"fill-{index:03}") != "block" for index in range(18))
    assert all(selections[f"high-{index:03}"] == "block" for index in range(181))


def test_prepare_accepts_exact_and_semantic_block_threshold_boundary(
    tmp_path: Path,
) -> None:
    report = _report()
    exact = report["findings"][0]
    exact.update({"kind": "exact", "detector": "normalized", "cosine": None})
    report["findings"][180]["cosine"] = 0.9
    report_path, controls_path = _write_inputs(tmp_path)
    report_path.write_text(json.dumps(report), encoding="utf-8")

    dataset = prepare_to_path(report_path, controls_path, tmp_path / "dataset.json")
    selections = {pair.pair_id: pair.selection for pair in dataset.pairs}

    assert selections["high-000"] == "block"
    assert selections["high-180"] == "block"


def test_prepare_rejects_report_without_minimum_block_band_count(tmp_path: Path) -> None:
    report = _report()
    report["findings"][180]["cosine"] = 0.899
    report_path, controls_path = _write_inputs(tmp_path)
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(
        ReportValidationError,
        match="expected at least 181 unique non-control block-band pairs, found 180",
    ):
        prepare_to_path(report_path, controls_path, tmp_path / "dataset.json")


def test_prepare_truncates_excess_block_findings_deterministically(tmp_path: Path) -> None:
    report_path, controls_path = _write_inputs(tmp_path)
    report = _report()
    extra = _finding("extra-block-000", 0.99, "family-9", 0, "advisory")
    report["findings"] = [extra] + report["findings"]
    report_path.write_text(json.dumps(report), encoding="utf-8")

    dataset = prepare_to_path(report_path, controls_path, tmp_path / "dataset.json")
    selections = {pair.pair_id: pair.selection for pair in dataset.pairs}

    assert len(dataset.pairs) == 421
    assert [pair.selection for pair in dataset.pairs].count("block") == 181
    assert selections["extra-block-000"] == "block"
    assert all(selections[f"high-{index:03}"] == "block" for index in range(180))
    assert "high-180" not in selections


def test_tracked_adversarial_controls_use_endpoint_evidence() -> None:
    controls_path = (
        Path(__file__).parents[3]
        / "tools/skill-distill/labels/adversarial-controls-v1.yaml"
    )
    controls = read_adversarial_controls(controls_path)

    assert len(controls) == 40
    assert [control["category"] for control in controls].count("high-overlap") == 14
    assert [control["category"] for control in controls].count(
        "reversed-obligation"
    ) == 13
    assert [control["category"] for control in controls].count(
        "low-cosine-repeat"
    ) == 13


def test_tracked_adversarial_fixture_matches_pr_322_report(tmp_path: Path) -> None:
    report_path_value = os.environ.get("SKILL_DISTILL_PR_322_REPORT")
    if report_path_value is None:
        pytest.skip("SKILL_DISTILL_PR_322_REPORT is not set")

    repo_root = Path(__file__).parents[3]
    fixture = json.loads(
        (
            repo_root
            / "tools/skill-distill/fixtures/adversarial-report-findings-v1.json"
        ).read_text(encoding="utf-8")
    )
    report_path = Path(report_path_value)
    source_before = report_path.read_bytes()
    report_sha256 = hashlib.sha256(source_before).hexdigest()

    assert report_sha256 == PR_322_REPORT_SHA256
    assert fixture["source_report_sha256"] == report_sha256

    with pytest.raises(
        ReportValidationError,
        match="expected at least 181 unique non-control block-band pairs",
    ):
        prepare_to_path(
            report_path,
            repo_root / "tools/skill-distill/labels/adversarial-controls-v1.yaml",
            tmp_path / "dataset.json",
        )
    assert report_path.read_bytes() == source_before


def test_tracked_adversarial_controls_resolve_the_pr_322_fixture() -> None:
    repo_root = Path(__file__).parents[3]
    fixture = json.loads(
        (
            repo_root
            / "tools/skill-distill/fixtures/adversarial-report-findings-v1.json"
        ).read_text(encoding="utf-8")
    )
    assert len(fixture["findings"]) == 40

    controls = read_adversarial_controls(
        repo_root / "tools/skill-distill/labels/adversarial-controls-v1.yaml"
    )
    selected = findings_for_adversarial_controls(fixture["findings"], controls)

    assert len(selected) == 40
    assert {finding["id"] for finding in selected} == {
        finding["id"] for finding in fixture["findings"]
    }


def test_prepare_rejects_malformed_or_impossible_reports(tmp_path: Path) -> None:
    report_path, controls_path = _write_inputs(tmp_path)
    report = _report()
    report["findings"][1]["id"] = report["findings"][0]["id"]
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReportValidationError, match="repeats finding id"):
        prepare_to_path(report_path, controls_path, tmp_path / "dataset.json")


def test_prepare_rejects_unmatched_adversarial_evidence(tmp_path: Path) -> None:
    report_path, controls_path = _write_inputs(tmp_path)
    controls = json.loads(controls_path.read_text(encoding="utf-8"))
    controls["controls"][0]["evidence"]["left"]["source_hash"] = "absent"
    controls_path.write_text(json.dumps(controls), encoding="utf-8")

    with pytest.raises(
        ReportValidationError, match="matched 0 overlap report findings"
    ):
        prepare_to_path(report_path, controls_path, tmp_path / "dataset.json")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda report: report.__setitem__("format", True), "format or mode"),
        (
            lambda report: report["findings"][0].__setitem__(
                "duplicate_tokens_estimate", True
            ),
            "duplicate_tokens_estimate",
        ),
        (
            lambda report: report["findings"][0]["left"].__setitem__("part", True),
            "left.part",
        ),
        (
            lambda report: report["findings"][0]["graph"].__setitem__(
                "directed_distance", True
            ),
            "directed_distance",
        ),
        (
            lambda report: report["frontmatter"][0].__setitem__("score", True),
            "frontmatter has invalid",
        ),
        (
            lambda report: report["trends"]["groups"][0].__setitem__(
                "current_findings", True
            ),
            "trends.groups has invalid",
        ),
        (
            lambda report: report["duplicate_components"][0].__setitem__(
                "endpoints", "left"
            ),
            "duplicate_components has invalid",
        ),
        (
            lambda report: report["calibration"]["score_distribution"][0].__setitem__(
                "count", True
            ),
            "score_distribution has invalid",
        ),
        (
            lambda report: report["calibration"]["samples"][0].__setitem__(
                "label", 1
            ),
            "samples has invalid",
        ),
        (
            lambda report: report.__setitem__(
                "reviewed_calibration",
                {"digest": 1, "thresholds": {"review": 0.8, "block": 0.9}},
            ),
            "reviewed_calibration.digest",
        ),
        (
            lambda report: report.__setitem__(
                "reviewed_calibration",
                {
                    "digest": "calibration",
                    "thresholds": {"review": True, "block": 0.9},
                },
            ),
            "thresholds must be finite",
        ),
    ],
)
def test_prepare_rejects_invalid_rust_report_field_types(
    tmp_path: Path, change, message: str
) -> None:
    report_path, controls_path = _write_inputs(tmp_path)
    report = _report()
    change(report)
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReportValidationError, match=message):
        prepare_to_path(report_path, controls_path, tmp_path / "dataset.json")


def test_prepare_rejects_rust_usize_overflow(tmp_path: Path) -> None:
    report_path, controls_path = _write_inputs(tmp_path)
    report = _report()
    report["findings"][0]["duplicate_tokens_estimate"] = 1 << (
        struct.calcsize("P") * 8
    )
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReportValidationError, match="duplicate_tokens_estimate"):
        prepare_to_path(report_path, controls_path, tmp_path / "dataset.json")


def test_prepare_rejects_rust_f32_overflow(tmp_path: Path) -> None:
    report_path, controls_path = _write_inputs(tmp_path)
    report = _report()
    report["frontmatter"][0]["score"] = float.fromhex("0x1.fffffep+128")
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReportValidationError, match="frontmatter has invalid"):
        prepare_to_path(report_path, controls_path, tmp_path / "dataset.json")
