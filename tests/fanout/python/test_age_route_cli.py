"""Tests for src/fanout/age_route_cli.py -- the CLI wrapper around
age_route.route().

Spec: deterministic-fanout-sizing.md curd `wire-up`. The payload is a
single `score` (plus optional risk_flags/entry/comments/ci_class), passed
straight through to route(**payload); a payload still shaped around the old
files_changed/insertions/deletions params must fail loud since route() no
longer accepts those keywords.
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src" / "fanout"))

from easy_cheese.shared.fanout import age_route, age_route_cli  # noqa: E402


def _run(payload: dict, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    # contextlib has no redirect_stdin; swap sys.stdin directly and restore.
    buf = io.StringIO()
    original_stdin = sys.stdin
    sys.stdin = io.StringIO(json.dumps(payload))
    try:
        with redirect_stdout(buf):
            exit_code = age_route_cli.main([])
    finally:
        sys.stdin = original_stdin
    return exit_code, buf.getvalue(), capsys.readouterr().err


class TestScorePayload:
    def test_score_payload_matches_direct_call(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code, out, _ = _run({"score": 30}, capsys)
        assert exit_code == 0
        assert json.loads(out) == age_route.route(score=30)

    def test_score_with_risk_flags_matches_direct_call(self, capsys: pytest.CaptureFixture[str]) -> None:
        payload = {"score": 20, "risk_flags": ["auth"]}
        exit_code, out, _ = _run(payload, capsys)
        assert exit_code == 0
        assert json.loads(out) == age_route.route(score=20, risk_flags=["auth"])


class TestLegacyPayloadRejected:
    def test_files_changed_payload_exits_nonzero(self, capsys: pytest.CaptureFixture[str]) -> None:
        payload = {"files_changed": 5, "insertions": 10, "deletions": 2}
        exit_code, out, err = _run(payload, capsys)
        assert exit_code != 0
        assert out == ""
        assert "ERROR" in err


class TestManifestErrors:
    def test_missing_manifest_path_exits_2(self, capsys: pytest.CaptureFixture[str]) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = age_route_cli.main(
                [str(REPO_ROOT / "does-not-exist.json")]
            )
        assert exit_code == 2
        assert "ERROR" in capsys.readouterr().err
