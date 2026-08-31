"""Import-closure, native-member, and isolated-execution checks (AC-7).

Mirrors tests/python/test_check_bundles.py's in-memory-zip-fixture pattern:
no pyz is built here for the synthetic cases, only assembled member-by-member
in a BytesIO archive. The committed-bundle cases read the real, already-built
skills/*/scripts/*.pyz directly -- no rebuild.
"""

from __future__ import annotations

import io
import re
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


_PYZ_REFERENCE = re.compile(r"[\w-]+\.pyz")

# ultracook is a retired skill: its SKILL.md documents that no ultracook.pyz
# is published and that runtime moved into cook.pyz, purely as retirement
# prose (see skills/ultracook/SKILL.md's "What did not move" section) -- not
# an instruction for any code path to invoke another skill's archive.
_RETIRED_REDIRECT_SKILLS = frozenset({"ultracook"})


def _referencing_files() -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for path in sorted(REPO_ROOT.glob("skills/*/SKILL.md")):
        files.append((path.parent.name, path))
    for path in sorted((REPO_ROOT / "src" / "easy_cheese" / "skills").rglob("*.py")):
        relative = path.relative_to(REPO_ROOT / "src" / "easy_cheese" / "skills")
        skill_dir = relative.parts[0]
        files.append((skill_dir.replace("_", "-"), path))
    return files


def test_skill_docs_and_sources_only_reference_their_own_pyz_archive() -> None:
    violations: list[str] = []
    for skill, path in _referencing_files():
        if skill in _RETIRED_REDIRECT_SKILLS:
            continue
        text = path.read_text(encoding="utf-8")
        for match in _PYZ_REFERENCE.finditer(text):
            archive = match.group(0)[: -len(".pyz")]
            if archive == "common":
                violations.append(f"{path}: references obsolete shared bundle common.pyz")
            elif archive != skill:
                violations.append(
                    f"{path}: references {archive}.pyz, not its own {skill}.pyz"
                )
    assert violations == [], "\n".join(violations)


def test_no_skill_ever_references_common_pyz_including_retired_docs() -> None:
    for _skill, path in _referencing_files():
        text = path.read_text(encoding="utf-8")
        assert "common.pyz" not in text, f"{path}: references obsolete shared bundle common.pyz"
