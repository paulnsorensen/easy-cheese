"""Contract tests for automatic skill-overlap workflow mode selection."""

import os
from pathlib import Path
import subprocess
import textwrap


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "skill-overlap.yml"


def _selector_script(requested: str = "", event_name: str = "pull_request") -> str:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    selector = workflow.split("- name: Select advisory or requested mode", 1)[1].split(
        "- name: Run model-free analyzer tests", 1
    )[0]
    script = textwrap.dedent(selector.split("run: |", 1)[1])
    return script.replace("${{ inputs.mode || '' }}", requested).replace(
        "${{ github.event_name }}", event_name
    )


def test_automatic_mode_selection_distinguishes_drafts_from_invalid_reviews(
    tmp_path: Path,
) -> None:
    metadata = tmp_path / ".github"
    metadata.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    cargo = bin_dir / "cargo"
    cargo.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$*" == *"calibration validate"* ]]; then '\
        'exit "$CALIBRATION_RESULT"; fi\n'
        'if [[ "$*" == *"baseline validate"* ]]; then '\
        'exit "$BASELINE_RESULT"; fi\n'
        "exit 99\n",
        encoding="utf-8",
    )
    cargo.chmod(0o755)

    cases = [
        ("draft", "draft", 1, 1, 0, "calibrate"),
        ("reviewed", "draft", 0, 1, 0, "report"),
        ("reviewed", "reviewed", 0, 0, 0, "check"),
        ("reviewed", "draft", 1, 1, 1, None),
        ("reviewed", "reviewed", 0, 1, 1, None),
    ]
    for calibration_status, baseline_status, calibration_result, baseline_result, expected_code, expected_mode in cases:
        (metadata / "skill-overlap-calibration.yml").write_text(
            f"status: {calibration_status}\n", encoding="utf-8"
        )
        (metadata / "skill-overlap-baseline.yml").write_text(
            f"status: {baseline_status}\n", encoding="utf-8"
        )
        output = tmp_path / "output"
        output.unlink(missing_ok=True)
        env = os.environ | {
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "GITHUB_OUTPUT": str(output),
            "CALIBRATION_RESULT": str(calibration_result),
            "BASELINE_RESULT": str(baseline_result),
        }

        result = subprocess.run(
            ["bash", "-c", _selector_script()],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == expected_code, result.stderr
        if expected_mode is None:
            assert not output.exists()
        else:
            assert output.read_text(encoding="utf-8") == f"value={expected_mode}\n"


def test_job_summary_is_concise_and_points_to_full_artifact() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    summary = workflow.split("- name: Job summary", 1)[1].split(
        "- uses: actions/upload-artifact", 1
    )[0]

    assert "cat report.md" not in summary
    assert "Report findings" in summary
    assert "Trend groups" in summary
    assert "skill-overlap-report" in summary
