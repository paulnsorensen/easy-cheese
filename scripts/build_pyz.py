#!/usr/bin/env python3
"""Build one hash-locked Shiv archive per packaged Python skill."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from collections.abc import Callable, Iterable, Sequence
from email.parser import Parser
from pathlib import Path
from types import ModuleType
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
PACKAGE_ROOT = SRC_ROOT / "easy_cheese"
SKILLS_ROOT = PACKAGE_ROOT / "skills"
RUNTIME_LOCK = REPO_ROOT / "requirements" / "runtime.txt"
SCHEMA_ROOT = SRC_ROOT / "easy_cheese_schemas"
SCHEMA_CONTRACT_SOURCE = SCHEMA_ROOT / "contracts.py"
SCHEMA_CATALOG_SOURCE = SCHEMA_ROOT / "_schema_catalog.py"
PHASE_REGISTRY_SOURCE = SCHEMA_ROOT / "_compiled_phase_registry.py"
DOCUMENT_RULES_SOURCE = PACKAGE_ROOT / "shared" / "document_rules.py"
SOURCE_DATE_EPOCH = "315532800"
NATIVE_SUFFIXES = {".so", ".pyd", ".dylib"}
VERSION = cast(
    str,
    tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())["project"]["version"],
)
SKILLS = tuple(
    sorted(
        path.parent.name.replace("_", "-") for path in SKILLS_ROOT.glob("*/commands.py")
    )
)


def _compiler_module(name: str) -> ModuleType:
    """Load a build-only compiler source module (excluded from wheels)."""
    package_entry = str(SCHEMA_ROOT)
    if package_entry not in sys.path:
        sys.path.insert(0, package_entry)
    return importlib.import_module(name)


def _phase_compiler() -> Callable[[Iterable[Path]], str]:
    compiler = _compiler_module("_phase_registry_compiler")
    return cast(
        Callable[[Iterable[Path]], str],
        getattr(compiler, "compile_phase_files_to_source"),
    )


def _compiled_phase_registry_source() -> str:
    return _phase_compiler()(sorted(REPO_ROOT.glob("skills/*/phase-contract.yaml")))


def _schema_catalog_compiler() -> tuple[
    Callable[[ModuleType], tuple[tuple[str, str], ...]],
    Callable[[Sequence[tuple[str, str]]], str],
]:
    compiler = _compiler_module("_schema_catalog_compiler")
    return (
        cast(
            Callable[[ModuleType], tuple[tuple[str, str], ...]],
            getattr(compiler, "collect"),
        ),
        cast(Callable[[Sequence[tuple[str, str]]], str], getattr(compiler, "render")),
    )


def _schema_contract_module() -> ModuleType:
    module = ModuleType("_build_schema_contracts")
    module.__file__ = str(SCHEMA_CONTRACT_SOURCE)
    sys.modules[module.__name__] = module
    source = SCHEMA_CONTRACT_SOURCE.read_bytes()
    exec(compile(source, str(SCHEMA_CONTRACT_SOURCE), "exec"), module.__dict__)
    return module


def _compiled_schema_catalog_source() -> str:
    collect, render = _schema_catalog_compiler()
    return render(collect(_schema_contract_module()))


def _document_rules_compiler() -> tuple[
    Callable[[type], type],
    Callable[[type], str],
]:
    compiler = _compiler_module("_document_rules_compiler")
    return (
        cast(Callable[[type], type], getattr(compiler, "collect")),
        cast(Callable[[type], str], getattr(compiler, "render")),
    )


def compiled_document_rules_source() -> str:
    collect, render = _document_rules_compiler()
    contract = cast(type, getattr(_schema_contract_module(), "MoldSpecDocument"))
    return render(collect(contract))


def _checked_in_generated_file_bytes(
    expected_source: str,
    source: Path,
    *,
    artifact_name: str,
) -> bytes:
    expected = expected_source.encode()
    try:
        actual = source.read_bytes()
    except FileNotFoundError as exc:
        raise RuntimeError(f"checked-in {artifact_name} is missing: {source}") from exc
    if actual != expected:
        target = (
            source.relative_to(REPO_ROOT)
            if source.is_relative_to(REPO_ROOT)
            else source
        )
        raise RuntimeError(f"checked-in {artifact_name} is stale; regenerate {target}")
    return actual


# The checked-in runtime sources this build compiles, and the renderer that
# produces each one. `--write-generated` writes them; the build checks them.
GENERATED_RUNTIME_SOURCES: tuple[tuple[Path, str, "Callable[[], str]"], ...] = (
    (PHASE_REGISTRY_SOURCE, "phase registry", lambda: _compiled_phase_registry_source()),
    (SCHEMA_CATALOG_SOURCE, "schema catalog", lambda: _compiled_schema_catalog_source()),
    (DOCUMENT_RULES_SOURCE, "document rules", lambda: compiled_document_rules_source()),
)


def _validate_generated_runtime() -> None:
    for source, artifact_name, render in GENERATED_RUNTIME_SOURCES:
        _ = _checked_in_generated_file_bytes(
            render(), source, artifact_name=artifact_name
        )


def write_generated_runtime() -> list[Path]:
    """Write every generated runtime source. Return the paths this call changed."""
    changed: list[Path] = []
    for source, _artifact_name, render in GENERATED_RUNTIME_SOURCES:
        expected = render().encode()
        current = source.read_bytes() if source.is_file() else None
        if current == expected:
            continue
        _ = source.write_bytes(expected)
        changed.append(source)
    return changed


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _wheel_metadata(path: Path) -> tuple[str, str, tuple[str, ...]]:
    with zipfile.ZipFile(path) as archive:
        members = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(members) != 1:
            raise ValueError(f"wheel has no unique METADATA: {path.name}")
        metadata = Parser().parsestr(archive.read(members[0]).decode())
    return (
        metadata["Name"],
        metadata["Version"],
        tuple(metadata.get_all("Requires-Dist", [])),
    )


def validate_pure_wheel(path: Path) -> None:
    """Reject wheels that are not platform-independent pure Python."""
    if not re.fullmatch(r".+-py\d+(?:\.\d+)?-none-any\.whl", path.name):
        raise ValueError(f"wheel is not py3-none-any: {path.name}")
    with zipfile.ZipFile(path) as archive:
        wheel_files = [
            name for name in archive.namelist() if name.endswith(".dist-info/WHEEL")
        ]
        if len(wheel_files) != 1:
            raise ValueError(f"wheel has no unique WHEEL metadata: {path.name}")
        wheel = archive.read(wheel_files[0]).decode()
        if not re.search(r"(?im)^Root-Is-Purelib:\s*true\s*$", wheel):
            raise ValueError(f"wheel is not Root-Is-Purelib: true: {path.name}")
        native = [
            name
            for name in archive.namelist()
            if Path(name).suffix.lower() in NATIVE_SUFFIXES
        ]
        if native:
            raise ValueError(f"wheel contains native members: {', '.join(native)}")


def _build_environment() -> dict[str, str]:
    environment = os.environ.copy()
    if "SOURCE_DATE_EPOCH" not in environment:
        environment["SOURCE_DATE_EPOCH"] = SOURCE_DATE_EPOCH
    return environment


def _require_build_frontend() -> None:
    if importlib.util.find_spec("build") is None:
        raise RuntimeError(
            "PEP 517 build tooling is required; install requirements-build.txt"
        )


def _project_toml(
    name: str, *, dependencies: Iterable[str], script: str | None = None
) -> str:
    lines = [
        "[build-system]",
        'requires = ["hatchling"]',
        'build-backend = "hatchling.build"',
        "",
        "[project]",
        f'name = "{name}"',
        f'version = "{VERSION}"',
        'requires-python = ">=3.11"',
        f"dependencies = {json.dumps(sorted(set(dependencies)))}",
    ]
    if script is not None:
        lines.extend(("", "[project.scripts]", script))
    lines.extend(
        ("", "[tool.hatch.build.targets.wheel]", 'packages = ["src/easy_cheese"]')
    )
    return "\n".join(lines) + "\n"


def _copy_package_scaffold(project: Path) -> Path:
    destination = project / "src" / "easy_cheese"
    destination.mkdir(parents=True)
    _ = shutil.copy2(PACKAGE_ROOT / "__init__.py", destination / "__init__.py")
    return destination


def _normalize_internal_wheel(wheel: Path) -> Path:
    """Remove compressor-specific bytes from a PEP 517-built wheel."""
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{wheel.stem}-", suffix=".whl", dir=wheel.parent
    )
    os.close(descriptor)
    normalized = Path(temporary)
    try:
        with (
            zipfile.ZipFile(wheel) as source,
            zipfile.ZipFile(normalized, "w", compression=zipfile.ZIP_STORED) as target,
        ):
            for source_info in sorted(
                source.infolist(), key=lambda item: item.filename
            ):
                info = zipfile.ZipInfo(source_info.filename, (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3  # noqa: V101
                info.external_attr = source_info.external_attr
                info.internal_attr = source_info.internal_attr
                target.writestr(info, source.read(source_info))
        os.replace(normalized, wheel)
    finally:
        normalized.unlink(missing_ok=True)
    return wheel


def _build_project(project: Path, wheelhouse: Path) -> Path:
    _require_build_frontend()
    before = set(wheelhouse.glob("*.whl"))
    _ = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(wheelhouse),
            str(project),
        ],
        cwd=REPO_ROOT,
        env=_build_environment(),
        check=True,
    )
    built = set(wheelhouse.glob("*.whl")) - before
    if len(built) != 1:
        raise RuntimeError(f"PEP 517 build produced {len(built)} wheels for {project}")
    wheel = _normalize_internal_wheel(built.pop())
    validate_pure_wheel(wheel)
    return wheel


def _build_schema_wheel(wheelhouse: Path) -> Path:
    _require_build_frontend()
    before = set(wheelhouse.glob("*.whl"))
    _ = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(wheelhouse),
            str(REPO_ROOT),
        ],
        cwd=REPO_ROOT,
        env=_build_environment(),
        check=True,
    )
    built = set(wheelhouse.glob("*.whl")) - before
    if len(built) != 1:
        raise RuntimeError(f"schema build produced {len(built)} wheels")
    wheel = _normalize_internal_wheel(built.pop())
    validate_pure_wheel(wheel)
    return wheel


def _build_shared_wheel(project_root: Path, wheelhouse: Path) -> Path:
    project = project_root / "shared"
    package = _copy_package_scaffold(project)
    _ = shutil.copytree(PACKAGE_ROOT / "shared", package / "shared")
    _ = (project / "pyproject.toml").write_text(
        _project_toml(
            "easy-cheese-shared",
            dependencies=(f"easy-cheese-schemas=={VERSION}",),
        ),
        encoding="utf-8",
    )
    return _build_project(project, wheelhouse)


def _build_skill_wheel(skill: str, project_root: Path, wheelhouse: Path) -> Path:
    package_name = skill.replace("-", "_")
    project = project_root / package_name
    package = _copy_package_scaffold(project)
    skills = package / "skills"
    skills.mkdir()
    _ = shutil.copy2(SKILLS_ROOT / "__init__.py", skills / "__init__.py")
    _ = shutil.copytree(SKILLS_ROOT / package_name, skills / package_name)
    _ = (project / "pyproject.toml").write_text(
        _project_toml(
            f"easy-cheese-{skill}",
            dependencies=(f"easy-cheese-shared=={VERSION}",),
            script=f'"{skill}" = "easy_cheese.skills.{package_name}.commands:main"',
        ),
        encoding="utf-8",
    )
    return _build_project(project, wheelhouse)


def _download_runtime_wheels(wheelhouse: Path) -> tuple[Path, ...]:
    _ = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--dest",
            str(wheelhouse),
            "--only-binary=:all:",
            "--require-hashes",
            "--requirement",
            str(RUNTIME_LOCK),
        ],
        cwd=REPO_ROOT,
        check=True,
    )
    wheels = tuple(sorted(wheelhouse.glob("*.whl")))
    for wheel in wheels:
        validate_pure_wheel(wheel)
    return wheels


def build_wheelhouse(
    wheelhouse: Path,
    skills: Iterable[str] | None = None,
) -> None:
    """Build the private pure-Python wheelhouse used by Shiv."""
    selected = tuple(skills or SKILLS)
    unknown = sorted(set(selected) - set(SKILLS))
    if unknown:
        raise ValueError(f"unknown skill(s): {', '.join(unknown)}")
    _validate_generated_runtime()
    wheelhouse.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="easy-cheese-projects-") as temporary:
        projects = Path(temporary)
        _ = _download_runtime_wheels(wheelhouse)
        _ = _build_schema_wheel(wheelhouse)
        _ = _build_shared_wheel(projects, wheelhouse)
        for skill in selected:
            _ = _build_skill_wheel(skill, projects, wheelhouse)


def _resolved_requirements(skill: str, wheelhouse: Path) -> str:
    report = wheelhouse.parent / f"{skill}-pip-report.json"
    _ = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--dry-run",
            "--ignore-installed",
            "--no-index",
            "--find-links",
            str(wheelhouse),
            "--only-binary=:all:",
            "--report",
            str(report),
            f"easy-cheese-{skill}=={VERSION}",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    by_name = {
        _normalize(_wheel_metadata(path)[0]): path for path in wheelhouse.glob("*.whl")
    }
    lines: list[str] = []
    for name, version in _pip_report_records(report):
        wheel = by_name.get(_normalize(name))
        if wheel is None:
            raise RuntimeError(
                f"pip resolved a wheel outside the private wheelhouse: {name}"
            )
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        lines.append(f"{name}=={version} --hash=sha256:{digest}")
    return "\n".join(sorted(lines, key=str.casefold)) + "\n"


def _pip_report_records(report: Path) -> list[tuple[str, str]]:
    """(name, version) pairs from a pip `--dry-run --report` document."""
    data = cast(dict[str, object], json.loads(report.read_text()))
    install = data.get("install")
    if not isinstance(install, list):
        raise RuntimeError("pip report has no install list")
    records: list[tuple[str, str]] = []
    for item in cast(list[dict[str, object]], install):
        metadata = cast(dict[str, object], item.get("metadata"))
        name = metadata.get("name")
        version = metadata.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise RuntimeError("pip report item must carry string name and version")
        records.append((name, version))
    return records


def _requirements_for(
    skill: str,
    wheelhouse: Path,
) -> Path:
    expected = _resolved_requirements(skill, wheelhouse)
    requirements = wheelhouse.parent / f"{skill}-requirements.txt"
    _ = requirements.write_text(expected, encoding="utf-8")
    return requirements


def _shiv_command(
    skill: str, requirements: Path, target: Path, wheelhouse: Path
) -> list[str]:
    executable = shutil.which("shiv")
    if executable:
        command = [executable]
    elif importlib.util.find_spec("shiv") is not None:
        command = [sys.executable, "-m", "shiv"]
    else:
        raise RuntimeError("Shiv is required; install requirements-build.txt")
    return command + [
        "--output-file",
        str(target),
        "--console-script",
        skill,
        "--python",
        "/usr/bin/env python3",
        "--reproducible",
        "--uncompressed",
        "--no-index",
        "--find-links",
        str(wheelhouse),
        "--only-binary=:all:",
        "--require-hashes",
        "--requirement",
        str(requirements),
    ]


def _build_from_wheelhouse(
    skill: str,
    target: Path,
    wheelhouse: Path,
) -> Path:
    requirements = _requirements_for(skill, wheelhouse)
    target.parent.mkdir(parents=True, exist_ok=True)
    _ = subprocess.run(
        _shiv_command(skill, requirements, target, wheelhouse),
        cwd=REPO_ROOT,
        env=_build_environment(),
        check=True,
    )
    target.chmod(0o755)
    return target


def build_bundles(
    destinations: dict[str, Path],
) -> dict[str, Path]:
    unknown = sorted(set(destinations) - set(SKILLS))
    if unknown:
        raise ValueError(f"unknown skill(s): {', '.join(unknown)}")
    with tempfile.TemporaryDirectory(prefix="easy-cheese-build-") as temporary:
        wheelhouse = Path(temporary) / "wheelhouse"
        build_wheelhouse(wheelhouse, destinations)
        return {
            skill: _build_from_wheelhouse(
                skill,
                target,
                wheelhouse,
            )
            for skill, target in destinations.items()
        }


def build_bundle(skill: str, target: Path) -> Path:
    return build_bundles({skill: target})[skill]


def cached_bundle(skill: str) -> Path:
    if skill not in SKILLS:
        raise ValueError(f"unknown skill: {skill}")
    bundle = REPO_ROOT / "skills" / skill / "scripts" / f"{skill}.pyz"
    if not bundle.is_file():
        raise RuntimeError(
            f"checked-in bundle is missing: {bundle.relative_to(REPO_ROOT)}"
        )
    return bundle


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--out-dir", type=Path)
    _ = parser.add_argument(
        "--write-generated",
        action="store_true",
        help="write every generated runtime source, then exit without building",
    )
    _ = parser.add_argument("skills", nargs="*")
    args = parser.parse_args(argv[1:])
    if cast(bool, args.write_generated):
        for path in write_generated_runtime():
            print(f"wrote {path.relative_to(REPO_ROOT)}")
        return 0
    out_dir = cast(Path | None, args.out_dir)
    skills_arg = cast(list[str] | None, args.skills)
    selected = tuple(skills_arg or SKILLS)
    unknown = sorted(set(selected) - set(SKILLS))
    if unknown:
        parser.error(f"unknown skill(s): {', '.join(unknown)}")
    destinations = {
        skill: (
            out_dir / f"{skill}.pyz"
            if out_dir
            else REPO_ROOT / "skills" / skill / "scripts" / f"{skill}.pyz"
        )
        for skill in selected
    }
    try:
        built = build_bundles(destinations)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(
            f"ERROR: bundle build failed for {', '.join(selected)}: {exc}",
            file=sys.stderr,
        )
        if isinstance(exc, subprocess.CalledProcessError):
            streams: tuple[tuple[str, str | bytes | None], ...] = (
                ("stdout", cast(str | bytes | None, exc.stdout)),
                ("stderr", cast(str | bytes | None, exc.stderr)),
            )
            for stream_name, output in streams:
                if output:
                    text = (
                        output.decode(errors="replace")
                        if isinstance(output, bytes)
                        else output
                    )
                    print(
                        f"--- subprocess {stream_name} ---\n{text.rstrip()}",
                        file=sys.stderr,
                    )
        return 1
    for target in built.values():
        print(f"built {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
