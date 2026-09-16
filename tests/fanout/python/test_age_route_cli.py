"""Focused tests for the contextual age-route JSON command."""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src" / "fanout"))

from easy_cheese.shared.fanout import age_route, age_route_cli  # noqa: E402


def _context() -> dict[str, object]:
    paths = ["src/feature.py", "tests/test_feature.py"]
    return {
        "scope": "diff",
        "effort": "normal",
        "snapshot": "0123456789abcdef",
        "changed_paths": paths,
        "surface_score": 20,
        "components": [
            {"id": "feature", "role": "application", "paths": [paths[0]]},
            {"id": "feature-tests", "role": "test", "paths": [paths[1]]},
        ],
        "subjects": [
            {
                "subject": subject,
                "applicability": "yes",
                "targets": paths,
                "evidence": [f"{subject} applies"],
            }
            for subject in age_route.SUBJECTS
        ],
        "risks": [],
        "is_subagent": False,
        "can_fan_out": True,
        "concurrency_limit": None,
    }


def _run(
    payload: Mapping[str, object], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    original_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        exit_code = age_route_cli.main([])
    finally:
        sys.stdin = original_stdin
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


def test_context_payload_matches_direct_plan(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = {"context": _context()}
    exit_code, out, err = _run(payload, capsys)
    assert exit_code == 0
    assert err == ""
    assert json.loads(out) == age_route.route(context=payload["context"])


def test_affinage_options_are_forwarded(capsys: pytest.CaptureFixture[str]) -> None:
    payload = {
        "context": _context(),
        "entry": "affinage",
        "comments": 10,
        "ci_class": "passing",
    }
    exit_code, out, err = _run(payload, capsys)
    assert exit_code == 0
    assert err == ""
    assert json.loads(out) == age_route.route(
        context=cast(dict[str, object], payload["context"]),
        entry="affinage",
        comments=10,
        ci_class="passing",
    )


def test_score_only_payload_is_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code, out, err = _run({"surface_score": 20}, capsys)
    assert exit_code != 0
    assert out == ""
    assert "ERROR" in err


def test_missing_manifest_path_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = age_route_cli.main([str(REPO_ROOT / "does-not-exist.json")])
    assert exit_code == 2
    assert "ERROR" in capsys.readouterr().err
