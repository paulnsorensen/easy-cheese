"""Contract regression binding /cure's documented render-brief CLI to the real surface.

Guards finding 18 from the r667 megamerge age review round: the § Coder
brief invocation was unverified prose, so a subcommand rename could ship
green while `/cure` step 2 fails at runtime.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CURE = REPO_ROOT / "skills" / "cure"
SELECTION = CURE / "references" / "selection.md"

DRIVER = (
    "import sys\n"
    "from easy_cheese.skills.cure.commands import main\n"
    "sys.exit(main(sys.argv[1:]))\n"
)

SAMPLE_REVIEW_RESULT: dict[str, object] = {
    "contract_version": {
        "schema_uri": "https://schemas.easy-cheese.dev/review-result",
        "major": "1",
        "minor": "0",
    },
    "review_id": "prose-contract",
    "disposition": "findings",
    "findings": [
        {
            "finding_id": "prose/finding/1",
            "severity": "critical",
            "summary": "`index` re-exports `SqlPgUser` across slice boundary.",
            "recommendation": "define `User` in the slice's public types, map at the boundary.",
            "evidence": [
                {
                    "evidence_id": "prose/evidence/1",
                    "kind": "review",
                    "artifact": {
                        "artifact_id": "prose/artifact/1",
                        "role": "review",
                        "uri": "repo://prose/evidence/1.json",
                        "digest": "sha256:" + "0" * 64,
                        "size_bytes": 64,
                        "media_type": "application/json",
                    },
                }
            ],
            "location": {
                "artifact_id": "prose/artifact/1",
                "path": "src/users/index.ts",
                "start_line": 42,
                "end_line": 42,
            },
        }
    ],
    "coverage": [{"target": "encapsulation", "disposition": "covered"}],
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _coder_brief_command() -> str:
    text = _read(SELECTION)
    fence = text.split("## Coder brief", 1)[1].split("```text\n", 1)[1].split("\n```", 1)[0]
    lines = [line for line in fence.splitlines() if line.strip()]
    assert len(lines) == 1, "expected exactly one command line in the fenced Coder brief block"
    return lines[0].strip()


def test_documented_render_brief_command_matches_the_findings_cli() -> None:
    command = _coder_brief_command()
    assert command == (
        'python3 skills/cure/scripts/cure.pyz findings render-brief --report <path> --selection "<ids>"'
    )


def test_documented_render_brief_invocation_runs_against_the_real_cli(tmp_path: Path) -> None:
    command = _coder_brief_command()
    tokens = command.split()
    assert tokens[:3] == ["python3", "skills/cure/scripts/cure.pyz", "findings"]
    subcommand = tokens[3]
    report_path = tmp_path / "review-result.json"
    _ = report_path.write_text(json.dumps(SAMPLE_REVIEW_RESULT), encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-c", DRIVER, "findings", subcommand, "--report", str(report_path), "--selection", "1"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "recommendation (locked): define `User`" in result.stdout
