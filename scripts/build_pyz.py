#!/usr/bin/env python3
"""Build deterministic skill bundles and the Cheese contract-runtime companion.

The Cheese companion is the sole shipped runtime for cross-skill contracts. It
embeds the compiled phase registry and the pinned pure-Python distributions the
runtime imports, so users install no Python libraries separately. Ordinary skill
bundles remain independently built.
"""

from __future__ import annotations

import argparse
import ast
import importlib.metadata
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
SHARED_SCRIPTS = REPO_ROOT / "shared" / "scripts"
SHARED_MODULES = {p.stem for p in SHARED_SCRIPTS.glob("*.py")}
ZIP_TIMESTAMP = (1980, 1, 2, 0, 0, 0)
PY_YAML_VERSION = "6.0.2"
# (distribution name, pinned version, top-level import roots) for every library
# vendored into cheese.pyz. Each must be pure Python -- the bundle ships no
# compiled extensions. A root names either a package directory or a bare module.
VENDORED_DISTRIBUTIONS = (
    ("PyYAML", PY_YAML_VERSION, ("yaml",)),
    ("cattrs", "26.1.0", ("cattr", "cattrs")),
    ("attrs", "26.1.0", ("attr", "attrs")),
    ("typing-extensions", "4.16.0", ("typing_extensions",)),
)
CHEESE = "cheese"

sys.path.insert(0, str(SHARED_SCRIPTS))
import handoff  # noqa: E402


@dataclass(frozen=True)
class Shared:
    """A subcommand sourced from a shared/scripts/ module rather than a
    src/<skill>/ script, so one file backs the subcommand across every skill
    that registers it — no per-skill copy to keep in sync."""

    filename: str

# skill -> {subcommand: source}. A plain string names a src/<skill>/ script;
# Shared(...) names a shared/scripts/ module reused across skills. Subcommands
# keep each script's stem verbatim; the staged module name underscores it.
SKILLS: dict[str, dict[str, str | Shared]] = {
    "melt": {
        "batch-resolve": "batch-resolve.py",
        "conflict-pick": "conflict-pick.py",
        "conflict-summary": "conflict-summary.py",
        "detect-squash-residue": "detect-squash-residue.py",
        "lockfile-resolve": "lockfile-resolve.py",
    },
    "affinage": {"pr-status": "pr-status.py", "post-reply": "post-reply.py", "age-route": "fanout/age_route_cli.py"},
    "mold": {
        "artifact-path": Shared("artifact_path.py"),
        "curd-count": "curd-count.py",
        "gate-graph": "gate-graph.py",
        "render_html": Shared("html_report_cli.py"),
    },
    "briesearch": {
        "artifact-path": Shared("artifact_path.py"),
        "ground-check": "ground_check.py",
    },
    "cook": {"artifact-path": Shared("artifact_path.py"), "worktree": Shared("worktree.py")},
    "easy-cheese-setup": {
        "global": Shared("hallouminate_setup.py"),
        "local": Shared("hallouminate_setup.py"),
        "doctor": Shared("hallouminate_setup.py"),
    },
    "age": {"html-report": "age-html-report.py", "age-route": "fanout/age_route_cli.py"},
    "hard-cheese": {
        "append-attempt": "append-attempt.py",
        "freshness-check": "freshness-check.py",
    },
    "pasteurize": {
        "debug-tag-sweep": "debug-tag-sweep.py",
        "repro-rerun": "repro-rerun.py",
    },
    # /ultracook drives the fan-out engine (formerly /cheese-factory); its
    # sources live in the mode-neutral src/fanout/ dir (see SRC_DIRS).
    "ultracook": {
        "artifact-path": Shared("artifact_path.py"),
        "baseline": "baseline.py",
        "phase_decision": "phase_decision.py",
        "mode": "mode.py",
        "worktree": Shared("worktree.py"),
        "milknado": "milknado.py",
        "validate_decomposition": "validate_decomposition.py",
        "validate_manifest": "validate_manifest.py",
        "validate_pr_plan": "validate_pr_plan.py",
        "manifest_update": "manifest_update.py",
        "wiring_topo_sort": "wiring_topo_sort.py",
        "pr_plan_to_branches": "pr_plan_to_branches.py",
        "age-route": "fanout/age_route_cli.py",
        "curd-block": "fanout/curd_block.py",
    },
}

# A skill whose scripts live in a src dir named differently from the skill.
# /ultracook drives the neutral src/fanout/ engine rather than a src/ultracook/.
SRC_DIRS: dict[str, str] = {"ultracook": "fanout"}

# Cross-skill source modules a bundle needs beyond its own src dir, staged as
# plain importable modules (not subcommands). mold/curd-count imports the
# canonical PARALLEL_THRESHOLD from src/fanout/mode.py — one source file,
# vendored into both the mold and ultracook bundles.
EXTRA_MODULES: dict[str, list[tuple[str, str]]] = {
    "mold": [("fanout", "mode.py")],
    "age": [("fanout", "age_route.py")],
    "affinage": [("fanout", "age_route.py")],
    "ultracook": [("fanout", "age_route.py")],
}

# The historical common bundle remains available only through --out-dir for
# compatibility with developer tests. It is never deployed or staged for release;
# Cheese is the only shipped cross-skill contract runtime.
COMMON = "common"
COMMON_SUBCOMMANDS: dict[str, str] = {
    "slugify": "slugify.py",
    "write_handoff_artifact": "write_handoff_artifact.py",
    "read_handoff_slug": "read_handoff_slug.py",
    "findings_cli": "findings_cli.py",
    "gates_cli": "gates_cli.py",
    "paths_cli": "paths_cli.py",
    "handoff_cli": "handoff_cli.py",
    "render_html": "html_report_cli.py",
}
COMMON_CONSUMERS: frozenset[str] = frozenset({"cure", "age", "ultracook"})

_CACHE: dict[str, Path] = {}


def _module_name(filename: str) -> str:
    return Path(filename).stem.replace("-", "_")


def _src_dir(skill: str) -> Path:
    """The src/ subdir a skill's scripts live in (usually the skill name)."""
    return SRC_ROOT / SRC_DIRS.get(skill, skill)


def _files(skill: str) -> dict[str, str | Shared]:
    return COMMON_SUBCOMMANDS if skill == COMMON else SKILLS[skill]


def _common_consumers(targets: list[str], *, explicit: bool) -> frozenset[str]:
    """Which consumer skills receive common.pyz for this build request.

    A full build (no explicit targets) or an explicit ``common`` build fans out
    to every consumer; an explicit skill list fans only to the consumers named.
    """
    if not explicit or COMMON in targets:
        return COMMON_CONSUMERS
    return frozenset(s for s in targets if s in COMMON_CONSUMERS)


def _filename(source: str | Shared) -> str:
    return source.filename if isinstance(source, Shared) else source


def _source_path(skill: str, source: str | Shared) -> Path:
    """Resolve a subcommand's source file. Shared() modules and every
    common-bundle subcommand live in shared/scripts/; a plain string containing
    a path separator is src/-relative (a cross-skill source, e.g. a fanout/
    module bundled into age/affinage/ultracook); any other plain string in a
    real skill lives in src/<skill>/."""
    if isinstance(source, Shared) or skill == COMMON:
        return SHARED_SCRIPTS / _filename(source)
    if isinstance(source, str) and "/" in source:
        return SRC_ROOT / source
    return _src_dir(skill) / source


def _imported_top_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _local_skill_modules(skill: str) -> set[str]:
    """Non-registered local src/<skill>/*.py modules transitively imported by the skill."""
    if skill == COMMON:
        return set()
    skill_dir = _src_dir(skill)
    registered = {_module_name(_filename(src)) for src in SKILLS[skill].values()}
    frontier: set[str] = set()
    for source in SKILLS[skill].values():
        for name in _imported_top_names(_source_path(skill, source)):
            if name not in registered and (skill_dir / f"{name}.py").exists():
                frontier.add(name)
    resolved: set[str] = set()
    while frontier:
        name = frontier.pop()
        if name in resolved:
            continue
        resolved.add(name)
        for imp in _imported_top_names(skill_dir / f"{name}.py"):
            if imp not in registered and imp not in resolved and (skill_dir / f"{imp}.py").exists():
                frontier.add(imp)
    return resolved


def needed_shared(skill: str) -> set[str]:
    """Shared modules transitively imported by the skill's scripts and local modules."""
    frontier: set[str] = set()
    for source in _files(skill).values():
        frontier |= _imported_top_names(_source_path(skill, source)) & SHARED_MODULES
    if skill != COMMON:
        skill_dir = _src_dir(skill)
        for name in _local_skill_modules(skill):
            frontier |= _imported_top_names(skill_dir / f"{name}.py") & SHARED_MODULES
    for src_subdir, filename in EXTRA_MODULES.get(skill, []):
        frontier |= _imported_top_names(SRC_ROOT / src_subdir / filename) & SHARED_MODULES
    resolved: set[str] = set()
    while frontier:
        module = frontier.pop()
        if module in resolved:
            continue
        resolved.add(module)
        frontier |= (_imported_top_names(SHARED_SCRIPTS / f"{module}.py") & SHARED_MODULES) - resolved
    return resolved


def _dispatcher_source(sub_to_module: dict[str, str]) -> str:
    choices = "|".join(sorted(sub_to_module))
    return (
        "import runpy\n"
        "import sys\n"
        "\n"
        f"SUBCOMMANDS = {sub_to_module!r}\n"
        "\n"
        "if len(sys.argv) < 2 or sys.argv[1] not in SUBCOMMANDS:\n"
        f"    sys.stderr.write('usage: <pyz> {{{choices}}} [args...]\\n')\n"
        "    sys.exit(2)\n"
        "\n"
        "_name = sys.argv[1]\n"
        "sys.argv = [_name, *sys.argv[2:]]\n"
        "runpy.run_module(SUBCOMMANDS[_name], run_name='__main__')\n"
    )


def _write_zipapp(source: Path, target: Path) -> None:
    with target.open("wb") as pyz:
        pyz.write(b"#!/usr/bin/env python3\n")
        with zipfile.ZipFile(pyz, "w", compression=zipfile.ZIP_STORED) as archive:
            for staged_file in sorted(source.rglob("*"), key=lambda p: p.as_posix()):
                if not staged_file.is_file():
                    continue
                info = zipfile.ZipInfo(staged_file.relative_to(source).as_posix(), date_time=ZIP_TIMESTAMP)
                info.create_system = 3
                info.external_attr = 0o644 << 16
                archive.writestr(info, staged_file.read_bytes())
    target.chmod(0o755)


def build_bundle(skill: str, target: Path) -> Path:
    """Build ``skill``'s bundle at ``target`` (a .pyz path). Returns it."""
    target.parent.mkdir(parents=True, exist_ok=True)
    files = _files(skill)
    sub_to_module = {sub: _module_name(_filename(src)) for sub, src in files.items()}
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td)
        for module in sorted(needed_shared(skill)):
            if module in sub_to_module.values():
                continue  # already staged below as a subcommand (common bundle)
            shutil.copy(SHARED_SCRIPTS / f"{module}.py", stage / f"{module}.py")
        for source in files.values():
            shutil.copy(_source_path(skill, source), stage / f"{_module_name(_filename(source))}.py")
        if skill != COMMON:
            skill_dir = _src_dir(skill)
            for name in sorted(_local_skill_modules(skill)):
                shutil.copy(skill_dir / f"{name}.py", stage / f"{name}.py")
        for src_subdir, filename in EXTRA_MODULES.get(skill, []):
            shutil.copy(SRC_ROOT / src_subdir / filename, stage / filename)
        (stage / "__main__.py").write_text(_dispatcher_source(sub_to_module), encoding="utf-8")
        _write_zipapp(stage, target)
    return target


def _require_distribution(name: str, version: str) -> importlib.metadata.Distribution:
    """Require and return one exact pinned distribution vendored into Cheese."""
    try:
        distribution = importlib.metadata.distribution(name)
    except importlib.metadata.PackageNotFoundError as exc:
        raise SystemExit(f"build_pyz: {name} {version} is required") from exc
    if distribution.version != version:
        raise SystemExit(
            f"build_pyz: {name} must be exactly {version}, "
            f"found {distribution.version}"
        )
    return distribution


def _stage_distribution(
    stage: Path,
    name: str,
    distribution: importlib.metadata.Distribution,
    roots: tuple[str, ...],
) -> None:
    """Stage one distribution's pure-Python modules and license into the archive."""
    files = tuple(distribution.files or ())
    wanted = set(roots) | {f"{root}.py" for root in roots}
    sources = sorted(
        member
        for member in files
        if member.parts[0] in wanted and member.suffix == ".py"
    )
    licenses = [
        member
        for member in files
        if member.name == "LICENSE"
        and any(part.endswith(".dist-info") for part in member.parts)
    ]
    if not sources or len(licenses) != 1:
        raise SystemExit(f"build_pyz: {name} distribution is incomplete")

    for member in sources:
        target = stage / Path(*member.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(distribution.locate_file(member), target)

    license_target = stage / "licenses" / f"{name}-LICENSE.txt"
    license_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(distribution.locate_file(licenses[0]), license_target)


def build_cheese_bundle(target: Path) -> Path:
    """Build the Cheese companion with compiled contracts and vendored libraries."""
    distributions = [
        (name, _require_distribution(name, version), roots)
        for name, version, roots in VENDORED_DISTRIBUTIONS
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    registry = handoff.assemble_transition_registry(
        sorted((REPO_ROOT / "skills").glob("*/references/handoff-contract.yaml"))
    )
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td)
        for module in (
            "cli",
            "handoff",
            "paths",
            "work",
            "work_cli",
            "write_handoff_artifact",
        ):
            shutil.copy(SHARED_SCRIPTS / f"{module}.py", stage / f"{module}.py")
        for name, distribution, roots in distributions:
            _stage_distribution(stage, name, distribution, roots)
        (stage / "contract_registry.py").write_text(
            # The registry is compiled at build time and emitted as a repr
            # literal, so loading it costs no YAML parse. That repr names the
            # contract dataclasses, so the module must import them itself.
            "from handoff import PayloadSchema, PhaseContract, TransitionRegistry\n\n"
            f"REGISTRY = {registry!r}\n",
            encoding="utf-8",
        )
        (stage / "contract_registry_cli.py").write_text(
            "import sys\nfrom contract_registry import REGISTRY\n\n"
            "def main():\n"
            "    if sys.argv[1:] != ['validate']:\n"
            "        sys.stderr.write('usage: cheese.pyz contract-registry validate\\n')\n"
            "        raise SystemExit(2)\n"
            "    phases = getattr(REGISTRY, 'phases', None)\n"
            "    if not isinstance(phases, dict) or not phases:\n"
            "        raise SystemExit('invalid compiled contract registry')\n"
            "    print('contract registry valid')\n\n"
            "if __name__ == '__main__':\n    main()\n",
            encoding="utf-8",
        )
        (stage / "handoff_commit_cli.py").write_text(
            "import json\nimport sys\nfrom contract_registry import REGISTRY\nfrom write_handoff_artifact import commit_handoff\n\n"
            "def main():\n"
            "    try:\n"
            "        request = json.load(sys.stdin)\n"
            "        if not isinstance(request, dict):\n"
            "            raise ValueError('request must be a JSON object')\n"
            "        request.setdefault('contracts', REGISTRY)\n"
            "        print(json.dumps(commit_handoff(**request), default=str))\n"
            "    except (OSError, ValueError, json.JSONDecodeError) as exc:\n"
            "        print(json.dumps({'error': str(exc)}), file=sys.stderr)\n"
            "        raise SystemExit(2) from exc\n\n"
            "if __name__ == '__main__':\n    main()\n",
            encoding="utf-8",
        )
        (stage / "handoff_resolve_cli.py").write_text(
            "import json\nimport sys\nfrom pathlib import Path\n"
            "from contract_registry import REGISTRY\n"
            "from handoff import HandoffEnvelope, parse_handoff, resolve_next\n\n"
            "def main():\n"
            "    try:\n"
            "        request = json.load(sys.stdin)\n"
            "        if not isinstance(request, dict):\n"
            "            raise ValueError('request must be a JSON object')\n"
            "        if 'artifact' in request:\n"
            "            path = Path(request['artifact'])\n"
            "            envelope = parse_handoff(path.read_text(encoding='utf-8'), path)\n"
            "        else:\n"
            "            envelope = HandoffEnvelope.from_mapping(request.get('envelope'))\n"
            "        result = resolve_next(envelope, request.get('available_phases', []), REGISTRY)\n"
            "        print(json.dumps(result, sort_keys=True))\n"
            "    except (OSError, ValueError, json.JSONDecodeError) as exc:\n"
            "        print(json.dumps({'error': str(exc)}), file=sys.stderr)\n"
            "        raise SystemExit(2) from exc\n\n"
            "if __name__ == '__main__':\n    main()\n",
            encoding="utf-8",
        )
        (stage / "__main__.py").write_text(
            _dispatcher_source(
                {
                    "contract-registry": "contract_registry_cli",
                    "handoff-commit": "handoff_commit_cli",
                    "handoff-resolve": "handoff_resolve_cli",
                    "work": "work_cli",
                }
            ),
            encoding="utf-8",
        )
        _write_zipapp(stage, target)
    return target


def cached_bundle(skill: str) -> Path:
    """Build ``skill``'s bundle once per process (to a temp dir) and reuse it.
    Used by the test conftests so the suite imports from the bundled artifact."""
    if skill not in _CACHE or not _CACHE[skill].exists():
        out = Path(tempfile.mkdtemp(prefix=f"ec-pyz-{skill}-"))
        _CACHE[skill] = build_bundle(skill, out / f"{skill}.pyz")
    return _CACHE[skill]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build per-skill .pyz bundles.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Build bundles here instead of deploying into each skill's scripts/ dir.",
    )
    parser.add_argument("skills", nargs="*", help="Skills to build (default: all).")
    args = parser.parse_args(argv[1:])
    known = {*SKILLS, COMMON, CHEESE, *COMMON_CONSUMERS}
    unknown = [s for s in args.skills if s not in known]
    if unknown:
        parser.error(f"unknown skill(s): {', '.join(unknown)}; known: {', '.join(sorted(known))}")
    targets = args.skills or [*SKILLS, COMMON, CHEESE]
    real = [skill for skill in targets if skill in SKILLS]
    want_common = COMMON in targets
    want_cheese = CHEESE in targets

    if args.out_dir is not None:
        for skill in real:
            print(f"built {build_bundle(skill, args.out_dir / f'{skill}.pyz')}")
        if want_common:
            print(f"built {build_bundle(COMMON, args.out_dir / 'common.pyz')}")
        if want_cheese:
            print(f"built {build_cheese_bundle(args.out_dir / 'cheese.pyz')}")
        return 0

    for skill in real:
        print(f"deployed {build_bundle(skill, REPO_ROOT / 'skills' / skill / 'scripts' / f'{skill}.pyz')}")
    if want_cheese:
        print(
            f"deployed {build_cheese_bundle(REPO_ROOT / 'skills' / 'cheese' / 'scripts' / 'cheese.pyz')}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
