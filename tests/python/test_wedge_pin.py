"""The pinned wedge and direct archive configuration agree."""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import runtime_gates  # noqa: E402

_REQUIREMENT_PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)", re.MULTILINE)
_WEDGE_SOURCE = re.compile(
    r"https://github\.com/paulnsorensen/skillz-that-grillz\?subdirectory=lib&rev=([0-9a-f]{40})#\1"
)
# Marker-only dependency for Python < 3.11; the archives target 3.11 and up.
_TEST_ENV_ONLY = {"exceptiongroup"}


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _pins(text: str) -> set[tuple[str, str]]:
    return {
        (_normalize(name), version)
        for name, version in cast(list[tuple[str, str]], _REQUIREMENT_PIN.findall(text))
    }


def test_the_wedge_tool_project_pins_wedge_by_commit() -> None:
    lock = tomllib.loads((REPO_ROOT / "tools" / "wedge" / "uv.lock").read_text(encoding="utf-8"))
    packages = {
        cast(str, p["name"]): p for p in cast(list[dict[str, object]], lock["package"])
    }
    source = cast(dict[str, str], packages["skillz-that-grillz"]["source"])
    assert _WEDGE_SOURCE.fullmatch(source["git"]), source


def test_runtime_requirements_match_the_uv_lock() -> None:
    exported = subprocess.run(
        [
            "uv", "export", "--frozen", "--no-dev", "--no-emit-project", "--no-emit-local",
            "--group", "runtime", "--no-hashes", "--no-annotate", "--no-header",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    runtime = (REPO_ROOT / "requirements" / "runtime.txt").read_text(encoding="utf-8")
    pinned = {pin for pin in _pins(runtime) if pin[0] not in _TEST_ENV_ONLY}

    assert pinned == _pins(exported)


def test_every_python_skill_has_a_consistent_wedge_config() -> None:
    shared = tomllib.loads((REPO_ROOT / "skills" / "wedge.toml").read_text(encoding="utf-8"))
    assert shared["groups"] == ["runtime"]
    assert shared["repo"] == "paulnsorensen/easy-cheese"
    assert shared["source"] == "../../src/easy_cheese"
    configured = {path.parent.name for path in (REPO_ROOT / "skills").glob("*/wedge.toml")}
    assert configured == set(runtime_gates.SKILLS)
    for skill in runtime_gates.SKILLS:
        config = tomllib.loads(
            (REPO_ROOT / "skills" / skill / "wedge.toml").read_text(encoding="utf-8")
        )
        assert config == {
            "name": skill,
            "entry": f"easy_cheese.skills.{skill.replace('-', '_')}.commands:main",
            "source_paths": [
                "__init__.py",
                "skills/__init__.py",
                f"skills/{skill.replace('-', '_')}",
                "shared",
                "cli",
            ],
        }
        source_root = REPO_ROOT / "src" / "easy_cheese"
        for selected in cast(list[str], config["source_paths"]):
            assert (source_root / selected).exists(), selected
