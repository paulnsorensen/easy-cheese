"""Opt-in browser regression for the outer Cook acceptance interface."""

from __future__ import annotations

import functools
import hashlib
import http.server
import json
import os
import subprocess
import shutil
import sys
import threading
from pathlib import Path
from typing import cast, override
from urllib.parse import unquote, urlparse

from easy_cheese.skills.cook.preparation import SetupEvidence, prepare, resubmit
from easy_cheese.shared.mold_cook_handoff import (
    bind_mold_cook_approval,
    canonical_mold_cook_proposal,
    materialize_artifact_ref,
)
from easy_cheese_schemas import CurdPlan, canonical_bytes
from easy_cheese_schemas.mold_cook import (
    MOLD_COOK_APPROVAL_SCHEMA_URI,
    CookPreparationOutcome,
    CookSetupAuthorization,
    MoldCookApprovalDecision,
    MoldCookApprovalKind,
    MoldCookApprovalSource,
)

from tests.python.test_mold_cook_producer import (
    finalize_fixture,
    make_approval,
    make_planner_result,
    make_spec,
)


ROOT = Path(__file__).resolve().parents[2]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    @override
    def log_message(self, format: str, *_args: object) -> None:
        _ = format
        return


def test_outer_preparation_and_browser_interaction(tmp_path: Path) -> None:
    """Drive Cook from RED to a produced feature, then observe it in Chromium."""
    repository = tmp_path / "repository"
    _ = repository.mkdir()
    spec = make_spec(repository)
    cook_pyz = ROOT / "skills" / "cook" / "scripts" / "cook.pyz"
    if not cook_pyz.is_file():
        raise AssertionError(f"generated Cook bundle is missing: {cook_pyz}")

    environment = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", str(Path.home())),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    red = subprocess.run(
        [
            sys.executable,
            str(cook_pyz),
            "prepare",
            "--spec",
            str(spec),
            "--mode",
            "full",
            "--repository-root",
            str(repository),
            "--artifact-root",
            str(repository / "artifacts"),
        ],
        cwd=str(cook_pyz.parent),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert red.returncode == 0, red.stderr
    red_result = cast(dict[str, object], json.loads(red.stdout))
    assert red_result["outcome"] == "needs-approval"
    assert red_result["approval_kind"] == "scope"
    assert not (repository / "index.html").exists()

    planner = make_planner_result()
    plan = cast(CurdPlan, planner.plan)
    plan_approval = make_approval(repository, spec, plan=planner)
    finalized = finalize_fixture(
        tmp_path=repository,
        spec_path=spec,
        approval=plan_approval,
        planner=planner,
    )
    assert finalized.status == "ready"
    artifact_root = repository / "artifacts"
    pointer = artifact_root / "pointers" / "operation-1.json"

    outer = Path(__file__).resolve().parents[1] / "fixtures" / "mold_cook_browser"
    browser_fixture = repository / "tests" / "browser"
    setup_command = (
        "corepack pnpm install --frozen-lockfile && "
        + "corepack pnpm exec playwright install --with-deps chromium"
    )
    authorization = CookSetupAuthorization(
        prerequisite_curd_id="curd-1",
        allowed_paths=("tests/browser/",),
        allowed_commands=(setup_command,),
    )
    _ = shutil.copytree(
        outer,
        browser_fixture,
        ignore=shutil.ignore_patterns("node_modules", "test-results"),
    )
    runner_response = b"Approve the test-local browser runner."
    runner_response_path = artifact_root / "runner-response.txt"
    _ = runner_response_path.write_bytes(runner_response)
    runner_response_ref = materialize_artifact_ref(
        runner_response,
        artifact_id="browser-runner-response",
        role="response",
        uri=runner_response_path.as_uri(),
        media_type="text/plain",
    )
    runner_proposal = canonical_mold_cook_proposal(
        request_id="request-1",
        kind=MoldCookApprovalKind.RUNNER,
        spec_digest=plan_approval.spec_digest,
        coverage=plan_approval.coverage,
        setup_authorization=authorization,
    )
    runner_proposal_path = artifact_root / "runner-proposal.json"
    _ = runner_proposal_path.write_bytes(runner_proposal)
    runner_proposal_ref = materialize_artifact_ref(
        runner_proposal,
        artifact_id="browser-runner-proposal",
        role="proposal",
        uri=runner_proposal_path.as_uri(),
        media_type="application/json",
    )
    runner_approval = bind_mold_cook_approval(
        request_id="request-1",
        kind=MoldCookApprovalKind.RUNNER,
        decision=MoldCookApprovalDecision.APPROVED,
        source=MoldCookApprovalSource.USER_RESPONSE,
        spec_digest=plan_approval.spec_digest,
        proposal_ref=runner_proposal_ref,
        response_ref=runner_response_ref,
        response_text=runner_response.decode(),
        response_source="runner-response.txt",
        coverage=plan_approval.coverage,
        setup_authorization=authorization,
    )
    runner_approval_content = canonical_bytes(runner_approval)
    runner_approval_path = artifact_root / "runner-approval.json"
    _ = runner_approval_path.write_bytes(runner_approval_content)
    runner_approval_ref = materialize_artifact_ref(
        runner_approval_content,
        artifact_id="browser-runner-approval",
        role="runner_approval",
        uri=runner_approval_path.as_uri(),
        media_type="application/json",
        schema_uri=MOLD_COOK_APPROVAL_SCHEMA_URI,
    )
    waiting = prepare(
        pointer,
        repository_root=repository,
        artifact_root=artifact_root,
        runner_approval=runner_approval_ref,
        setup_authorization=authorization,
    )
    assert waiting.outcome is CookPreparationOutcome.NEEDS_PREPARATION
    setup = subprocess.run(
        ["bash", "-lc", setup_command],
        cwd=str(browser_fixture),
        env=environment,
        capture_output=True,
        check=False,
    )
    assert setup.returncode == 0, (setup.stdout + setup.stderr).decode(errors="replace")
    setup_output = setup.stdout + setup.stderr
    setup_output_digest = f"sha256:{hashlib.sha256(setup_output).hexdigest()}"
    _ = (
        artifact_root / f"sha256-{setup_output_digest.removeprefix('sha256:')}"
    ).write_bytes(setup_output)
    setup_evidence = SetupEvidence(
        prerequisite_curd_id="curd-1",
        plan_digest=f"sha256:{hashlib.sha256(canonical_bytes(plan)).hexdigest()}",
        authorization_digest=(
            f"sha256:{hashlib.sha256(canonical_bytes(authorization)).hexdigest()}"
        ),
        runner_command=setup_command,
        fixture_path="tests/browser/package.json",
        environment_id="mold-cook-browser-test",
        exit_code=setup.returncode,
        captured_output_digest=setup_output_digest,
    )
    setup_evidence_content = canonical_bytes(setup_evidence)
    setup_evidence_path = artifact_root / "setup-evidence.json"
    _ = setup_evidence_path.write_bytes(setup_evidence_content)
    setup_evidence_ref = materialize_artifact_ref(
        setup_evidence_content,
        artifact_id="browser-setup-evidence",
        role="setup_evidence",
        uri=setup_evidence_path.as_uri(),
        media_type="application/json",
        schema_uri="https://schemas.easy-cheese.dev/setup-evidence",
    )
    ready = resubmit(
        waiting,
        runner_approval=runner_approval_ref,
        setup_authorization=authorization,
        setup_evidence=setup_evidence_ref,
    )
    assert ready.outcome is CookPreparationOutcome.READY
    assert ready.handoff_ref is not None
    ready_pointer = Path(unquote(urlparse(ready.handoff_ref.uri).path))
    production_env = {
        **environment,
        "PYTHONPATH": str(ROOT / "src"),
    }
    produced = subprocess.run(
        [
            sys.executable,
            str(outer / "outer_workflow.py"),
            str(ready_pointer),
            str(repository),
            str(repository / "artifacts"),
        ],
        cwd=str(repository),
        env=production_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert produced.returncode == 0, produced.stderr
    production_result = cast(dict[str, object], json.loads(produced.stdout))
    assert production_result == {"feature": "index.html", "results": 1}
    document = repository / "index.html"
    assert document.is_file()
    assert "Feature executed" in document.read_text(encoding="utf-8")

    handler = functools.partial(_QuietHandler, directory=str(repository))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        browser_env = {
            **environment,
            "MOLD_COOK_BROWSER_URL": f"http://127.0.0.1:{server.server_port}/index.html",
            "PLAYWRIGHT_OUTPUT_DIR": str(tmp_path / "playwright-results"),
        }
        fixture = browser_fixture
        result = subprocess.run(
            [
                "corepack",
                "pnpm",
                "exec",
                "playwright",
                "test",
                "--config=playwright.config.mjs",
            ],
            cwd=str(fixture),
            env=browser_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
