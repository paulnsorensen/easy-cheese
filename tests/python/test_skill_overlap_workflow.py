"""Contract tests for automatic skill-overlap workflow mode selection."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "skill-overlap.yml"


def test_pull_requests_check_only_after_calibration_and_baseline_validate() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    selector = workflow.split("- name: Select advisory or requested mode", 1)[1].split(
        "- name: Run model-free analyzer tests", 1
    )[0]

    requested = selector.index('if [[ -n "$requested" ]]')
    pull_request = selector.index('github.event_name }}" == "pull_request"')
    calibration = selector.index("calibration validate", pull_request)
    baseline = selector.index("baseline validate", calibration)
    check = selector.index('echo "value=check"', baseline)
    report = selector.index('echo "value=report"', check)
    calibrate = selector.index('echo "value=calibrate"', report)

    assert requested < pull_request < calibration < baseline < check < report < calibrate


def test_job_summary_is_concise_and_points_to_full_artifact() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    summary = workflow.split("- name: Job summary", 1)[1].split(
        "- uses: actions/upload-artifact", 1
    )[0]

    assert "cat report.md" not in summary
    assert "Report findings" in summary
    assert "Trend groups" in summary
    assert "skill-overlap-report" in summary
