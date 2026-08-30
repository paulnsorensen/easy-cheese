"""Each skill ships a self-contained Shiv archive assembled from wheel metadata."""

from __future__ import annotations

import json
import importlib.util
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import cast

import pytest
from easy_cheese.shared import paths

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD = REPO_ROOT / "scripts" / "build_pyz.py"
SPEC_FORMAT_FIXTURES = REPO_ROOT / "tests" / "python" / "fixtures" / "spec_format"
COOK_PAYLOAD_FIXTURES = REPO_ROOT / "tests" / "python" / "fixtures" / "cook_payloads"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402
import check_bundles  # noqa: E402


pytestmark = pytest.mark.skipif(  # noqa: V107
    importlib.util.find_spec("build") is None
    or importlib.util.find_spec("pip") is None
    or (shutil.which("shiv") is None and importlib.util.find_spec("shiv") is None),
    reason="bundle integration requires requirements-build.txt",
)

SKILL_SUBCOMMANDS = {
    "melt": [
        "batch-resolve",
        "conflict-pick",
        "conflict-summary",
        "detect-squash-residue",
        "lockfile-resolve",
    ],
    "affinage": ["pr-status", "post-reply", "age-route", "review-surface"],
    "mold": ["artifact-path", "curd-count", "gate-graph", "render-html", "taste-test", "validate-spec"],
    "briesearch": ["artifact-path", "ground-check", "research-layout"],
    "plate": ["stack-tools", "validate-publication"],
    "cook": [
        "artifact-path", "age-route", "baseline", "phase-decision", "milknado", "mode", "worktree",
        "validate-decomposition", "validate-manifest", "validate-pr-plan", "manifest-update",
        "wiring-topo-sort", "pr-plan-to-branches", "curd-block",
        "normalize", "validate", "slugify", "write-handoff-artifact",
        "read-handoff-slug", "findings-cli", "gates-cli", "paths-cli",
        "handoff-cli", "render-html",
    ],
    "cure": [
        "slugify", "write-handoff-artifact", "read-handoff-slug", "findings-cli",
        "gates-cli", "paths-cli", "handoff-cli", "render-html",
    ],
    "wheypoint": ["commit", "resolve", "show", "lint"],
    "easy-cheese-setup": ["global", "local", "doctor"],
    "age": [
        "artifact-path", "html-report", "age-route", "review-surface", "severity", "slugify",
        "write-handoff-artifact", "read-handoff-slug", "findings-cli", "gates-cli", "paths-cli",
        "handoff-cli", "render-html",
    ],
    "hard-cheese": ["append-attempt", "freshness-check"],
    "pasteurize": ["debug-tag-sweep", "repro-rerun", "pasteurize-route"],
    "press": ["press-route", "press-telemetry"],
}

# Every skill that registers the durable-corpus resolver shim. One shared source
# (shared/scripts/artifact_path.py) backs them all; each must agree with
# paths.artifact_path / paths.project_corpus_root.
ARTIFACT_PATH_SKILLS = ("mold", "briesearch", "cook")

# Schema-dependent runtime bundles carry the schema wheel and its pure-Python deps.
TYPED_RUNTIME_BUNDLES = ("cook", "cure", "wheypoint")
REQUIRED_WORKFLOW_MODULES = (
    "easy_cheese_schemas/__init__.py",
    "easy_cheese_schemas/artifacts.py",
    "easy_cheese_schemas/contracts.py",
    "easy_cheese_schemas/planner.py",
    "easy_cheese_schemas/schema_runtime.py",
    "easy_cheese_schemas/workflow.py",
    "easy_cheese_schemas/_schema_catalog.py",
)


@pytest.fixture(scope="module")
def bundles(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("pyz")
    result = subprocess.run(
        [sys.executable, str(BUILD), "--out-dir", str(out)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return out


def test_default_batch_builds_every_registered_skill(tmp_path: Path) -> None:
    assert build_pyz.main(["build_pyz.py", "--out-dir", str(tmp_path)]) == 0
    expected = set(build_pyz.SKILLS)
    assert len(expected) == 13
    assert {path.stem for path in tmp_path.glob("*.pyz")} == expected
    assert {path.name for path in tmp_path.glob("*.pyz")} == {f"{skill}.pyz" for skill in expected}


def _zip_with_shiv_metadata(
    *,
    entry_point: str = "easy_cheese.commands:main",
    build_id: str | None = None,
    built_at: str = "1980-01-01 00:00:00",
    interpreter: str = "/opt/python/bin/python3",
    wrapper_import: str = "from easy_cheese import main",
    record: bytes = b"easy_cheese/demo.py,sha256=old,1\n",
) -> bytes:
    from io import BytesIO

    wrapper = f"#!{interpreter}\n{wrapper_import}\nmain()\n".encode()
    members = {
        "easy_cheese/demo.py": b"VALUE = 1\n",
        "bin/demo": wrapper,
        "easy_cheese-1.0.dist-info/RECORD": record,
    }
    if build_id is None:
        import hashlib

        digest = hashlib.sha256()
        for name in sorted(members):
            digest.update(members[name])
            digest.update(name.encode())
        build_id = digest.hexdigest()

    data = BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        for member in (
            "_bootstrap/__init__.py",
            "_bootstrap/environment.py",
            "_bootstrap/filelock.py",
            "_bootstrap/interpreter.py",
            "__main__.py",
        ):
            archive.writestr(member, b"")
        archive.writestr(
            "environment.json",
            json.dumps(
                {
                    "build_id": build_id,
                    "built_at": built_at,
                    "entry_point": entry_point,
                    "reproducible": True,
                }
            ),
        )
        archive.writestr("site-packages/bin/demo", wrapper)
        archive.writestr("site-packages/easy_cheese/demo.py", members["easy_cheese/demo.py"])
        archive.writestr(
            "site-packages/easy_cheese-1.0.dist-info/RECORD", record
        )
    return data.getvalue()


def test_bundle_manifest_catches_execution_metadata_tampering() -> None:
    baseline = check_bundles._manifest(_zip_with_shiv_metadata())  # pyright: ignore[reportPrivateUsage]
    host_variation = check_bundles._manifest(  # pyright: ignore[reportPrivateUsage]
        _zip_with_shiv_metadata(
            built_at="2026-08-26 10:00:00",
            interpreter="/usr/bin/python3",
            record=b"easy_cheese/demo.py,sha256=new,1\n",
        )
    )
    assert baseline == host_variation

    tampered = check_bundles._manifest(  # pyright: ignore[reportPrivateUsage]
        _zip_with_shiv_metadata(entry_point="evil.module:main")
    )
    assert tampered["environment.json"] != baseline["environment.json"]

    wrapper_tampered = _zip_with_shiv_metadata(
        wrapper_import="from evil import main"
    )
    assert check_bundles._manifest(wrapper_tampered)["site-packages/bin/demo"] != baseline[  # pyright: ignore[reportPrivateUsage]
        "site-packages/bin/demo"
    ]

    with pytest.raises(ValueError, match="build_id does not match"):
        _ = check_bundles._manifest(  # pyright: ignore[reportPrivateUsage]
            _zip_with_shiv_metadata(build_id="tampered")
        )


def test_bundle_manifest_preserves_wrapper_flags() -> None:
    baseline = check_bundles._manifest(  # pyright: ignore[reportPrivateUsage]
        _zip_with_shiv_metadata(interpreter="/opt/python/bin/python3 -I")
    )
    host_variation = check_bundles._manifest(  # pyright: ignore[reportPrivateUsage]
        _zip_with_shiv_metadata(interpreter="/usr/bin/env python3 -I")
    )
    assert baseline == host_variation

    flag_tampered = check_bundles._manifest(  # pyright: ignore[reportPrivateUsage]
        _zip_with_shiv_metadata(interpreter="/usr/bin/env python3 -X")
    )
    assert flag_tampered["site-packages/bin/demo"] != baseline[
        "site-packages/bin/demo"
    ]


def test_bundle_manifest_keeps_non_python_shebang_distinct() -> None:
    python = check_bundles._manifest(_zip_with_shiv_metadata())  # pyright: ignore[reportPrivateUsage]
    shell = check_bundles._manifest(  # pyright: ignore[reportPrivateUsage]
        _zip_with_shiv_metadata(interpreter="/bin/sh")
    )
    assert shell["site-packages/bin/demo"] != python["site-packages/bin/demo"]


def _run(
    pyz: Path,
    *args: str,
    extra_env: dict[str, str] | None = None,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    # Run from the bundle's own dir with PYTHONPATH stripped, so the only way an
    # import can resolve is from inside the .pyz itself.
    env = dict(os.environ)
    _ = env.pop("PYTHONPATH", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(pyz), *args],
        cwd=str(pyz.parent),
        capture_output=True,
        text=True,
        env=env,
        input=stdin,
    )


def _bundle_members(pyz: Path) -> set[str]:
    with zipfile.ZipFile(pyz) as archive:
        return {
            name.removeprefix("site-packages/")
            for name in archive.namelist()
            if name.startswith("site-packages/") and not name.startswith("site-packages/bin/")
        }


def _extract_site_packages(pyz: Path, root: Path) -> Path:
    package_root = root / "site-packages"
    with zipfile.ZipFile(pyz) as archive:
        for name in archive.namelist():
            if not name.startswith("site-packages/") or name.startswith("site-packages/bin/"):
                continue
            relative = Path(name.removeprefix("site-packages/"))
            target = package_root / relative
            if name.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                _ = target.write_bytes(archive.read(name))
    return package_root


@pytest.mark.parametrize(
    "skill,sub",
    [(skill, sub) for skill, subs in SKILL_SUBCOMMANDS.items() for sub in subs],
)
def test_subcommand_resolves_inside_bundle(bundles: Path, skill: str, sub: str) -> None:
    result = _run(bundles / f"{skill}.pyz", sub, "--help")
    combined = result.stdout + result.stderr
    assert "ModuleNotFoundError" not in combined, combined
    assert "Traceback" not in combined, combined
    # A deleted subcommand falls through to the dispatcher's own unknown-subcommand
    # fallback ("usage: <pyz> {other-subs}"), which never names the deleted sub. A
    # real subcommand always dispatches into its own code -- whether it then exits 0
    # on --help (most) or errors on "--help" as a bogus positional argument
    # (validate_manifest/validate_pr_plan/validate_decomposition, which take a bare
    # manifest path and never print their own name) is immaterial: either way it never
    # produces the dispatcher's exact fallback string. This is the precise negation of
    # the deleted-subcommand failure mode, verified by a watched-it-fail cycle.
    dispatcher_fallback = combined.strip().startswith("usage: <pyz>")
    assert not dispatcher_fallback, combined




@pytest.mark.parametrize(
    ("skill", "canonical", "legacy"),
    [
        ("age", "write-handoff-artifact", "write_handoff_artifact"),
        ("cook", "read-handoff-slug", "read_handoff_slug"),
        ("cure", "findings-cli", "findings_cli"),
        ("mold", "render-html", "render_html"),
    ],
)
def test_kebab_commands_and_legacy_aliases_dispatch_from_committed_bundles(
    bundles: Path, skill: str, canonical: str, legacy: str
) -> None:
    for name in (canonical, legacy):
        result = _run(bundles / f"{skill}.pyz", name, "--help")
        combined = result.stdout + result.stderr
        assert "ModuleNotFoundError" not in combined, combined
        assert "Traceback" not in combined, combined
        assert not combined.strip().startswith("usage: <pyz>"), combined
@pytest.mark.parametrize("skill", list(SKILL_SUBCOMMANDS))
def test_unknown_subcommand_is_rejected(bundles: Path, skill: str) -> None:
    result = _run(bundles / f"{skill}.pyz", "no-such-subcommand")
    assert result.returncode == 2
    assert "usage" in result.stderr.lower()


def test_melt_subcommand_executes_with_forwarded_args(
    bundles: Path, tmp_path: Path
) -> None:
    """A real subcommand runs end-to-end through the bundle: proves argv forwarding,
    the shared git_utils import resolving, and correct routing."""
    conflict = tmp_path / "f.txt"
    _ = conflict.write_text(
        "before\n<<<<<<< HEAD\nOURS_LINE\n=======\nTHEIRS_LINE\n>>>>>>> branch\nafter\n"
    )
    result = _run(
        bundles / "melt.pyz", "conflict-pick", str(conflict), "--theirs", "--dry-run"
    )
    assert result.returncode == 0, result.stderr
    assert "THEIRS_LINE" in result.stdout
    assert "OURS_LINE" not in result.stdout
    assert "<<<<<<<" not in result.stdout




def test_plate_bundle_validates_publication_without_source_imports(
    bundles: Path, tmp_path: Path
) -> None:
    state = {
        "mode": "commit-only",
        "topology": "n/a",
        "provider": "n/a",
        "artifacts": [],
        "gate": {"command": "just check", "result": "pass"},
        "commits": ["0022ccafb9568b5ddf04f6d3b86592885184427a"],
        "prs": [],
        "risk": "none",
    }
    path = tmp_path / "publication.json"
    _ = path.write_text(json.dumps(state))

    result = _run(bundles / "plate.pyz", "validate-publication", str(path))

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["valid"] is True


def test_plate_bundle_reports_stack_tools_without_source_imports(
    bundles: Path, tmp_path: Path
) -> None:
    result = _run(bundles / "plate.pyz", "stack-tools", "--cwd", str(tmp_path))

    assert result.returncode == 0, result.stderr
    report = cast(dict[str, object], json.loads(result.stdout))
    assert set(cast(list[object], report["providers"])) == {"graphite", "git-town", "gh-stack"}


def test_bundle_carries_only_its_own_skill_package(bundles: Path) -> None:
    """Internal wheel metadata includes shared code without other skill apps."""
    melt = _bundle_members(bundles / "melt.pyz")
    assert "easy_cheese/skills/melt/conflict_pick.py" in melt
    assert "easy_cheese/shared/git_utils.py" in melt
    assert not any(name.startswith("easy_cheese/skills/affinage/") for name in melt)
    assert not any(name.startswith("easy_cheese/skills/ultracook/") for name in melt)

    affinage = _bundle_members(bundles / "affinage.pyz")
    assert "easy_cheese/skills/affinage/pr_status.py" in affinage
    assert "easy_cheese/shared/fanout/age_route.py" in affinage
    assert not any(name.startswith("easy_cheese/skills/melt/") for name in affinage)


def test_briesearch_bundle_uses_internal_distributions(bundles: Path) -> None:
    content = {
        name for name in _bundle_members(bundles / "briesearch.pyz")
        if ".dist-info/" not in name
    }
    assert "easy_cheese/skills/briesearch/commands.py" in content
    assert "easy_cheese/shared/bundle_commands.py" in content
    assert "easy_cheese_schemas/__init__.py" in content
    assert not any(name.startswith("easy_cheese/skills/mold/") for name in content)




def test_press_bundle_emits_a_telemetry_record(bundles: Path) -> None:
    request = json.dumps(
        {
            "slug": "outer-tdd-gates",
            "attempt": 2,
            "outcome": "green",
            "repair_cycles": 1,
            "tool_errors": [
                {"phase": "attack", "operation": "pytest"},
                {"phase": "attack", "operation": "pytest"},
            ],
            "delegations": [{"role": "reviewer", "purpose": "replay the digest"}],
            "changed_files": ["tests/test_widget.py", "src/widget.py"],
        }
    )

    result = _run(bundles / "press.pyz", "press-telemetry", stdin=request)

    assert result.returncode == 0, result.stderr
    record = cast(dict[str, object], json.loads(result.stdout))
    assert record["operations"] == [
        {"phase": "attack", "operation": "pytest", "errors": 2, "recurring": True}
    ]
    assert record["production_source_files"] == ["src/widget.py"]
    assert record["boundary_consistent"] is False


def test_press_bundle_loads_router_and_rejects_receipt_keys(bundles: Path) -> None:
    result = _run(
        bundles / "press.pyz",
        "press-route",
        stdin='{"outcome": "green", "current_receipt": "press.json"}',
    )

    assert result.returncode == 1
    assert (
        result.stderr.strip()
        == "ERROR: request must contain exactly outcome and repair_cycles"
    )


def test_cook_baseline_classifies_failures_via_stdin(bundles: Path) -> None:
    payload = (
        '{"baseline": [], "current": '
        '[{"suite": "s", "test_id": "t", "signature": "x"}]}'
    )
    result = _run(bundles / "cook.pyz", "baseline", stdin=payload)
    assert result.returncode == 0, result.stderr
    classification = cast(dict[str, object], json.loads(result.stdout))
    assert classification["new"] == [{"suite": "s", "test_id": "t", "signature": "x"}]
    assert classification["identical"] == []
    assert classification["changed"] == []
    assert classification["resolved"] == []


def test_cook_baseline_rejects_malformed_stdin(bundles: Path) -> None:
    result = _run(bundles / "cook.pyz", "baseline", stdin="not json")
    assert result.returncode == 2, result.stderr
    assert result.stderr.startswith("ERROR:")


def test_cook_baseline_rejects_wrong_typed_value(bundles: Path) -> None:
    result = _run(bundles / "cook.pyz", "baseline", stdin='{"baseline": [], "current": {}}')
    assert result.returncode == 2, result.stderr
    assert result.stderr.startswith("ERROR:")


# Pinned env so the resolved corpus path is deterministic and does not depend on
# the test host's git remote or real XDG dirs.
_CORPUS_ENV = {
    "EASY_CHEESE_HOME": "/tmp/ec-corpus",
    "EASY_CHEESE_PROJECT": "demo-project",
}


@pytest.mark.parametrize("skill", ARTIFACT_PATH_SKILLS)
def test_artifact_path_specs_matches_paths_module(bundles: Path, skill: str) -> None:
    """The shim's specs path equals paths.artifact_path under the same env — the
    single-source guarantee. If paths.py changes the path math, this fails."""
    # paths.project_corpus_root reads the env at call time; pin it to match the bundle.
    old = {k: os.environ.get(k) for k in _CORPUS_ENV}
    try:
        os.environ.update(_CORPUS_ENV)
        expected = str(paths.artifact_path("specs", "demo-slug"))
    finally:
        for k, v in old.items():
            if v is None:
                _ = os.environ.pop(k, None)
            else:
                os.environ[k] = v
    result = _run(
        bundles / f"{skill}.pyz",
        "artifact-path",
        "specs",
        "demo-slug",
        extra_env=_CORPUS_ENV,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


def test_artifact_path_research_returns_corpus_root(bundles: Path) -> None:
    """research resolves to the bare project corpus root; briesearch composes the
    nested research/<slug>/<slug>.md layout on top of it."""
    result = _run(
        bundles / "briesearch.pyz",
        "artifact-path",
        "research",
        "demo-slug",
        extra_env=_CORPUS_ENV,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "/tmp/ec-corpus/demo-project"


def test_artifact_path_research_returns_root_and_ignores_slug(bundles: Path) -> None:
    """research returns the bare corpus root and does NOT validate or embed the slug:
    paths.artifact_path deliberately does not own the nested research/<slug>/<slug>.md
    layout, so the shim hands briesearch the root and lets it compose + validate the
    slug itself. This pins that contract — if the shim ever starts validating or
    appending the slug for research, that change must be deliberate, not silent."""
    # A slug that validate_slug would reject is accepted on the research path because
    # the shim never validates it; the output is the same bare root either way.
    bad = _run(
        bundles / "briesearch.pyz",
        "artifact-path",
        "research",
        "Bad_Slug",
        extra_env=_CORPUS_ENV,
    )
    assert bad.returncode == 0, bad.stderr
    assert bad.stdout.strip() == "/tmp/ec-corpus/demo-project"
    # The slug is not appended to the path for research (contrast with specs).
    assert "Bad_Slug" not in bad.stdout
    other = _run(
        bundles / "briesearch.pyz",
        "artifact-path",
        "research",
        "totally-different-slug",
        extra_env=_CORPUS_ENV,
    )
    assert other.stdout.strip() == bad.stdout.strip()


def test_artifact_path_rejects_bad_slug(bundles: Path) -> None:
    result = _run(
        bundles / "mold.pyz",
        "artifact-path",
        "specs",
        "Bad_Slug",
        extra_env=_CORPUS_ENV,
    )
    assert result.returncode == 1
    assert "kebab-case" in result.stderr


def test_artifact_path_rejects_unknown_phase(bundles: Path) -> None:
    result = _run(
        bundles / "mold.pyz",
        "artifact-path",
        "nonsense",
        "demo-slug",
        extra_env=_CORPUS_ENV,
    )
    assert result.returncode == 1
    assert "unknown phase" in result.stderr


def test_research_layout_prints_slug_aware_paths(bundles: Path) -> None:
    """`artifact-path research <slug>` returns only the corpus root, so every caller
    re-derived `research/<slug>/…` by hand (#492). research-layout returns the whole
    nested layout as JSON, anchored at the same corpus root."""
    result = _run(
        bundles / "briesearch.pyz",
        "research-layout",
        "demo-slug",
        extra_env=_CORPUS_ENV,
    )
    assert result.returncode == 0, result.stderr
    layout = cast("dict[str, str]", json.loads(result.stdout))
    root = f"{_CORPUS_ENV['EASY_CHEESE_HOME']}/{_CORPUS_ENV['EASY_CHEESE_PROJECT']}"
    assert layout == {
        "slug": "demo-slug",
        "corpus_root": root,
        "dir": f"{root}/research/demo-slug",
        "report": f"{root}/research/demo-slug/demo-slug.md",
        "raw_dir": f"{root}/research/demo-slug/raw",
        "manifest": f"{root}/research/demo-slug/manifest.json",
    }


def test_research_layout_rejects_invalid_slug(bundles: Path) -> None:
    result = _run(
        bundles / "briesearch.pyz",
        "research-layout",
        "Not A Slug",
        extra_env=_CORPUS_ENV,
    )
    assert result.returncode == 1
    assert "kebab-case" in result.stderr


def test_artifact_path_research_root_unchanged_by_layout_command(
    bundles: Path,
) -> None:
    """#492 required research-layout to be additive: `artifact-path research <slug>`
    still prints the bare corpus root every existing caller substitutes into
    "$ROOT/research/<slug>/"."""
    result = _run(
        bundles / "briesearch.pyz",
        "artifact-path",
        "research",
        "demo-slug",
        extra_env=_CORPUS_ENV,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        f"{_CORPUS_ENV['EASY_CHEESE_HOME']}/{_CORPUS_ENV['EASY_CHEESE_PROJECT']}"
    )


# briesearch ground-check: the mechanical grounding gate behind issue #113. The
# original failure was a synthesis that concluded "Codex has no static config
# permission surface" with no citation, contradicting a fact its own raw notes
# recorded. These pin that an un-grounded claim can no longer pass silently.
_GROUNDED_REPORT = """## Research: q

### Evidence

| Claim | Evidence | Source type | Freshness | Confidence | Caveat |
| --- | --- | --- | --- | --- | --- |
| Codex exposes a granular approval_policy permission surface | ref.md:25 | vendor docs | 2026-06-01 | certain | |
| No broader sandbox knob was found in the config reference searched | [^s1] | vendor docs | 2026-06-01 | speculating | only config.toml checked |

## References
[^s1]: https://example.com/codex (fetched 2026-06-01).
"""


def _write(tmp_path: Path, body: str) -> Path:
    report = tmp_path / "report.md"
    _ = report.write_text(body)
    return report


def test_ground_check_fails_uncited_claim(bundles: Path, tmp_path: Path) -> None:
    """The exact #113 failure: an absence claim with no citation. Ask 1 says every
    claim must carry a verifiable citation — this must be a hard, non-zero exit so
    the un-grounded claim cannot survive into the artifact."""
    body = _GROUNDED_REPORT.replace("ref.md:25", "(synthesized from the docs)")
    report = _write(tmp_path, body)
    result = _run(bundles / "briesearch.pyz", "ground-check", str(report))
    assert result.returncode == 1, result.stderr
    assert "CITATION" in result.stderr
    assert "granular approval_policy" in result.stderr


def test_ground_check_passes_grounded_report(bundles: Path, tmp_path: Path) -> None:
    """A fully-cited report whose only absence claim is hedged (speculating +
    'searched') is clean — the gate enforces grounding, it does not forbid
    well-grounded negatives."""
    result = _run(
        bundles / "briesearch.pyz",
        "ground-check",
        str(_write(tmp_path, _GROUNDED_REPORT)),
    )
    assert result.returncode == 0, result.stderr
    assert "grounding ok" in result.stderr


def test_ground_check_rejects_nonlabel_confidence(
    bundles: Path, tmp_path: Path
) -> None:
    """Confidence must be one of the three exact labels. A synonym like 'high' is a
    silent confidence drift the cap rules can't reason about — fail it."""
    body = _GROUNDED_REPORT.replace("| certain |", "| high |")
    result = _run(
        bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body))
    )
    assert result.returncode == 1, result.stderr
    assert "CONFIDENCE" in result.stderr


def test_ground_check_absence_advisory_does_not_fail(
    bundles: Path, tmp_path: Path
) -> None:
    """A cited, certain absence claim with no ruling-out phrase is surfaced as an
    ADVISORY (feeds the synthesis-fidelity self-check) but does NOT fail the gate:
    observed-vs-inferred absence is not decidable from text, so it is flagged for
    judgement, not auto-rejected. Pins that the advisory stays soft."""
    body = _GROUNDED_REPORT.replace(
        "| No broader sandbox knob was found in the config reference searched | [^s1] | vendor docs | 2026-06-01 | speculating | only config.toml checked |",
        "| Codex does not expose a global sandbox knob | [^s1] | vendor docs | 2026-06-01 | certain | |",
    )
    result = _run(
        bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body))
    )
    assert result.returncode == 0, result.stderr
    assert "ADVISORY" in result.stderr
    assert "ABSENCE" in result.stderr


def test_ground_check_no_table_is_error(bundles: Path, tmp_path: Path) -> None:
    """A synthesis with prose claims but no evidence table grounds nothing — that is
    itself a grounding failure, not a pass-by-default."""
    report = _write(tmp_path, "## Research: q\n\nCodex has no permission surface.\n")
    result = _run(bundles / "briesearch.pyz", "ground-check", str(report))
    assert result.returncode == 1, result.stderr
    assert "no evidence table" in result.stderr


def test_ground_check_accepts_nonlocal_and_existing_local_citations(
    bundles: Path, tmp_path: Path
) -> None:
    """URLs and inline paths need no lookup; local paths use their defined roots."""
    raw = tmp_path / "raw"
    raw.mkdir()
    _ = (raw / "01-example.md").write_text("one\ntwo\nthree\nfour\n")
    cheese = bundles / ".cheese"
    cheese.mkdir()
    _ = (cheese / "notes.md").write_text("one\ntwo\n")
    body = (
        "## Research: q\n\n### Evidence\n\n"
        "| Claim | Evidence | Confidence |\n| --- | --- | --- |\n"
        "| A holds | https://example.com/a | certain |\n"
        "| B holds | source.py:12 | certain |\n"
        "| C holds | `<raw/01-example.md#L3-4>.` | certain |\n"
        "| D holds | `<.cheese/notes.md#L1-2>.` | certain |\n"
    )
    result = _run(
        bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body))
    )
    assert result.returncode == 0, result.stderr
    assert "grounding ok" in result.stderr


def test_ground_check_scans_every_table(bundles: Path, tmp_path: Path) -> None:
    """A deep report has several tables (per-finding tables + the Evidence table). The
    gate must check every one — an un-cited claim in the *second* table must still fail.
    Locks against a regression that stops after the first table and skips later claims."""
    body = (
        "## Research: q\n\n### Findings\n\n"
        "| Claim | Evidence | Confidence |\n| --- | --- | --- |\n"
        "| X holds | [^s1] | certain |\n\n"
        "### Evidence\n\n"
        "| Claim | Evidence | Confidence |\n| --- | --- | --- |\n"
        "| Y holds | naming a source in prose | certain |\n\n"
        "## References\n[^s1]: https://example.com (fetched 2026-06-01).\n"
    )
    result = _run(
        bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body))
    )
    assert result.returncode == 1, result.stderr
    assert "CITATION" in result.stderr
    assert "Y holds" in result.stderr
    assert "2 table(s)" in result.stderr


def test_ground_check_reads_source_column_in_three_col_table(
    bundles: Path, tmp_path: Path
) -> None:
    """The real deep-report artifact uses | Claim | Source | Confidence |. The gate must
    map the Source column as the evidence column: a claim whose Claim cell has no
    citation but whose Source cell does must PASS. Locks the Source≡Evidence mapping —
    if a regression stopped recognising 'Source', evidence would fall back to the Claim
    cell and this grounded row would wrongly fail."""
    body = (
        "## Research: q\n\n### Evidence\n\n"
        "| Claim | Source | Confidence |\n| --- | --- | --- |\n"
        "| Z holds | https://example.com/z | certain |\n"
    )
    result = _run(
        bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body))
    )
    assert result.returncode == 0, result.stderr


def test_ground_check_absence_guard_flags_inferred_absence_without_false_positive(
    bundles: Path, tmp_path: Path
) -> None:
    """The absence advisory must not fire on a positive claim containing a negation
    substring mid-word ('another'), but it must still flag a certain absence inferred
    from a searched-but-empty source. 'Not found in ... searched' is the downgraded
    claim shape from synthesis.md, not proof that earns `certain`."""
    body = (
        "## Research: q\n\n### Evidence\n\n"
        "| Claim | Evidence | Confidence |\n| --- | --- | --- |\n"
        "| Cargo exposes another download feature | [^s1] | certain |\n"
        "| The knob was not found in the two references searched | [^s1] | certain |\n\n"
        "## References\n[^s1]: https://example.com (fetched 2026-06-01).\n"
    )
    result = _run(
        bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body))
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr.count("ADVISORY") == 1


def test_ground_check_rejects_numeric_ratio_as_citation(
    bundles: Path, tmp_path: Path
) -> None:
    """The inline path:line citation marker must require a real, alpha-led file
    extension. A numeric ratio/timestamp/verse ('4.5:1', '3.30:15') is <word>.<digit>:<digit>
    shaped and would satisfy a loose `\\.\\w+:\\d+` matcher, letting an un-cited prose
    evidence cell pass exit 0 — the exact #113 failure shape (prose, no citation). Pins
    that such a cell fails CITATION so the core grounding guarantee can't be bypassed."""
    body = (
        "## Research: q\n\n### Evidence\n\n"
        "| Claim | Evidence | Confidence |\n| --- | --- | --- |\n"
        "| WCAG AA needs a 4.5:1 contrast ratio | the 4.5:1 ratio is recommended | certain |\n"
    )
    result = _run(
        bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body))
    )
    assert result.returncode == 1, result.stderr
    assert "CITATION" in result.stderr
    assert "contrast ratio" in result.stderr


def test_ground_check_flags_short_row_as_malformed(
    bundles: Path, tmp_path: Path
) -> None:
    """A data row with fewer cells than the header's column count can't be graded —
    the evidence/confidence cells it claims to have are missing. The gate must fail it
    as MALFORMED rather than index past the row's end or skip it silently, so a
    truncated table is a loud error, not a coverage hole."""
    body = (
        "## Research: q\n\n### Evidence\n\n"
        "| Claim | Evidence | Confidence |\n| --- | --- | --- |\n"
        "| A holds | [^s1] |\n\n"
        "## References\n[^s1]: https://example.com (fetched 2026-06-01).\n"
    )
    result = _run(
        bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body))
    )
    assert result.returncode == 1, result.stderr
    assert "MALFORMED" in result.stderr


def test_ground_check_rejects_unresolved_footnote(
    bundles: Path, tmp_path: Path
) -> None:
    body = _GROUNDED_REPORT.replace("[^s1]", "[^missing]").replace(
        "[^missing]: https://example.com/codex (fetched 2026-06-01).",
        "[^s1]: https://example.com/codex (fetched 2026-06-01).",
    )
    result = _run(
        bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body))
    )
    assert result.returncode == 1, result.stderr
    assert "FOOTNOTE" in result.stderr
    assert "missing" in result.stderr


def test_ground_check_rejects_footnote_definition_without_citation(
    bundles: Path, tmp_path: Path
) -> None:
    body = _GROUNDED_REPORT.replace(
        "https://example.com/codex (fetched 2026-06-01).",
        "vendor documentation",
    )
    result = _run(
        bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body))
    )
    assert result.returncode == 1, result.stderr
    assert "FOOTNOTE" in result.stderr
    assert "no verifiable citation" in result.stderr


def test_ground_check_accepts_citation_on_footnote_continuation_line(
    bundles: Path, tmp_path: Path
) -> None:
    body = _GROUNDED_REPORT.replace(
        "[^s1]: https://example.com/codex (fetched 2026-06-01).",
        "[^s1]: Vendor documentation\n    https://example.com/codex",
    )
    result = _run(
        bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body))
    )
    assert result.returncode == 0, result.stderr


def test_ground_check_rejects_duplicate_footnote_labels(
    bundles: Path, tmp_path: Path
) -> None:
    body = _GROUNDED_REPORT + "[^s1]: https://example.com/duplicate\n"
    result = _run(
        bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body))
    )
    assert result.returncode == 1, result.stderr
    assert "FOOTNOTE" in result.stderr
    assert "duplicate definition" in result.stderr


@pytest.mark.parametrize(
    "evidence,references",
    [
        ("raw/01-missing.md#L3-8", ""),
        ("[^s1]", "## References\n[^s1]: raw/01-missing.md#L3-8\n"),
    ],
)
def test_ground_check_rejects_missing_report_local_raw_path(
    bundles: Path, tmp_path: Path, evidence: str, references: str
) -> None:
    body = (
        "## Research: q\n\n### Evidence\n\n"
        "| Claim | Evidence | Confidence |\n| --- | --- | --- |\n"
        f"| A holds | {evidence} | certain |\n\n"
        f"{references}"
    )
    result = _run(
        bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body))
    )
    assert result.returncode == 1, result.stderr
    assert "LOCAL_PATH" in result.stderr
    assert "raw/01-missing.md" in result.stderr


@pytest.mark.parametrize("anchor", ["#L3-8", "#L4-3", "#L0"])
def test_ground_check_rejects_invalid_local_line_anchor(
    bundles: Path, tmp_path: Path, anchor: str
) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    _ = (raw / "source.md").write_text("one\ntwo\nthree\nfour\n")
    body = (
        "## Research: q\n\n### Evidence\n\n"
        "| Claim | Evidence | Confidence |\n| --- | --- | --- |\n"
        f"| A holds | raw/source.md{anchor} | certain |\n"
    )
    result = _run(
        bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body))
    )
    assert result.returncode == 1, result.stderr
    assert "LOCAL_PATH" in result.stderr
    assert "line anchor" in result.stderr


def test_ground_check_rejects_local_path_traversal(
    bundles: Path, tmp_path: Path
) -> None:
    _ = (tmp_path / "raw-secret.md").write_text("outside raw\n")
    _ = (bundles / "cheese-secret.md").write_text("outside cheese\n")
    (bundles / ".cheese").mkdir(exist_ok=True)
    body = (
        "## Research: q\n\n### Evidence\n\n"
        "| Claim | Evidence | Confidence |\n| --- | --- | --- |\n"
        "| A holds | raw/../raw-secret.md#L1 | certain |\n"
        "| B holds | .cheese/../cheese-secret.md#L1 | certain |\n"
    )
    result = _run(
        bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body))
    )
    assert result.returncode == 1, result.stderr
    assert result.stderr.count("outside allowed root") == 2


def test_bundle_build_is_byte_deterministic(tmp_path: Path) -> None:
    """The PR freshness check compares raw .pyz bytes after rebuilding, so two
    builds of identical source must produce byte-identical archives."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    for out in (first, second):
        result = subprocess.run(
            [sys.executable, str(BUILD), "--out-dir", str(out)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    for skill in SKILL_SUBCOMMANDS:
        assert (first / f"{skill}.pyz").read_bytes() == (
            second / f"{skill}.pyz"
        ).read_bytes()


def test_skill_bundles_each_ship_shared_slugify(bundles: Path) -> None:
    for skill in ("cook", "age", "cure"): 
        result = _run(
            bundles / f"{skill}.pyz",
            "slugify",
            "from-task",
            "--task",
            "Fix the off-by-one error",
            "--json",
        )
        assert result.returncode == 0, f"{skill}: {result.stderr}"
        assert json.loads(result.stdout)["slug"] == "fix-off-by-one-error"


def test_schema_wheel_is_staged_in_each_schema_dependent_bundle(bundles: Path) -> None:
    expected = (REPO_ROOT / "src" / "easy_cheese_schemas" / "_schema_catalog.py").read_bytes()
    for skill in TYPED_RUNTIME_BUNDLES:
        with zipfile.ZipFile(bundles / f"{skill}.pyz") as archive:
            assert archive.read("site-packages/easy_cheese_schemas/_schema_catalog.py") == expected





@pytest.mark.parametrize("skill", TYPED_RUNTIME_BUNDLES)
def test_typed_runtime_modules_are_shipped_without_compiler(
    bundles: Path, skill: str
) -> None:
    content = _bundle_members(bundles / f"{skill}.pyz")
    missing = sorted(set(REQUIRED_WORKFLOW_MODULES) - content)
    assert not missing, f"{skill}.pyz missing canonical runtime modules: {missing}"
    assert not any(
        name.rsplit("/", 1)[-1] == "_phase_registry_compiler.py" for name in content
    ), f"{skill}.pyz must not ship the source-only phase compiler"


@pytest.mark.parametrize("skill", sorted(SKILL_SUBCOMMANDS))
def test_no_runtime_bundle_ships_phase_registry_compiler(
    bundles: Path, skill: str
) -> None:
    content = _bundle_members(bundles / f"{skill}.pyz")
    assert not any(
        name.rsplit("/", 1)[-1] == "_phase_registry_compiler.py" for name in content
    ), f"{skill}.pyz leaked the source-only phase compiler"
    assert not any(
        name.rsplit("/", 1)[-1] == "_schema_catalog_compiler.py" for name in content
    ), f"{skill}.pyz leaked the schema catalog compiler"


@pytest.mark.parametrize("skill", ("cook", "cure"))
def test_cook_and_cure_installed_paths_expose_canonical_workflow_api(
    bundles: Path, tmp_path: Path, skill: str
) -> None:
    """Import the shipped packages, not the repository source tree.

    Both bundles must expose the same canonical planner/Cook/Cure seam and its
    typed boundary helpers.
    """
    package_root = _extract_site_packages(bundles / f"{skill}.pyz", tmp_path / skill)
    code = (
        "import sys;"
        "sys.path[:0] = sys.argv[1:];"
        "import easy_cheese_schemas as schemas;"
        "from easy_cheese_schemas import "
        "CurdPlan, CurdResult, DiagnosisResult, PlannerResult, "
        "bind_diagnosis, cook, cure, materialize_planner_result, "
        "normalize_agent_output, resolve_artifact, run_workflow, "
        "schema_bytes, validate_curd_plan;"
        "assert all(callable(item) for item in ("
        "bind_diagnosis, cook, cure, materialize_planner_result, "
        "normalize_agent_output, resolve_artifact, run_workflow, "
        "validate_curd_plan));"
        "assert schema_bytes(CurdPlan);"
        "assert schemas.supported_version_for(PlannerResult) is not None;"
        "assert CurdResult.__name__ == 'CurdResult';"
        "assert DiagnosisResult.__name__ == 'DiagnosisResult';"
        "print('ok')"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            code,
            str(package_root),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == "ok\n"


def test_unknown_skill_name_still_errors() -> None:
    """build_pyz.py must exit non-zero for truly unknown skill names."""
    result = subprocess.run(
        [sys.executable, str(BUILD), "--out-dir", "/tmp", "no-such-skill"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "no-such-skill" in result.stderr


def _bundle_content(pyz: Path) -> dict[str, bytes]:
    """Return source payload members, excluding Shiv-generated host metadata."""
    with zipfile.ZipFile(pyz) as archive:
        return {
            name: archive.read(name)
            for name in archive.namelist()
            if name != "environment.json"
            and not name.startswith("site-packages/bin/")
            and not name.endswith(".dist-info/RECORD")
        }


@pytest.mark.parametrize("skill", sorted(SKILL_SUBCOMMANDS))
def test_committed_bundle_matches_source(bundles: Path, skill: str) -> None:
    """Every committed skills/<skill>/scripts/<skill>.pyz must carry the same
    source payload members as a fresh build of the current source.

    Shiv generates the bootstrap, environment metadata, console-script wrappers,
    and RECORD entries from the host interpreter. Those members are excluded;
    source and wheel metadata remain the staleness signal worth gating: a source
    edit that never made it into the committed bundle shows up as changed, added,
    or removed members here.

    Byte determinism is still asserted separately: two builds of one source tree
    on one host must agree
    (test_build_pyz_tree_staging.py::test_bundle_build_is_byte_deterministic)."""
    committed = REPO_ROOT / "skills" / skill / "scripts" / f"{skill}.pyz"
    fresh = bundles / f"{skill}.pyz"
    assert committed.exists(), f"committed bundle missing: {committed}"

    have = _bundle_content(committed)
    want = _bundle_content(fresh)
    added = sorted(set(want) - set(have))
    removed = sorted(set(have) - set(want))
    changed = sorted(n for n in set(have) & set(want) if have[n] != want[n])
    if not (added or removed or changed):
        return
    raise AssertionError(
        f"committed {skill}.pyz is stale vs its source "
        + f"(changed={changed}, added={added}, removed={removed}). "
        + "Rebuild and commit it: python3 scripts/build_pyz.py"
    )


def test_no_orphan_committed_bundles():
    """A skill dropped from both build registries must not leave a stale committed
    .pyz behind—the build workflow only diffs bundles it rebuilds, so an orphan
    would ship silently. Every registered skill owns its same-named archive."""
    committed = {
        p.relative_to(REPO_ROOT).as_posix()
        for p in REPO_ROOT.glob("skills/*/scripts/*.pyz")
    }
    expected = {f"skills/{skill}/scripts/{skill}.pyz" for skill in build_pyz.SKILLS}
    assert committed == expected


def test_application_metadata_declares_shared_internal_dependency(bundles: Path) -> None:
    with zipfile.ZipFile(bundles / "briesearch.pyz") as archive:
        metadata_name = next(
            name
            for name in archive.namelist()
            if "easy_cheese_briesearch-" in name and name.endswith(".dist-info/METADATA")
        )
        metadata = archive.read(metadata_name).decode()
    assert f"Requires-Dist: easy-cheese-shared=={build_pyz.VERSION}" in metadata


def test_age_bundle_exposes_html_report_help(bundles: Path) -> None:
    """age.pyz should expose the new html-report subcommand and its CLI surface."""
    age_pyz = bundles / "age.pyz"
    assert age_pyz.exists(), f"age bundle missing: {age_pyz}"

    result = _run(age_pyz, "html-report", "--help")
    assert result.returncode == 0, result.stderr
    help_text = result.stdout + result.stderr
    assert "--report" in help_text
    assert "--slug" in help_text
    assert "--out-dir" in help_text


def test_age_bundle_html_report_runs_from_inside_bundle(
    bundles: Path, tmp_path: Path
) -> None:
    """Smoke-run html-report end-to-end so a module-name collision (the age
    entrypoint shadowing the shared html_report renderer) can't hide behind a
    --help-only check that never reaches render_document."""
    age_pyz = bundles / "age.pyz"
    assert age_pyz.exists(), f"age bundle missing: {age_pyz}"

    report = tmp_path / "rep.md"
    _ = report.write_text(
        "# Age report — demo\n\n## Blocker\n"
        + "- **[security:blocker]** `a.py:1` — token parsed without validation.\n\n"
        + "## Confidence\ncertain\n",
        encoding="utf-8",
    )
    result = _run(
        age_pyz,
        "html-report",
        "--report",
        str(report),
        "--slug",
        "demo",
        "--out-dir",
        str(tmp_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    out_html = tmp_path / "age-demo.html"
    assert out_html.is_file(), f"expected {out_html}; stdout={result.stdout!r}"
    html = out_html.read_text(encoding="utf-8")
    assert "token parsed without validation" in html
    assert "Blocker" in html


def test_age_bundle_carries_html_report_and_findings_imports(bundles: Path) -> None:
    """The bundle must stage the report generator plus its shared parser helper."""
    age_pyz = bundles / "age.pyz"
    assert age_pyz.exists(), f"age bundle missing: {age_pyz}"

    content = _bundle_members(age_pyz)
    assert "easy_cheese/skills/age/age_html_report.py" in content
    assert "easy_cheese/shared/findings.py" in content


def test_document_rules_projection_matches_checked_in_source() -> None:
    generated = REPO_ROOT / "src" / "easy_cheese" / "shared" / "document_rules.py"
    assert build_pyz._compiled_document_rules_source() == generated.read_text(encoding="utf-8")  # pyright: ignore[reportPrivateUsage]


def test_skill_archives_own_shared_commands_and_no_common_archive(bundles: Path) -> None:
    for skill in ("cook", "age", "cure"):
        assert "easy_cheese/shared/slugify.py" in _bundle_members(bundles / f"{skill}.pyz")
    assert not any(REPO_ROOT.glob("skills/*/scripts/common.pyz"))


def test_mold_pyz_dispatches_validate_spec_end_to_end() -> None:
    mold_pyz = build_pyz.cached_bundle("mold")
    result = _run(mold_pyz, "validate-spec", str(SPEC_FORMAT_FIXTURES / "valid_spec.md"))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ERROR:" not in result.stderr


def test_cook_pyz_dispatches_normalize_end_to_end() -> None:
    cook_pyz = build_pyz.cached_bundle("cook")
    rejected = _run(
        cook_pyz,
        "normalize",
        str(COOK_PAYLOAD_FIXTURES / "host_owned_writer_view.json"),
        "--invocation",
        str(COOK_PAYLOAD_FIXTURES / "clean_invocation.json"),
    )
    assert rejected.returncode == 1, rejected.stdout + rejected.stderr
    assert "host-owned field" in rejected.stderr

    accepted = _run(
        cook_pyz,
        "normalize",
        str(COOK_PAYLOAD_FIXTURES / "clean_writer_view.json"),
        "--invocation",
        str(COOK_PAYLOAD_FIXTURES / "clean_invocation.json"),
    )
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    canonical = cast(dict[str, object], json.loads(accepted.stdout))
    assert cast(dict[str, object], canonical["value"])["plan_id"] == "curdplan-cook-cli-normalize-1"
    assert cast(str, canonical["digest"]).startswith("sha256:")


def test_cook_pyz_dispatches_validate_end_to_end() -> None:
    cook_pyz = build_pyz.cached_bundle("cook")
    rejected = _run(
        cook_pyz,
        "validate",
        str(COOK_PAYLOAD_FIXTURES / "nonconforming_writer_view.json"),
        "--schema",
        "agent-writer-view",
    )
    assert rejected.returncode == 1, rejected.stdout + rejected.stderr
    assert "$.kind" in rejected.stderr

    accepted = _run(
        cook_pyz,
        "validate",
        str(COOK_PAYLOAD_FIXTURES / "conforming_writer_view.json"),
        "--schema",
        "agent-writer-view",
    )
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
