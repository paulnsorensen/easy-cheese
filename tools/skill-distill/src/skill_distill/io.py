"""Strict readers and canonical writers for skill-distill evidence."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import yaml

from .contracts import PairEvidenceV1


class ReportValidationError(ValueError):
    """Raised when an overlap analyzer report cannot be used as evidence."""


_REPORT_KEYS = {
    "format",
    "detector",
    "mode",
    "findings",
    "duplicate_components",
    "frontmatter",
    "trends",
    "calibration",
    "reviewed_calibration",
}
_DETECTOR_KEYS = {"version", "model_lock_digest", "chunker", "pooling", "normalization"}
_FINDING_KEYS = {
    "id",
    "lane",
    "detector",
    "kind",
    "left",
    "right",
    "graph",
    "cosine",
    "duplicate_tokens_estimate",
    "disposition",
}
_ENDPOINT_KEYS = {
    "path",
    "heading_path",
    "part",
    "source_hash",
    "span",
    "original_excerpt",
    "token_count",
}
_GRAPH_KEYS = {
    "directly_linked",
    "directed_distance",
    "undirected_distance",
    "same_component",
    "same_skill",
    "disconnected",
}
_CONTROL_KEYS = {"category", "evidence", "predicates"}
_CONTROL_CATEGORIES = {"high-overlap", "reversed-obligation", "low-cosine-repeat"}
_CONTROL_EVIDENCE_KEYS = {"left", "right"}
_CONTROL_ENDPOINT_KEYS = {"path", "heading_path", "part", "source_hash", "span"}
_CONTROL_PREDICATE_KEYS = {"lane", "detector", "kind", "disposition"}


def canonical_json_bytes(value: Any) -> bytes:
    """Return the sole JSON serialization used for generated evidence."""
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_canonical_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def read_overlap_report(path: Path) -> tuple[dict[str, Any], str]:
    """Read an unmodified Rust analyzer report and return its exact-byte digest."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ReportValidationError(f"cannot read overlap report {path}: {exc}") from exc
    try:
        report = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReportValidationError(
            f"overlap report {path} is not valid JSON: {exc}"
        ) from exc
    _validate_report(report)
    return report, sha256_bytes(raw)


def read_adversarial_controls(path: Path) -> tuple[dict[str, Any], ...]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReportValidationError(
            f"cannot read adversarial controls {path}: {exc}"
        ) from exc
    try:
        value = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ReportValidationError(
            f"adversarial controls {path} are not valid YAML: {exc}"
        ) from exc
    if not isinstance(value, dict) or set(value) != {"schema_version", "controls"}:
        raise ReportValidationError(
            "adversarial controls must contain only schema_version and controls"
        )
    if value["schema_version"] != "adversarial-controls-v1":
        raise ReportValidationError(
            "adversarial controls schema_version must be adversarial-controls-v1"
        )
    controls = value["controls"]
    if not isinstance(controls, list) or len(controls) != 40:
        raise ReportValidationError("adversarial controls must list exactly 40 controls")
    for index, control in enumerate(controls):
        _validate_adversarial_control(control, index)
    encoded = [canonical_json_bytes(control) for control in controls]
    if len(set(encoded)) != len(encoded):
        raise ReportValidationError("adversarial controls contain duplicate selectors")
    return tuple(controls)


def findings_for_adversarial_controls(
    findings: list[dict[str, Any]], controls: tuple[dict[str, Any], ...]
) -> tuple[dict[str, Any], ...]:
    selected: list[dict[str, Any]] = []
    for index, control in enumerate(controls):
        matches = [
            finding
            for finding in findings
            if _matches_adversarial_control(finding, control)
        ]
        if len(matches) != 1:
            raise ReportValidationError(
                f"adversarial control {index} matched {len(matches)} overlap report findings"
            )
        selected.append(matches[0])
    if len({finding["id"] for finding in selected}) != len(selected):
        raise ReportValidationError(
            "adversarial controls resolve to duplicate overlap report findings"
        )
    return tuple(selected)


def report_block_threshold(report: dict[str, Any]) -> float:
    reviewed = report.get("reviewed_calibration")
    if not isinstance(reviewed, dict):
        raise ReportValidationError(
            "overlap report lacks reviewed_calibration block-threshold evidence"
        )
    thresholds = reviewed.get("thresholds")
    if not isinstance(thresholds, dict):
        raise ReportValidationError(
            "overlap report lacks reviewed_calibration.thresholds"
        )
    block = thresholds.get("block")
    review = thresholds.get("review")
    if not _finite_score(block) or not _finite_score(review) or review > block:
        raise ReportValidationError(
            "overlap report has impossible reviewed calibration thresholds"
        )
    return float(block)


def report_review_threshold(report: dict[str, Any]) -> float:
    reviewed = report["reviewed_calibration"]
    return float(reviewed["thresholds"]["review"])


def pair_from_finding(finding: dict[str, Any], selection: str) -> PairEvidenceV1:
    graph = finding["graph"]
    cosine = finding["cosine"]
    return PairEvidenceV1(
        pair_id=finding["id"],
        left=dict(finding["left"]),
        right=dict(finding["right"]),
        lane=finding["lane"],
        detector=finding["detector"],
        kind=finding["kind"],
        graph=dict(graph),
        cosine=cosine,
        duplicate_tokens_estimate=finding["duplicate_tokens_estimate"],
        disposition=finding["disposition"],
        selection=selection,
        score_decile=_score_decile(cosine),
        graph_class=_graph_class(graph),
        skill_family=_skill_family(
            finding["left"]["path"], finding["right"]["path"]
        ),
    )


def _validate_report(report: Any) -> None:
    if not isinstance(report, dict):
        raise ReportValidationError("overlap report root must be an object")
    unknown = set(report) - _REPORT_KEYS
    if unknown:
        raise ReportValidationError(
            f"overlap report has unknown fields: {', '.join(sorted(unknown))}"
        )
    required = {"format", "detector", "mode", "findings", "frontmatter", "trends"}
    missing = required - set(report)
    if missing:
        raise ReportValidationError(
            f"overlap report is missing fields: {', '.join(sorted(missing))}"
        )
    if (
        not _unsigned_int(report["format"])
        or report["format"] != 1
        or report["mode"] not in {"calibrate", "report", "check"}
    ):
        raise ReportValidationError("overlap report format or mode is invalid")
    _validate_object_strings(report["detector"], _DETECTOR_KEYS, "detector")
    if not isinstance(report["findings"], list):
        raise ReportValidationError("overlap report findings must be a list")
    _validate_auxiliary_report_evidence(report)
    ids: set[str] = set()
    for index, finding in enumerate(report["findings"]):
        _validate_finding(finding, index)
        pair_id = finding["id"]
        if pair_id in ids:
            raise ReportValidationError(
                f"overlap report repeats finding id {pair_id!r}"
            )
        ids.add(pair_id)


def _validate_auxiliary_report_evidence(report: dict[str, Any]) -> None:
    _validate_frontmatter(report["frontmatter"])
    trends = report["trends"]
    if not isinstance(trends, dict) or set(trends) != {"groups"}:
        raise ReportValidationError(
            "overlap report trends does not match the analyzer schema"
        )
    _validate_trend_groups(trends["groups"])
    if "duplicate_components" in report:
        _validate_duplicate_components(report["duplicate_components"])
    if "calibration" in report and report["calibration"] is not None:
        calibration = report["calibration"]
        if not isinstance(calibration, dict) or set(calibration) != {
            "score_distribution",
            "samples",
        }:
            raise ReportValidationError(
                "overlap report calibration does not match the analyzer schema"
            )
        _validate_score_distribution(calibration["score_distribution"])
        _validate_samples(calibration["samples"])
    if "reviewed_calibration" in report and report["reviewed_calibration"] is not None:
        reviewed = report["reviewed_calibration"]
        if not isinstance(reviewed, dict) or set(reviewed) != {"digest", "thresholds"}:
            raise ReportValidationError(
                "overlap report reviewed_calibration does not match the analyzer schema"
            )
        if not isinstance(reviewed["digest"], str) or not reviewed["digest"]:
            raise ReportValidationError(
                "overlap report reviewed_calibration.digest must be a non-empty string"
            )
        _validate_thresholds(reviewed["thresholds"])


def _validate_thresholds(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {"review", "block"}:
        raise ReportValidationError(
            "overlap report reviewed calibration thresholds are malformed"
        )
    if not _finite_score(value["review"]) or not _finite_score(value["block"]):
        raise ReportValidationError(
            "overlap report reviewed calibration thresholds must be finite"
        )


def _validate_frontmatter(value: Any) -> None:
    keys = {"left", "right", "field", "left_value", "right_value", "score"}
    _validate_records(value, keys, "frontmatter")
    for item in value:
        if any(not isinstance(item[key], str) for key in keys - {"score"}) or not _finite_score(
            item["score"]
        ):
            raise ReportValidationError(
                "overlap report frontmatter has invalid field types"
            )


def _validate_trend_groups(value: Any) -> None:
    string_keys = {"lane", "graph_class", "disposition"}
    keys = string_keys | {
        "current_findings",
        "baseline_findings",
        "current_estimated_duplicate_tokens",
        "baseline_estimated_duplicate_tokens",
    }
    _validate_records(value, keys, "trends.groups")
    for item in value:
        if any(not isinstance(item[key], str) for key in string_keys) or any(
            not _unsigned_int(item[key]) for key in keys - string_keys
        ):
            raise ReportValidationError(
                "overlap report trends.groups has invalid field types"
            )


def _validate_duplicate_components(value: Any) -> None:
    keys = {"id", "endpoints", "finding_ids", "redundant_tokens_estimate"}
    _validate_records(value, keys, "duplicate_components")
    for item in value:
        if (
            not isinstance(item["id"], str)
            or not isinstance(item["endpoints"], list)
            or any(not isinstance(endpoint, str) for endpoint in item["endpoints"])
            or not isinstance(item["finding_ids"], list)
            or any(not isinstance(finding_id, str) for finding_id in item["finding_ids"])
            or not _unsigned_int(item["redundant_tokens_estimate"])
        ):
            raise ReportValidationError(
                "overlap report duplicate_components has invalid field types"
            )


def _validate_score_distribution(value: Any) -> None:
    keys = {"min_score", "max_score", "count"}
    _validate_records(value, keys, "calibration.score_distribution")
    for item in value:
        if (
            not _finite_score(item["min_score"])
            or not _finite_score(item["max_score"])
            or not _unsigned_int(item["count"])
        ):
            raise ReportValidationError(
                "overlap report calibration.score_distribution has invalid field types"
            )


def _validate_samples(value: Any) -> None:
    keys = {"left", "right", "score", "label"}
    _validate_records(value, keys, "calibration.samples")
    for item in value:
        if any(
            not isinstance(item[key], str) for key in {"left", "right", "label"}
        ) or not _finite_score(item["score"]):
            raise ReportValidationError(
                "overlap report calibration.samples has invalid field types"
            )


def _validate_records(value: Any, keys: set[str], where: str) -> None:
    if not isinstance(value, list) or any(
        not isinstance(item, dict) or set(item) != keys for item in value
    ):
        raise ReportValidationError(
            f"overlap report {where} does not match the analyzer schema"
        )


def _validate_adversarial_control(value: Any, index: int) -> None:
    where = f"adversarial controls[{index}]"
    if not isinstance(value, dict) or set(value) != _CONTROL_KEYS:
        raise ReportValidationError(
            f"{where} must contain category, evidence, and predicates"
        )
    if value["category"] not in _CONTROL_CATEGORIES:
        raise ReportValidationError(f"{where}.category is unsupported")
    evidence = value["evidence"]
    if not isinstance(evidence, dict) or set(evidence) != _CONTROL_EVIDENCE_KEYS:
        raise ReportValidationError(
            f"{where}.evidence must identify left and right endpoints"
        )
    for side in ("left", "right"):
        endpoint = evidence[side]
        if not isinstance(endpoint, dict) or set(endpoint) != _CONTROL_ENDPOINT_KEYS:
            raise ReportValidationError(
                f"{where}.evidence.{side} does not match endpoint identity evidence"
            )
        _validate_control_endpoint(endpoint, f"{where}.evidence.{side}")
    predicates = value["predicates"]
    if (
        not isinstance(predicates, dict)
        or set(predicates) - _CONTROL_PREDICATE_KEYS
        or any(not isinstance(item, str) or not item for item in predicates.values())
    ):
        raise ReportValidationError(
            f"{where}.predicates must contain supported non-empty string values"
        )


def _validate_control_endpoint(endpoint: dict[str, Any], where: str) -> None:
    span = endpoint["span"]
    if (
        not isinstance(endpoint["path"], str)
        or not endpoint["path"]
        or not isinstance(endpoint["heading_path"], list)
        or any(
            not isinstance(heading, str) or not heading
            for heading in endpoint["heading_path"]
        )
        or not _unsigned_int(endpoint["part"])
        or not isinstance(endpoint["source_hash"], str)
        or not endpoint["source_hash"]
        or not isinstance(span, dict)
        or set(span) != {"start", "end"}
        or any(
            not _unsigned_int(span[key]) or span[key] < 1
            for key in ("start", "end")
        )
        or span["start"] > span["end"]
    ):
        raise ReportValidationError(f"{where} is invalid")


def _matches_adversarial_control(
    finding: dict[str, Any], control: dict[str, Any]
) -> bool:
    for side in ("left", "right"):
        expected = control["evidence"][side]
        if any(finding[side][key] != value for key, value in expected.items()):
            return False
    return all(
        finding[key] == value for key, value in control["predicates"].items()
    )


def _validate_finding(finding: Any, index: int) -> None:
    where = f"findings[{index}]"
    if not isinstance(finding, dict) or set(finding) != _FINDING_KEYS:
        raise ReportValidationError(
            f"{where} does not match the analyzer finding schema"
        )
    for key in ("id", "lane", "detector", "kind", "disposition"):
        if not isinstance(finding[key], str) or not finding[key]:
            raise ReportValidationError(f"{where}.{key} must be a non-empty string")
    if finding["kind"] not in {"exact", "semantic"}:
        raise ReportValidationError(f"{where}.kind must be exact or semantic")
    if not _unsigned_int(finding["duplicate_tokens_estimate"]):
        raise ReportValidationError(
            f"{where}.duplicate_tokens_estimate must be non-negative"
        )
    cosine = finding["cosine"]
    if finding["kind"] == "exact" and cosine is not None:
        raise ReportValidationError(f"{where}.exact findings must have null cosine")
    if finding["kind"] == "semantic" and (
        not _finite_score(cosine) or not -1.0 <= cosine <= 1.0
    ):
        raise ReportValidationError(
            f"{where}.semantic cosine must be finite and within [-1, 1]"
        )
    for side in ("left", "right"):
        _endpoint(finding[side], f"{where}.{side}")
    graph = finding["graph"]
    if not isinstance(graph, dict) or set(graph) != _GRAPH_KEYS:
        raise ReportValidationError(
            f"{where}.graph does not match the analyzer graph schema"
        )
    for key in ("directly_linked", "same_component", "same_skill", "disconnected"):
        if not isinstance(graph[key], bool):
            raise ReportValidationError(f"{where}.graph.{key} must be boolean")
    for key in ("directed_distance", "undirected_distance"):
        if graph[key] is not None and not _unsigned_int(graph[key]):
            raise ReportValidationError(
                f"{where}.graph.{key} must be null or non-negative integer"
            )


def _endpoint(value: Any, where: str) -> None:
    if not isinstance(value, dict) or set(value) != _ENDPOINT_KEYS:
        raise ReportValidationError(
            f"{where} does not match the analyzer endpoint schema"
        )
    path = value["path"]
    headings = value["heading_path"]
    source_hash = value["source_hash"]
    excerpt = value["original_excerpt"]
    if (
        not isinstance(path, str)
        or not path
        or path.startswith("/")
        or ".." in Path(path).parts
    ):
        raise ReportValidationError(f"{where}.path must be a repository-relative path")
    if not isinstance(headings, list) or any(
        not isinstance(item, str) or not item for item in headings
    ):
        raise ReportValidationError(
            f"{where}.heading_path must be a list of non-empty strings"
        )
    if (
        not isinstance(source_hash, str)
        or not source_hash
        or not isinstance(excerpt, str)
    ):
        raise ReportValidationError(f"{where} source evidence is malformed")
    for key in ("part", "token_count"):
        if not _unsigned_int(value[key]):
            raise ReportValidationError(
                f"{where}.{key} must be a non-negative integer"
            )
    span = value["span"]
    if not isinstance(span, dict) or set(span) != {"start", "end"}:
        raise ReportValidationError(f"{where}.span must contain start and end")
    if (
        any(
            not _unsigned_int(span[key]) or span[key] < 1
            for key in ("start", "end")
        )
        or span["start"] > span["end"]
    ):
        raise ReportValidationError(f"{where}.span is impossible")


def _validate_object_strings(value: Any, keys: set[str], where: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ReportValidationError(
            f"overlap report {where} does not match the analyzer schema"
        )
    if any(not isinstance(value[key], str) or not value[key] for key in keys):
        raise ReportValidationError(
            f"overlap report {where} must contain non-empty strings"
        )


def _unsigned_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _finite_score(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _score_decile(score: float | None) -> int | None:
    if score is None:
        return None
    return min(9, max(0, math.floor(score * 10)))


def _graph_class(graph: dict[str, Any]) -> str:
    if graph["directly_linked"]:
        return "directly-linked"
    if graph["same_skill"]:
        return "same-skill"
    if graph["same_component"]:
        return "connected"
    return "disconnected"


def _family(path: str) -> str:
    parts = Path(path).parts
    if len(parts) >= 2 and parts[0] == "skills":
        return "/".join(parts[:2])
    if len(parts) >= 3 and parts[:2] == (".agents", "skills"):
        return "/".join(parts[:3])
    return parts[0]


def _skill_family(left_path: str, right_path: str) -> str:
    return "|".join(sorted((_family(left_path), _family(right_path))))
