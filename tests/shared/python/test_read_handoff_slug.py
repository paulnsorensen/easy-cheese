"""Tests for shared/scripts/read_handoff_slug.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "shared" / "scripts" / "read_handoff_slug.py"


def _write_artifact(tmp_path: Path, phase: str, slug: str, body: str) -> Path:
    artifact = tmp_path / ".cheese" / phase / f"{slug}.md"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(body)
    return artifact


def _run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )


def test_happy_path_parse(tmp_path: Path) -> None:
    body = (
        "status: ok\n"
        "next: cure\n"
        "artifact: .cheese/age/foo.md\n"
        "high-stake encapsulation leak in cli.py\n"
    )
    _write_artifact(tmp_path, "age", "foo", body)

    result = _run(tmp_path, "--phase", "age", "--slug", "foo")
    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    assert set(payload.keys()) == {"status", "next", "artifact", "orientation", "halt_reason"}
    assert payload == {
        "status": "ok",
        "next": "cure",
        "artifact": ".cheese/age/foo.md",
        "orientation": "high-stake encapsulation leak in cli.py",
        "halt_reason": None,
    }


def test_halt_status_extracts_reason(tmp_path: Path) -> None:
    body = (
        "status: halt: seed bootstrap failed\n"
        "next: done\n"
        "artifact:\n"
        "no usable seed found\n"
    )
    _write_artifact(tmp_path, "cook", "bar", body)

    result = _run(tmp_path, "--phase", "cook", "--slug", "bar")
    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    assert payload["status"] == "halt"
    assert payload["halt_reason"] == "seed bootstrap failed"
    assert payload["artifact"] is None
    assert payload["next"] == "done"
    assert payload["orientation"] == "no usable seed found"


def test_missing_file_raises_cli_error(tmp_path: Path) -> None:
    result = _run(tmp_path, "--phase", "age", "--slug", "ghost")
    assert result.returncode == 2
    assert result.stderr.startswith("ERROR:")
    assert "artifact not found" in result.stderr
    assert "ghost" in result.stderr


def test_missing_required_arg_exits_2(tmp_path: Path) -> None:
    # Omit --slug; argparse should error and exit 2.
    result = _run(tmp_path, "--phase", "age")
    assert result.returncode == 2
    # argparse writes usage to stderr; sanity-check it complained about --slug.
    assert "--slug" in result.stderr
