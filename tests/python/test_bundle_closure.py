"""Import-closure, native-member, and isolated-execution checks (AC-7).

Mirrors tests/python/test_check_bundles.py's in-memory-zip-fixture pattern:
no pyz is built here for the synthetic cases, only assembled member-by-member
in a BytesIO archive. The committed-bundle cases read the real, already-built
skills/*/scripts/*.pyz directly -- no rebuild.
"""

from __future__ import annotations

import io
import site
import zipfile
from pathlib import Path

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
    assert check_bundles._native_members(archive) == [  # pyright: ignore[reportPrivateUsage]
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
    problems = check_bundles.check_import_closure(archive)
    assert any("totally_missing_module" in p for p in problems), problems


def test_check_import_closure_passes_guarded_import_error_with_stdlib_fallback() -> None:
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
    problems = check_bundles.check_import_closure(archive)
    assert any("easy_cheese.skills.other_skill" in p for p in problems), problems


def test_check_import_closure_flags_ambient_third_party_import() -> None:
    archive = _archive(
        {"site-packages/easy_cheese/demo.py": b"import requests\n"}
    )
    problems = check_bundles.check_import_closure(archive)
    assert any("requests" in p for p in problems), problems


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
    problems = check_bundles.check_import_closure(archive)
    assert any("easy_cheese.missing" in p for p in problems), problems


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
    problems = check_bundles.check_import_closure(archive)
    assert any("missing_sibling" in p for p in problems), problems


def test_all_committed_bundles_pass_closure_and_native_checks() -> None:
    bundles = sorted(REPO_ROOT.glob("skills/*/scripts/*.pyz"))
    assert bundles, "expected committed .pyz bundles under skills/*/scripts/"
    for path in bundles:
        with zipfile.ZipFile(path) as archive:
            problems = [
                f"native member: {name}"
                for name in check_bundles._native_members(archive)  # pyright: ignore[reportPrivateUsage]
            ]
            problems += check_bundles.check_import_closure(archive)
        assert problems == [], f"{path.relative_to(REPO_ROOT)}: {problems}"


def test_isolated_execution_check_passes_on_a_real_committed_bundle() -> None:
    pyz = REPO_ROOT / "skills" / "melt" / "scripts" / "melt.pyz"
    assert pyz.exists(), pyz
    assert check_bundles.check_isolated_execution(pyz) == []


def test_check_isolated_execution_flags_module_only_in_user_site_packages(
    tmp_path: Path,
) -> None:
    marker = "easy_cheese_isolation_marker_for_test"
    user_site = Path(site.getusersitepackages())
    user_site.mkdir(parents=True, exist_ok=True)
    marker_path = user_site / f"{marker}.py"
    preexisting = marker_path.exists()
    _ = marker_path.write_text("VALUE = 1\n", encoding="utf-8")
    try:
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("__main__.py", f"import {marker}\n".encode())
        pyz = tmp_path / "demo.pyz"
        _ = pyz.write_bytes(data.getvalue())

        problems = check_bundles.check_isolated_execution(pyz)
    finally:
        if not preexisting:
            marker_path.unlink()

    assert any(marker in p for p in problems), problems


def test_check_pyz_references_finds_no_violations_across_the_repo() -> None:
    assert check_bundles.check_pyz_references() == []
