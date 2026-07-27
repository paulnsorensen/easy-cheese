"""Cheese companion archive tests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402


def _assert_pins_installed_before(workflow_name: str, step: str) -> None:
    """Every distribution build_pyz vendors must be pip-pinned before ``step``.

    A missing pin makes the bundle build fail in CI (PyYAML) or ship a runtime
    that dies with ModuleNotFoundError under `python3 -S` (cattrs and friends).
    """
    workflow = (REPO_ROOT / ".github" / "workflows" / workflow_name).read_text()
    assert f"pip install --no-cache-dir pyyaml=={build_pyz.PY_YAML_VERSION}" in workflow
    for name, version, _roots in build_pyz.VENDORED_DISTRIBUTIONS:
        pin = f"{name.lower()}=={version}"
        assert pin in workflow, f"{workflow_name} is missing pin {pin}"
        assert workflow.index(pin) < workflow.index(step), f"{pin} installed after {step}"


def test_build_workflow_installs_pinned_distributions_before_bundle_build() -> None:
    _assert_pins_installed_before("build-pyz.yml", "python3 scripts/build_pyz.py")


def test_release_workflow_installs_pinned_distributions_before_staging() -> None:
    _assert_pins_installed_before("release.yml", "python3 scripts/stage_release.py")


def test_cheese_archive_bundles_pure_python_pyyaml_and_license(tmp_path: Path) -> None:
    archive = build_pyz.build_cheese_bundle(tmp_path / "cheese.pyz")
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        assert "yaml/__init__.py" in names
        assert bundle.read("licenses/PyYAML-LICENSE.txt").strip()
        assert "contract_registry.py" in names
        assert "work_cli.py" in names
        assert "handoff_resolve_cli.py" in names
        assert not [
            name
            for name in names
            if name.endswith((".so", ".pyd", ".pyc")) or "__pycache__" in name
        ]
        assert not [
            name for name in names if ".dist-info/" in name or ".egg-info/" in name
        ]
        assert all(info.date_time == build_pyz.ZIP_TIMESTAMP for info in bundle.infolist())


def test_cheese_archive_is_reproducible_with_bundled_pyyaml(tmp_path: Path) -> None:
    first = build_pyz.build_cheese_bundle(tmp_path / "first.pyz")
    second = build_pyz.build_cheese_bundle(tmp_path / "second.pyz")
    assert first.read_bytes() == second.read_bytes()


def test_cheese_archive_bundles_every_pinned_distribution(tmp_path: Path) -> None:
    """All four vendored distributions ship with their sources and licenses.

    handoff.py imports cattrs lazily, so a bundle missing it builds fine and
    only fails at runtime under `python3 -S`.
    Spec: .hallouminate/wiki/specs/cross-skill-work-contract.md:279.
    """
    archive = build_pyz.build_cheese_bundle(tmp_path / "cheese.pyz")
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        for name, _version, roots in build_pyz.VENDORED_DISTRIBUTIONS:
            assert bundle.read(f"licenses/{name}-LICENSE.txt").strip()
            for root in roots:
                assert {f"{root}/__init__.py", f"{root}.py"} & names, root


def test_cheese_archive_runs_without_ambient_packages(tmp_path: Path) -> None:
    archive = build_pyz.build_cheese_bundle(tmp_path / "cheese.pyz")
    result = subprocess.run(
        [sys.executable, "-S", str(archive), "contract-registry", "validate"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "contract registry valid"


def test_cheese_archive_executes_work_and_availability_commands(tmp_path: Path) -> None:
    archive = build_pyz.build_cheese_bundle(tmp_path / "cheese.pyz")
    env = dict(os.environ)
    env["XDG_DATA_HOME"] = str(tmp_path / "data")
    env["EASY_CHEESE_PROJECT"] = "bundle-test"
    created = subprocess.run(
        [
            sys.executable,
            "-S",
            str(archive),
            "work",
            "ensure",
            "--subject",
            "Bundled work",
            "--worktree",
            "wt_bundle",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    record = json.loads(created.stdout)
    assert record["title"] == "Bundled work"

    record_path = (
        tmp_path
        / "data"
        / "cheese"
        / "bundle-test"
        / "work"
        / record["work_id"]
        / "index.md"
    )
    frontmatter = record_path.read_text(encoding="utf-8").split("---\n", 2)[1]
    assert yaml.safe_load(frontmatter) == record

    resumed = subprocess.run(
        [sys.executable, "-S", str(archive), "work", "continue", "--worktree", "wt_bundle"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert resumed.returncode == 0, resumed.stderr
    assert json.loads(resumed.stdout)["action"] == "continue"

    artifact = tmp_path / "handoff.md"
    envelope = {
        "contract_version": "cheese-handoff/v1",
        "work_id": record["work_id"],
        "attempt_id": record["attempts"][0]["attempt_id"],
        "operation_id": "op_resolve",
        "phase": "cook",
        "status": "ok",
        "halt_reason": None,
        "next": "press",
        "artifact": str(artifact),
        "payload": {},
        "provenance": {},
    }
    artifact.write_text(
        "---\n" + yaml.safe_dump(envelope, sort_keys=False, allow_unicode=True) + "---\n",
        encoding="utf-8",
    )
    resolved = subprocess.run(
        [sys.executable, "-S", str(archive), "handoff-resolve"],
        input=json.dumps({"artifact": str(artifact), "available_phases": []}),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert resolved.returncode == 0, resolved.stderr
    assert json.loads(resolved.stdout) == {"action": "unavailable", "phase": "press"}
