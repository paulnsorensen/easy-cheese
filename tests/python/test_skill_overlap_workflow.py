"""Contract tests for automatic skill-overlap workflow mode selection."""

import json
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
    _ = cargo.write_text(
        "#!/usr/bin/env bash\n"
        + 'if [[ "$*" == *"calibration validate"* ]]; then '
        + 'exit "$CALIBRATION_RESULT"; fi\n'
        + 'if [[ "$*" == *"baseline validate"* ]]; then '
        + 'exit "$BASELINE_RESULT"; fi\n'
        + "exit 99\n",
        encoding="utf-8",
    )
    cargo.chmod(0o755)

    cases = [
        # (calibration_status, baseline_status, calibration_result, baseline_result,
        #  event_name, expected_code, expected_mode, expected_stderr_substring)
        ("draft", "draft", 1, 1, "pull_request", 0, "calibrate", None),
        (
            "draft",
            "reviewed",
            1,
            1,
            "pull_request",
            1,
            None,
            "baseline must remain draft until calibration is reviewed",
        ),
        ("reviewed", "draft", 0, 1, "pull_request", 0, "report", None),
        ("reviewed", "reviewed", 0, 0, "pull_request", 0, "check", None),
        ("reviewed", "reviewed", 0, 0, "schedule", 0, "report", None),
        (
            "reviewed",
            "draft",
            1,
            1,
            "pull_request",
            1,
            None,
            "reviewed calibration failed validation",
        ),
        (
            "reviewed",
            "reviewed",
            0,
            1,
            "pull_request",
            1,
            None,
            "reviewed baseline failed validation",
        ),
        (
            "reviewed",
            "bogus",
            0,
            0,
            "pull_request",
            1,
            None,
            "baseline status must be draft or reviewed",
        ),
        (
            "bogus",
            "draft",
            1,
            1,
            "pull_request",
            1,
            None,
            "calibration status must be draft or reviewed",
        ),
    ]
    for (
        calibration_status,
        baseline_status,
        calibration_result,
        baseline_result,
        event_name,
        expected_code,
        expected_mode,
        expected_stderr,
    ) in cases:
        _ = (metadata / "skill-overlap-calibration.yml").write_text(
            f"status: {calibration_status}\n", encoding="utf-8"
        )
        _ = (metadata / "skill-overlap-baseline.yml").write_text(
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
            ["bash", "-c", _selector_script(event_name=event_name)],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == expected_code, result.stderr
        if expected_stderr is not None:
            assert expected_stderr in result.stderr, result.stderr
        if expected_mode is None:
            assert not output.exists()
        else:
            assert output.read_text(encoding="utf-8") == f"value={expected_mode}\n"


def test_job_summary_is_concise_and_points_to_full_artifact(tmp_path: Path) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    summary = workflow.split("- name: Job summary", 1)[1].split(
        "- name: Save cargo + model cache", 1
    )[0]
    script = textwrap.dedent(summary.split("run: |", 1)[1]).replace(
        "${{ steps.mode.outputs.value }}", "check"
    ).replace("${{ steps.analyze.outcome }}", "success")

    _ = (tmp_path / "report.json").write_text(
        json.dumps({"findings": [1, 2, 3], "trends": {"groups": ["a", "b"]}}),
        encoding="utf-8",
    )
    summary_file = tmp_path / "summary.md"

    result = subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        env=os.environ | {"GITHUB_STEP_SUMMARY": str(summary_file)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    output = summary_file.read_text(encoding="utf-8")
    assert "cat report.md" not in output
    assert "Report findings: 3" in output
    assert "Trend groups: 2" in output
    assert "skill-overlap-report" in output
