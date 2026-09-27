#!/usr/bin/env python3
"""Gate the checked-in runtime that wedge packages.

Three checks run before any skill archive is built or a lock is trusted:

- every generated runtime source (phase registry, schema catalog, document
  rules, bundle command index) is current with its compiler inputs;
- every skill's `COMMANDS` manifest agrees with its `@bundle_command` surface;
- skill documents and sources name only their own launcher, and no checked-in
  `.pyz` archive or `common.pyz` reference survives.

`--write-generated` rewrites the generated sources instead of checking them.
wedge (pinned under tools/wedge/) builds each archive from `src/` and verifies the
committed locks; it does not run these gates, so `just test`, `just check`,
and CI run this script beside `wedge check`.
"""

from __future__ import annotations

import argparse
import importlib
import re
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from types import ModuleType
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
PACKAGE_ROOT = SRC_ROOT / "easy_cheese"
SKILLS_ROOT = PACKAGE_ROOT / "skills"
SCHEMA_ROOT = SRC_ROOT / "easy_cheese_schemas"
BUILD_SCRIPTS_ROOT = REPO_ROOT / "scripts"
SCHEMA_CATALOG_SOURCE = SCHEMA_ROOT / "_schema_catalog.py"
PHASE_REGISTRY_SOURCE = SCHEMA_ROOT / "_compiled_phase_registry.py"
DOCUMENT_RULES_SOURCE = PACKAGE_ROOT / "shared" / "document_rules.py"
BUNDLE_COMMAND_INDEX_SOURCE = PACKAGE_ROOT / "shared" / "bundle_command_index.py"
SKILLS = tuple(
    sorted(
        path.parent.name.replace("_", "-") for path in SKILLS_ROOT.glob("*/commands.py")
    )
)


def _import_from(root: Path, name: str) -> ModuleType:
    """Import `name` with `root` on sys.path."""
    entry = str(root)
    if entry not in sys.path:
        sys.path.insert(0, entry)
    return importlib.import_module(name)


def _compiler_module(name: str) -> ModuleType:
    """Load a build-only compiler source module (never packaged)."""
    return _import_from(BUILD_SCRIPTS_ROOT, name)


def _phase_compiler() -> Callable[[Iterable[Path]], str]:
    compiler = _compiler_module("_phase_registry_compiler")
    return cast(
        Callable[[Iterable[Path]], str],
        getattr(compiler, "compile_phase_files_to_source"),
    )


def _compiled_phase_registry_source() -> str:
    return _phase_compiler()(sorted(REPO_ROOT.glob("skills/*/phase-contract.yaml")))


def _schema_catalog_compiler() -> tuple[
    Callable[[Sequence[ModuleType]], tuple[tuple[str, str], ...]],
    Callable[[Sequence[tuple[str, str]]], str],
]:
    compiler = _compiler_module("_schema_catalog_compiler")
    return (
        cast(
            Callable[[Sequence[ModuleType]], tuple[tuple[str, str], ...]],
            getattr(compiler, "collect"),
        ),
        cast(Callable[[Sequence[tuple[str, str]]], str], getattr(compiler, "render")),
    )


def _contract_modules_inventory() -> ModuleType:
    return _import_from(SRC_ROOT, "easy_cheese_schemas._contract_modules")


def _imported_contract_modules() -> tuple[ModuleType, ...]:
    inventory = _contract_modules_inventory()
    module_names = cast(tuple[str, ...], getattr(inventory, "CONTRACT_MODULES"))
    return tuple(_import_from(SRC_ROOT, module_name) for module_name in module_names)


def _compiled_schema_catalog_source() -> str:
    """Compile the catalog from a normal import of each contract module.

    The import is safe. `schema_runtime` checks catalog staleness lazily,
    on first catalog use, not at import time.
    """
    collect, render = _schema_catalog_compiler()
    pairs = collect(_imported_contract_modules())
    return render(pairs)


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
    inventory = _contract_modules_inventory()
    module_name, attribute_name = cast(
        tuple[str, str], getattr(inventory, "DOCUMENT_RULES_TARGET")
    )
    module = _import_from(SRC_ROOT, module_name)
    target = cast(type, getattr(module, attribute_name))
    return render(collect(target))


def _bundle_command_index_compiler() -> tuple[
    Callable[[Sequence[tuple[str, ModuleType]]], tuple[object, object]],
    Callable[..., str],
]:
    compiler = _compiler_module("_bundle_command_index_compiler")
    return (
        cast(
            Callable[[Sequence[tuple[str, ModuleType]]], tuple[object, object]],
            getattr(compiler, "collect"),
        ),
        cast(Callable[..., str], getattr(compiler, "render")),
    )


def _imported_skill_command_modules(
    skills: Iterable[str],
) -> tuple[tuple[str, ModuleType], ...]:
    _ = _import_from(SRC_ROOT, "easy_cheese")
    return tuple(
        (
            skill,
            _import_from(
                SRC_ROOT, f"easy_cheese.skills.{skill.replace('-', '_')}.commands"
            ),
        )
        for skill in skills
    )


def _compiled_bundle_command_index_source() -> str:
    """Compile the cross-bundle command index from every skill's COMMANDS."""
    collect, render = _bundle_command_index_compiler()
    command_index, leaf_index = collect(_imported_skill_command_modules(SKILLS))
    return render(command_index, leaf_index)


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


# The checked-in runtime sources this gate compiles, and the renderer that
# produces each one. `--write-generated` writes them; the gate checks them.
GENERATED_RUNTIME_SOURCES: tuple[tuple[Path, str, "Callable[[], str]"], ...] = (
    (PHASE_REGISTRY_SOURCE, "phase registry", _compiled_phase_registry_source),
    (SCHEMA_CATALOG_SOURCE, "schema catalog", _compiled_schema_catalog_source),
    (DOCUMENT_RULES_SOURCE, "document rules", compiled_document_rules_source),
    (
        BUNDLE_COMMAND_INDEX_SOURCE,
        "bundle command index",
        _compiled_bundle_command_index_source,
    ),
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


def validate_command_surfaces(skills: Iterable[str]) -> None:
    """Reject a skill whose `COMMANDS` manifest and `@bundle_command` surface disagree.

    Runs the dispatcher's own two-way check plus `command_map`'s duplicate and
    alias-collision rejection against each manifest under `src/`, so a broken
    surface fails here rather than inside a published archive. Every failure
    names the skill.
    """
    package = _import_from(SRC_ROOT, "easy_cheese")
    origin = Path(package.__file__ or "").resolve()
    if not origin.is_relative_to(SRC_ROOT):
        raise RuntimeError(
            f"easy_cheese resolved from {origin}, not {SRC_ROOT}; "
            + "the surface gate must inspect the sources that get packaged"
        )
    from easy_cheese.shared.bundle_commands import (
        Command,
        command_map,
        validate_command_surface,
    )

    for skill in skills:
        module_name = f"easy_cheese.skills.{skill.replace('-', '_')}.commands"
        try:
            module = importlib.import_module(module_name)
            commands = cast(Sequence[Command], getattr(module, "COMMANDS"))
            validate_command_surface(module, commands)
            _ = command_map(commands)
        except (ImportError, SyntaxError, AttributeError, TypeError, ValueError) as exc:
            raise ValueError(f"{skill}: {exc}") from exc


# Any `<name>.pyz` token. Checked-in archives are retired; a skill's prose
# invokes its launcher, `python3 skills/<skill>/scripts/<skill>`.
_ARCHIVE_REFERENCE = re.compile(r"[\w-]+\.pyz")
# A launcher path. Group 1 is the skill directory when the path is complete.
_LAUNCHER_REFERENCE = re.compile(r"(?:skills/([\w-]+)/)?scripts/([\w-]+)\b")
# ultracook is a retired skill: its SKILL.md documents that no ultracook
# archive is published and that its runtime moved into cook, purely as
# retirement guidance.
_RETIRED_REDIRECT_SKILLS = frozenset({"ultracook"})
_SELF_PATH = Path(__file__).resolve()


def _owning_skill(path: Path) -> str | None:
    """The skill whose launcher a file may name, or None if none applies."""
    parts = path.relative_to(REPO_ROOT).parts
    if parts[0] == "skills":
        return parts[1]
    if parts[:3] == ("src", "easy_cheese", "skills"):
        return parts[3].replace("_", "-")
    if parts[:4] == ("website", "content", "docs", "skills") and len(parts) == 5:
        return path.stem
    return None


def _reference_roots() -> list[Path]:
    return [
        *REPO_ROOT.glob("skills/**/*.md"),
        # Launchers, but not the locks: a lock names its own .pyz asset.
        *(
            p
            for p in REPO_ROOT.glob("skills/*/scripts/*")
            if p.is_file() and not p.name.endswith(".wedge.json")
        ),
        *(
            p
            for p in (REPO_ROOT / "src").rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        ),
        *REPO_ROOT.glob("website/content/docs/**/*.md"),
        *(p for p in (REPO_ROOT / "scripts").glob("*.py") if p.resolve() != _SELF_PATH),
    ]


def check_skill_references() -> list[str]:
    """Skill docs and sources may name only their own launcher.

    A file naming another skill's launcher is either a stale doc (the skill was
    renamed or merged) or a real cross-skill call. Any `.pyz` token is a
    reference to the retired checked-in archives; `wedge check` rejects the
    files themselves.
    """
    violations: list[str] = []
    for path in sorted(set(_reference_roots())):
        skill = _owning_skill(path)
        if skill in _RETIRED_REDIRECT_SKILLS:
            continue
        relative = path.relative_to(REPO_ROOT)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # binary content carries no launcher references
        except OSError as exc:
            # A present-but-unreadable file was never inspected; say so
            # rather than letting the gate go green on it.
            violations.append(f"{relative}: unreadable ({exc.strerror or exc})")
            continue
        for match in _ARCHIVE_REFERENCE.finditer(text):
            if match.group(0) == "common.pyz":
                violations.append(
                    f"{relative}: references obsolete shared bundle common.pyz"
                )
            else:
                violations.append(
                    f"{relative}: references retired archive {match.group(0)}; "
                    + "name the launcher scripts/<skill> instead"
                )
        for match in _LAUNCHER_REFERENCE.finditer(text):
            directory, launcher = match.group(1), match.group(2)
            if launcher not in SKILLS:
                continue
            if directory is not None and directory != launcher:
                violations.append(
                    f"{relative}: names {match.group(0)}, which is not that skill's launcher"
                )
            elif skill is not None and launcher != skill:
                violations.append(
                    f"{relative}: references {launcher}'s launcher, not its own scripts/{skill}"
                )
    return violations


def check() -> list[str]:
    """Run every gate; return one line per problem."""
    problems: list[str] = []
    try:
        _validate_generated_runtime()
    except RuntimeError as exc:
        problems.append(str(exc))
    try:
        validate_command_surfaces(SKILLS)
    except (RuntimeError, ValueError) as exc:
        problems.append(f"command surface: {exc}")
    problems.extend(check_skill_references())
    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "--write-generated",
        action="store_true",
        help="write every generated runtime source, then exit without checking",
    )
    args = parser.parse_args(argv[1:])
    if cast(bool, args.write_generated):
        for path in write_generated_runtime():
            print(f"wrote {path.relative_to(REPO_ROOT)}")
        return 0
    problems = check()
    for problem in problems:
        print(f"! {problem}")
    if problems:
        return 1
    print(f"runtime gates passed for {len(SKILLS)} skills")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
