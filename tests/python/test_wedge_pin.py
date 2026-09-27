"""The wedge pin and the committed wedge artifacts agree with each other.

scripts/wedge.py pins one wedge commit for every local build; the workflow pins
the same commit for CI. The runtime closure is pinned twice (uv.lock for the
archives, requirements/runtime.txt for the test and typing environments) and
must not drift. Every Python skill commits a wedge.toml, a launcher, and a
lock that name the same skill.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import runtime_gates  # noqa: E402
import wedge  # noqa: E402

_ACTION_PIN = re.compile(r"paulnsorensen/skillz-that-grillz/actions/wedge@([0-9a-f]{40})")
_REQUIREMENT_PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)", re.MULTILINE)
# Marker-only dependency for Python < 3.11; the archives target 3.11 and up.
_TEST_ENV_ONLY = {"exceptiongroup"}


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def test_workflow_pins_the_same_wedge_commit_as_the_script() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "wedge.yml").read_text(encoding="utf-8")
    pins = _ACTION_PIN.findall(workflow)

    assert len(pins) == 2, "check and publish jobs each pin the action once"
    assert set(pins) == {wedge.WEDGE_SHA}
    assert wedge.WEDGE_SHA in wedge.WEDGE_SPEC


def test_runtime_requirements_match_the_uv_lock() -> None:
    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    packages = cast(list[dict[str, object]], lock["package"])
    locked = {(_normalize(cast(str, p["name"])), cast(str, p["version"])) for p in packages}
    pins = cast(
        list[tuple[str, str]],
        _REQUIREMENT_PIN.findall((REPO_ROOT / "requirements" / "runtime.txt").read_text(encoding="utf-8")),
    )

    assert pins, "requirements/runtime.txt pins the runtime closure"
    missing = [
        (name, version)
        for name, version in pins
        if _normalize(name) not in _TEST_ENV_ONLY and (_normalize(name), version) not in locked
    ]
    assert missing == [], f"pins absent from uv.lock: {missing}"


def test_every_python_skill_has_a_consistent_wedge_config() -> None:
    configured = {path.parent.name for path in (REPO_ROOT / "skills").glob("*/wedge.toml")}
    assert configured == set(runtime_gates.SKILLS)
    for skill in runtime_gates.SKILLS:
        config = tomllib.loads((REPO_ROOT / "skills" / skill / "wedge.toml").read_text(encoding="utf-8"))
        assert config["name"] == skill
        assert config["entry"] == f"easy_cheese.skills.{skill.replace('-', '_')}.commands:main"
        assert config["repo"] == "paulnsorensen/easy-cheese"


def test_every_python_skill_commits_a_launcher_and_a_matching_lock() -> None:
    for skill in runtime_gates.SKILLS:
        scripts = REPO_ROOT / "skills" / skill / "scripts"
        launcher = scripts / skill
        assert launcher.is_file(), f"{skill}: missing launcher"
        assert launcher.stat().st_mode & 0o111, f"{skill}: launcher is not executable"
        lock = cast(dict[str, object], json.loads((scripts / f"{skill}.wedge.json").read_text(encoding="utf-8")))
        digest = cast(str, lock["content_sha256"])
        assert lock["name"] == skill
        assert lock["repo"] == "paulnsorensen/easy-cheese"
        assert lock["asset"] == f"{skill}-{digest[:12]}.pyz"


def test_no_checked_in_archives() -> None:
    assert list((REPO_ROOT / "skills").glob("*/scripts/*.pyz")) == []
