"""Import-closure, native-member, and isolated-execution checks (AC-7).

Mirrors tests/python/test_check_bundles.py's in-memory-zip-fixture pattern:
no pyz is built here for the synthetic cases, only assembled member-by-member
in a BytesIO archive. The committed-bundle cases read the real, already-built
skills/*/scripts/*.pyz directly -- no rebuild.
"""

from __future__ import annotations

import io
import subprocess
import zipfile
from pathlib import Path

import pytest

from scripts import check_bundles

REPO_ROOT = Path(__file__).resolve().parents[2]


def _archive(members: dict[str, bytes]) -> zipfile.ZipFile:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    _ = data.seek(0)
    return zipfile.ZipFile(data)


def test_native_members_rejects_shared_objects() -> None:
    archive = _archive(
        {
            "site-packages/easy_cheese/demo.py": b"",
            "site-packages/somepkg/_speedups.cpython-311-darwin.so": b"\x00",
        }
    )
    assert check_bundles.native_members(archive) == [
        "site-packages/somepkg/_speedups.cpython-311-darwin.so"
    ]


def test_check_import_closure_flags_unresolved_deferred_import() -> None:
    archive = _archive(
        {
            "site-packages/easy_cheese/demo.py": (
                b"def run():\n    import totally_missing_module\n"
            )
        }
    )
    assert check_bundles.check_import_closure(archive) == [
        "unresolved import 'totally_missing_module'"
        + " in site-packages/easy_cheese/demo.py"
    ]


def test_check_import_closure_passes_guarded_import_error_with_stdlib_fallback() -> (
    None
):
    archive = _archive(
        {
            "site-packages/easy_cheese/demo.py": (
                b"try:\n"
                b"    import ujson as jsonlib\n"
                b"except ImportError:\n"
                b"    import json as jsonlib\n"
            )
        }
    )
    assert check_bundles.check_import_closure(archive) == []


def test_check_import_closure_flags_cross_skill_style_unresolved_import() -> None:
    archive = _archive(
        {
            "site-packages/easy_cheese/demo.py": (
                b"from easy_cheese.skills.other_skill import helper\n"
            )
        }
    )
    assert check_bundles.check_import_closure(archive) == [
        "unresolved import 'easy_cheese.skills.other_skill.helper'"
        + " in site-packages/easy_cheese/demo.py"
    ]


def test_check_import_closure_flags_ambient_third_party_import() -> None:
    archive = _archive({"site-packages/easy_cheese/demo.py": b"import requests\n"})
    assert check_bundles.check_import_closure(archive) == [
        "unresolved import 'requests' in site-packages/easy_cheese/demo.py"
    ]


def test_check_import_closure_resolves_command_manifest_target() -> None:
    archive = _archive(
        {
            "site-packages/easy_cheese/dispatch.py": (
                b'COMMANDS = [Command("demo", "easy_cheese.handler:main")]\n'
            ),
            "site-packages/easy_cheese/handler.py": b"def main() -> None:\n    pass\n",
        }
    )
    assert check_bundles.check_import_closure(archive) == []


def test_check_import_closure_flags_unresolved_command_manifest_target() -> None:
    archive = _archive(
        {
            "site-packages/easy_cheese/dispatch.py": (
                b'COMMANDS = [Command("demo", "easy_cheese.missing:main")]\n'
            )
        }
    )
    assert check_bundles.check_import_closure(archive) == [
        "unresolved Command target 'easy_cheese.missing'"
        + " in site-packages/easy_cheese/dispatch.py"
    ]


def test_check_import_closure_resolves_relative_import_to_sibling_module() -> None:
    archive = _archive(
        {
            "site-packages/easy_cheese/skills/foo/__init__.py": b"",
            "site-packages/easy_cheese/skills/foo/handler.py": b"from . import sibling\n",
            "site-packages/easy_cheese/skills/foo/sibling.py": b"",
        }
    )
    assert check_bundles.check_import_closure(archive) == []


def test_check_import_closure_flags_unresolved_relative_import() -> None:
    archive = _archive(
        {
            "site-packages/easy_cheese/skills/foo/__init__.py": b"",
            "site-packages/easy_cheese/skills/foo/handler.py": (
                b"from . import missing_sibling\n"
            ),
        }
    )
    assert check_bundles.check_import_closure(archive) == [
        "unresolved import 'easy_cheese.skills.foo.missing_sibling'"
        + " in site-packages/easy_cheese/skills/foo/handler.py"
    ]


def test_all_committed_bundles_pass_closure_and_native_checks() -> None:
    bundles = sorted(REPO_ROOT.glob("skills/*/scripts/*.pyz"))
    assert bundles, "expected committed .pyz bundles under skills/*/scripts/"
    for path in bundles:
        with zipfile.ZipFile(path) as archive:
            problems = [
                f"native member: {name}"
                for name in check_bundles.native_members(archive)
            ]
            problems += check_bundles.check_import_closure(archive)
        assert problems == [], f"{path.relative_to(REPO_ROOT)}: {problems}"


def test_isolated_execution_check_passes_on_a_real_committed_bundle() -> None:
    pyz = REPO_ROOT / "skills" / "melt" / "scripts" / "melt.pyz"
    assert pyz.exists(), pyz
    assert check_bundles.check_isolated_execution(pyz) == []


def test_check_isolated_execution_flags_module_only_in_user_site_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A module reachable only through user site-packages must not resolve.

    The marker lives in a temporary ``PYTHONUSERBASE`` site directory, never in
    the developer's real user site directory.
    """
    marker = "easy_cheese_isolation_marker_for_test"
    user_base = tmp_path / "userbase"
    monkeypatch.setenv("PYTHONUSERBASE", str(user_base))
    interpreter = check_bundles._isolated_interpreter()  # pyright: ignore[reportPrivateUsage]
    user_site = Path(
        subprocess.run(
            [interpreter, "-c", "import site; print(site.getusersitepackages())"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    assert user_base in user_site.parents, user_site
    user_site.mkdir(parents=True, exist_ok=True)
    _ = (user_site / f"{marker}.py").write_text("VALUE = 1\n", encoding="utf-8")

    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("__main__.py", f"import {marker}\n".encode())
    pyz = tmp_path / "demo.pyz"
    _ = pyz.write_bytes(data.getvalue())

    # Control: a non-isolated run resolves the marker from the temporary site.
    control = subprocess.run(
        [interpreter, str(pyz)], cwd=tmp_path, capture_output=True, text=True
    )
    assert control.returncode == 0, control.stdout + control.stderr

    problems = check_bundles.check_isolated_execution(pyz)
    assert any(marker in p for p in problems), problems


def test_check_pyz_references_finds_no_violations_across_the_repo() -> None:
    assert check_bundles.check_pyz_references() == []
