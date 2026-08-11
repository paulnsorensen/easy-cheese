"""Executable contract: skill docs must invoke helpers that actually resolve.

Scans every code span and fenced block in ``skills/**/*.md`` and checks:

- ``<bundle>.pyz <subcommand>`` names a shipped bundle whose dispatcher knows
  that subcommand;
- explicit ``skills/<skill>/scripts/<bundle>.pyz`` paths exist;
- ``${CLAUDE_SKILL_DIR}``-relative bundle paths resolve from the doc's own
  skill directory (cross-skill references use ``../<skill>/scripts/``);
- ``python3 shared/scripts/<file>.py`` invocations target a module with a
  ``__main__`` entry point, AND the doc's own skill ships that module inside
  one of its bundles — shared scripts are compiled from this repo into each
  consuming skill's .pyz precisely so installed skills never depend on the
  cheese checkout being present.

Guards the doc-rot class where a documented command dies at import or dispatch
before doing anything (cheese continue-resume fallback, age dimensions
``paths.py``-as-CLI, cook fan-pathway pathless ``common.pyz``).
"""

from __future__ import annotations

import ast
import re
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = REPO_ROOT / "skills"

_PYZ_REF = re.compile(r"(\S*?([\w-]+\.pyz))\s+([a-z][\w-]*)")
_SKILL_PATH = re.compile(r"\bskills/([\w-]+)/scripts/([\w-]+\.pyz)")
_SKILL_DIR_PATH = re.compile(
    r"\$\{CLAUDE_SKILL_DIR\}((?:/\.\./[\w-]+)?/scripts/[\w-]+\.pyz)"
)
_SHARED_CLI = re.compile(r"python3\s+shared/scripts/([\w.-]+\.py)\b")


def _dispatchers() -> dict[str, set[str]]:
    """Bundle filename -> union of dispatcher subcommands across shipped copies."""
    subcommands: dict[str, set[str]] = {}
    for pyz in SKILLS.glob("*/scripts/*.pyz"):
        with zipfile.ZipFile(pyz) as archive:
            main = archive.read("__main__.py").decode("utf-8")
        for line in main.splitlines():
            if line.startswith("SUBCOMMANDS = "):
                mapping = ast.literal_eval(line.removeprefix("SUBCOMMANDS = "))
                subcommands.setdefault(pyz.name, set()).update(mapping)
    return subcommands


def _shipped_modules() -> dict[str, set[str]]:
    """Skill name -> union of .py member basenames across its shipped bundles."""
    modules: dict[str, set[str]] = {}
    for pyz in SKILLS.glob("*/scripts/*.pyz"):
        skill = pyz.parts[-3]
        with zipfile.ZipFile(pyz) as archive:
            modules.setdefault(skill, set()).update(
                Path(name).name for name in archive.namelist() if name.endswith(".py")
            )
    return modules


def _command_texts(doc: Path) -> list[tuple[int, str]]:
    """(lineno, text) for each inline code span and fenced-block line."""
    texts: list[tuple[int, str]] = []
    fenced = False
    for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            texts.append((lineno, line))
        else:
            texts.extend((lineno, span) for span in re.findall(r"`([^`]+)`", line))
    return texts


def _doc_problems() -> list[str]:
    dispatchers = _dispatchers()
    shipped = _shipped_modules()
    problems: list[str] = []
    for doc in sorted(SKILLS.glob("**/*.md")):
        skill = doc.relative_to(SKILLS).parts[0]
        for lineno, text in _command_texts(doc):
            where = f"{doc.relative_to(REPO_ROOT)}:{lineno}"
            for full, bundle, sub in _PYZ_REF.findall(text):
                if "<" in full:
                    continue  # templated placeholder, not a literal invocation
                if bundle not in dispatchers:
                    problems.append(f"{where}: {bundle} is not shipped by any skill")
                elif sub not in dispatchers[bundle]:
                    problems.append(f"{where}: {bundle} has no subcommand {sub!r}")
            for skill_name, bundle in _SKILL_PATH.findall(text):
                if not (SKILLS / skill_name / "scripts" / bundle).is_file():
                    problems.append(
                        f"{where}: skills/{skill_name}/scripts/{bundle} does not exist"
                    )
            for tail in _SKILL_DIR_PATH.findall(text):
                if not (SKILLS / skill / tail.lstrip("/")).resolve().is_file():
                    problems.append(
                        f"{where}: ${{CLAUDE_SKILL_DIR}}{tail} does not resolve "
                        f"from skills/{skill}/"
                    )
            for script in _SHARED_CLI.findall(text):
                path = REPO_ROOT / "shared" / "scripts" / script
                if not path.is_file():
                    problems.append(f"{where}: shared/scripts/{script} does not exist")
                    continue
                if "__main__" not in path.read_text(encoding="utf-8"):
                    problems.append(
                        f"{where}: shared/scripts/{script} has no __main__ entry point"
                    )
                if script not in shipped.get(skill, set()):
                    problems.append(
                        f"{where}: shared/scripts/{script} is invoked but no bundle "
                        f"in skills/{skill}/scripts/ ships it — the source path only "
                        "exists in the cheese checkout"
                    )
    return problems


def test_skill_doc_helper_invocations_resolve() -> None:
    problems = _doc_problems()
    assert not problems, "\n" + "\n".join(problems)
