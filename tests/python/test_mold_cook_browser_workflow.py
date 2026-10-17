"""Opt-in browser regression for direct Cook execution."""

from __future__ import annotations

import functools
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import cast, override

import pytest

from easy_cheese.shared.mold_cook_handoff import (
    SETUP_EVIDENCE_SCHEMA_URI,
    SetupEvidence,
    materialize_artifact_ref,
    validate_bound_execution,
    validate_mold_cook_setup_evidence,
    validate_runner_authority,
)
from easy_cheese.skills.mold.producer import finalize_mold
from easy_cheese_schemas import ArtifactRef, CurdPlan, MoldCookCoverage, canonical_bytes
from easy_cheese_schemas.schema_runtime import (
    structure_contract_value,
)
from easy_cheese_schemas.mold_cook import CookSetupAuthorization
from tests.python.test_mold_cook_producer import (
    finalize_fixture,
    make_planner_result,
    make_spec,
)

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(  # noqa: V107
    os.environ.get("MOLD_COOK_BROWSER") != "1",
    reason="opt-in; run via just test-workflow-browser",
)


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    @override
    def log_message(self, format: str, *_args: object) -> None:
        _ = format
        return


def _retain_runner(
    root: Path, content: bytes, *, role: str,
    schema_uri: str | None = None,
) -> ArtifactRef:
    digest = hashlib.sha256(content).hexdigest()
    path = root / f"sha256-{digest}"
    _ = path.write_bytes(content)
    return materialize_artifact_ref(
        content, artifact_id=f"browser-{role}", role=role,
        uri=path.as_uri(), schema_uri=schema_uri,
    )


def test_direct_execution_and_browser_interaction(tmp_path: Path) -> None:
    """Drive Cook from missing planning to a feature, then observe Chromium."""
    repository = tmp_path / "repository"
    _ = repository.mkdir()
    spec = make_spec(repository)

    browser_node_modules = Path(os.environ.get("MOLD_COOK_BROWSER_NODE_MODULES", ""))
    browser_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    if not browser_node_modules.is_dir() or not browser_path:
        raise AssertionError(
            "browser dependencies must be provisioned by just test-workflow-browser"
        )
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp_path / "home"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PLAYWRIGHT_BROWSERS_PATH": browser_path,
    }
    red = finalize_mold(
        spec, artifact_root=repository / "artifacts",
        operation_id="missing-plan", request_id="request-1",
    )
    assert red.status == "saved-not-ready"
    assert "plan_ref" not in red.payload
    assert not (repository / "index.html").exists()

    planner = make_planner_result()
    plan = cast(CurdPlan, planner.plan)
    finalized = finalize_fixture(
        tmp_path=repository, spec_path=spec, planner=planner,
    )
    assert finalized.status == "ready"
    artifact_root = repository / "artifacts"
    payload = finalized.payload
    spec_ref = structure_contract_value(payload["spec_ref"], ArtifactRef, "spec_ref")
    planner_ref = structure_contract_value(payload["planner_result_ref"], ArtifactRef, "planner_result_ref")
    plan_ref = structure_contract_value(payload["plan_ref"], ArtifactRef, "plan_ref")
    coverage = structure_contract_value(payload["coverage"], MoldCookCoverage, "coverage")
    spec_digest = spec_ref.digest

    outer = Path(__file__).resolve().parents[1] / "fixtures" / "mold_cook_browser"
    browser_fixture = repository / "tests" / "browser"
    setup_command = (
        "node -e \"const { chromium } = require('@playwright/test'); "
        + "const fs = require('fs'); "
        + "if (!fs.existsSync(chromium.executablePath())) process.exit(1)\""
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
    (browser_fixture / "node_modules").symlink_to(
        browser_node_modules, target_is_directory=True
    )
    authorization_content = canonical_bytes(authorization)
    runner_authorization_ref = _retain_runner(
        artifact_root, authorization_content, role="runner_authorization",
    )
    authorization_digest = runner_authorization_ref.digest
    runner_response = canonical_bytes({
        "authorization_digest": authorization_digest,
        "spec_digest": spec_digest,
        "curd_ids": list(coverage.curd_ids),
        "question": f"Approve runner limits {authorization_digest} for {spec_digest} and {coverage.curd_ids[0]}?",
        "response": "approve",
        "execution_authorized": True,
    })
    runner_response_ref = _retain_runner(
        artifact_root, runner_response, role="dialogue",
    )
    assert validate_runner_authority(
        runner_authorization_ref, runner_response_ref, artifact_root,
        spec_digest=spec_digest, coverage=coverage,
    ) == authorization
    setup = subprocess.run(
        ["bash", "-lc", setup_command],
        cwd=str(browser_fixture),
        env=environment,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert setup.returncode == 0, (setup.stdout + setup.stderr).decode(errors="replace")
    setup_output = setup.stdout + setup.stderr
    setup_output_digest = f"sha256:{hashlib.sha256(setup_output).hexdigest()}"
    _ = (
        artifact_root / f"sha256-{setup_output_digest.removeprefix('sha256:')}"
    ).write_bytes(setup_output)
    setup_evidence = SetupEvidence(
        prerequisite_curd_id="curd-1",
        plan_digest=plan.digest,
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
    setup_evidence_ref = _retain_runner(
        artifact_root, setup_evidence_content, role="setup_evidence",
        schema_uri=SETUP_EVIDENCE_SCHEMA_URI,
    )
    assert validate_mold_cook_setup_evidence(
        setup_evidence_ref, authorization=authorization, plan=plan,
        artifact_root=artifact_root,
    ) == setup_evidence
    assert validate_bound_execution(
        spec_ref=spec_ref, planner_result_ref=planner_ref, plan_ref=plan_ref,
        coverage=coverage, artifact_root=artifact_root,
        runner_authorization_ref=runner_authorization_ref,
        runner_response_ref=runner_response_ref,
        setup_evidence_refs=(setup_evidence_ref,),
    ) == plan
    result_path = cast(str, payload["result_path"])
    production_env = {
        **environment,
        "PYTHONPATH": str(ROOT / "src"),
    }
    produced = subprocess.run(
        [
            sys.executable,
            str(outer / "outer_workflow.py"),
            result_path,
            str(repository),
            str(artifact_root),
            str(Path(runner_authorization_ref.uri.removeprefix("file://"))),
            str(Path(runner_response_ref.uri.removeprefix("file://"))),
            str(Path(setup_evidence_ref.uri.removeprefix("file://"))),
        ],
        cwd=str(repository),
        env=production_env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert produced.returncode == 0, produced.stderr
    production_result = cast(dict[str, object], json.loads(produced.stdout))
    assert production_result == {
        "feature": "index.html",
        "results": 1,
        "disposition": "passed",
        "whole_task_complete": True,
        "remainder": [],
    }
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
            "PLAYWRIGHT_BROWSERS_PATH": browser_path,
            "PLAYWRIGHT_OUTPUT_DIR": str(tmp_path / "playwright-results"),
        }
        fixture = browser_fixture
        result = subprocess.run(
            [
                "node_modules/.bin/playwright",
                "test",
                "--config=playwright.config.mjs",
            ],
            cwd=str(fixture),
            env=browser_env,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
