"""Each skill ships a self-contained <skill>.pyz containing only its own scripts
plus the shared modules it imports. Every subcommand must dispatch and resolve its
imports from inside the zip — no sys.path traversal, and no other skill's code.
"""

from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD = REPO_ROOT / "scripts" / "build_pyz.py"

sys.path.insert(0, str(REPO_ROOT / "shared" / "scripts"))
import paths  # noqa: E402  the path-math single source the shim must agree with

SKILL_SUBCOMMANDS = {
    "melt": [
        "batch-resolve",
        "conflict-pick",
        "conflict-summary",
        "detect-squash-residue",
        "lockfile-resolve",
    ],
    "cheese-factory": [
        "artifact-path",
        "pr_plan_to_branches",
        "validate_decomposition",
        "validate_manifest",
        "validate_pr_plan",
    ],
    "affinage": ["pr-status"],
    "mold": ["artifact-path", "curd-count"],
    "briesearch": ["artifact-path", "ground-check"],
    "cook": ["artifact-path"],
}

# Every skill that registers the durable-corpus resolver shim. One shared source
# (shared/scripts/artifact_path.py) backs them all; each must agree with
# paths.artifact_path / paths.project_corpus_root.
ARTIFACT_PATH_SKILLS = ("mold", "cheese-factory", "briesearch", "cook")


@pytest.fixture(scope="module")
def bundles(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("pyz")
    result = subprocess.run(
        [sys.executable, str(BUILD), "--out-dir", str(out)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return out


def _run(pyz: Path, *args: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    # Run from the bundle's own dir with PYTHONPATH stripped, so the only way an
    # import can resolve is from inside the .pyz itself.
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(pyz), *args],
        cwd=str(pyz.parent),
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.mark.parametrize(
    "skill,sub",
    [(skill, sub) for skill, subs in SKILL_SUBCOMMANDS.items() for sub in subs],
)
def test_subcommand_resolves_inside_bundle(bundles: Path, skill: str, sub: str) -> None:
    result = _run(bundles / f"{skill}.pyz", sub, "--help")
    combined = result.stdout + result.stderr
    assert "ModuleNotFoundError" not in combined, combined
    assert "Traceback" not in combined, combined


@pytest.mark.parametrize("skill", list(SKILL_SUBCOMMANDS))
def test_unknown_subcommand_is_rejected(bundles: Path, skill: str) -> None:
    result = _run(bundles / f"{skill}.pyz", "no-such-subcommand")
    assert result.returncode == 2
    assert "usage" in result.stderr.lower()


def test_melt_subcommand_executes_with_forwarded_args(bundles: Path, tmp_path: Path) -> None:
    """A real subcommand runs end-to-end through the bundle: proves argv forwarding,
    the shared git_utils import resolving, and correct routing."""
    conflict = tmp_path / "f.txt"
    conflict.write_text(
        "before\n<<<<<<< HEAD\nOURS_LINE\n=======\nTHEIRS_LINE\n>>>>>>> branch\nafter\n"
    )
    result = _run(bundles / "melt.pyz", "conflict-pick", str(conflict), "--theirs", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "THEIRS_LINE" in result.stdout
    assert "OURS_LINE" not in result.stdout
    assert "<<<<<<<" not in result.stdout


def test_cheese_factory_routing_is_subcommand_specific(bundles: Path, tmp_path: Path) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text("{}")
    manifest = _run(bundles / "cheese-factory.pyz", "validate_manifest", str(empty))
    pr_plan = _run(bundles / "cheese-factory.pyz", "validate_pr_plan", str(empty))
    assert manifest.returncode == 1
    assert pr_plan.returncode == 1
    assert "manifest.slug is required" in manifest.stderr
    assert "manifest.slug" not in pr_plan.stderr
    assert "shape must be one of single" in pr_plan.stderr


def test_bundle_carries_only_its_own_skill(bundles: Path) -> None:
    """The O(n) guarantee: a skill's bundle excludes other skills' scripts and any
    shared module it does not import."""
    melt = set(zipfile.ZipFile(bundles / "melt.pyz").namelist())
    assert "conflict_pick.py" in melt
    assert "git_utils.py" in melt  # the one shared module melt imports
    assert "validate_manifest.py" not in melt  # cheese-factory's script
    assert "pr_status.py" not in melt  # affinage's script
    assert "manifest_io.py" not in melt  # shared module melt does not import
    assert "severity.py" not in melt  # shared module no bundled skill imports

    affinage = set(zipfile.ZipFile(bundles / "affinage.pyz").namelist())
    assert "pr_status.py" in affinage
    assert not (affinage & {"git_utils.py", "manifest_io.py", "schema.py"})  # no shared needed


# Pinned env so the resolved corpus path is deterministic and does not depend on
# the test host's git remote or real XDG dirs.
_CORPUS_ENV = {"EASY_CHEESE_HOME": "/tmp/ec-corpus", "EASY_CHEESE_PROJECT": "demo-project"}


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
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    result = _run(bundles / f"{skill}.pyz", "artifact-path", "specs", "demo-slug", extra_env=_CORPUS_ENV)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


def test_artifact_path_research_returns_corpus_root(bundles: Path) -> None:
    """research resolves to the bare project corpus root; briesearch composes the
    nested research/<slug>/<slug>.md layout on top of it."""
    result = _run(
        bundles / "briesearch.pyz", "artifact-path", "research", "demo-slug", extra_env=_CORPUS_ENV
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
    bad = _run(bundles / "briesearch.pyz", "artifact-path", "research", "Bad_Slug", extra_env=_CORPUS_ENV)
    assert bad.returncode == 0, bad.stderr
    assert bad.stdout.strip() == "/tmp/ec-corpus/demo-project"
    # The slug is not appended to the path for research (contrast with specs).
    assert "Bad_Slug" not in bad.stdout
    other = _run(bundles / "briesearch.pyz", "artifact-path", "research", "totally-different-slug", extra_env=_CORPUS_ENV)
    assert other.stdout.strip() == bad.stdout.strip()


def test_artifact_path_rejects_bad_slug(bundles: Path) -> None:
    result = _run(bundles / "mold.pyz", "artifact-path", "specs", "Bad_Slug", extra_env=_CORPUS_ENV)
    assert result.returncode == 1
    assert "kebab-case" in result.stderr


def test_artifact_path_rejects_unknown_phase(bundles: Path) -> None:
    result = _run(bundles / "mold.pyz", "artifact-path", "nonsense", "demo-slug", extra_env=_CORPUS_ENV)
    assert result.returncode == 1
    assert "unknown phase" in result.stderr


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
    report.write_text(body)
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
    result = _run(bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, _GROUNDED_REPORT)))
    assert result.returncode == 0, result.stderr
    assert "grounding ok" in result.stderr


def test_ground_check_rejects_nonlabel_confidence(bundles: Path, tmp_path: Path) -> None:
    """Confidence must be one of the three exact labels. A synonym like 'high' is a
    silent confidence drift the cap rules can't reason about — fail it."""
    body = _GROUNDED_REPORT.replace("| certain |", "| high |")
    result = _run(bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body)))
    assert result.returncode == 1, result.stderr
    assert "CONFIDENCE" in result.stderr


def test_ground_check_absence_advisory_does_not_fail(bundles: Path, tmp_path: Path) -> None:
    """A cited, certain absence claim with no ruling-out phrase is surfaced as an
    ADVISORY (feeds the synthesis-fidelity self-check) but does NOT fail the gate:
    observed-vs-inferred absence is not decidable from text, so it is flagged for
    judgement, not auto-rejected. Pins that the advisory stays soft."""
    body = _GROUNDED_REPORT.replace(
        "| No broader sandbox knob was found in the config reference searched | [^s1] | vendor docs | 2026-06-01 | speculating | only config.toml checked |",
        "| Codex does not expose a global sandbox knob | [^s1] | vendor docs | 2026-06-01 | certain | |",
    )
    result = _run(bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body)))
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


def test_ground_check_accepts_url_and_raw_path_citations(bundles: Path, tmp_path: Path) -> None:
    """A verifiable citation is a footnote, URL, path:line, OR a raw-capture path —
    not just the footnote form the headline test uses. Locks all marker branches so a
    narrowed citation regex (e.g. footnote-only) fails loudly instead of rejecting
    legitimately-grounded reports."""
    body = (
        "## Research: q\n\n### Evidence\n\n"
        "| Claim | Evidence | Confidence |\n| --- | --- | --- |\n"
        "| A holds | https://example.com/a | certain |\n"
        "| B holds | raw/01-example.md#L3-8 | certain |\n"
    )
    result = _run(bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body)))
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
    result = _run(bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body)))
    assert result.returncode == 1, result.stderr
    assert "CITATION" in result.stderr
    assert "Y holds" in result.stderr
    assert "2 table(s)" in result.stderr


def test_ground_check_reads_source_column_in_three_col_table(bundles: Path, tmp_path: Path) -> None:
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
    result = _run(bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body)))
    assert result.returncode == 0, result.stderr


def test_ground_check_absence_guard_avoids_false_positives(bundles: Path, tmp_path: Path) -> None:
    """The absence advisory must not fire on (a) a positive claim that merely contains a
    negation substring mid-word ('another'), nor (b) a certain absence already grounded
    by a ruling-out phrase ('not found in ... searched'). Locks the word-boundary match
    and the ruled-out escape so the advisory stays signal, not noise."""
    body = (
        "## Research: q\n\n### Evidence\n\n"
        "| Claim | Evidence | Confidence |\n| --- | --- | --- |\n"
        "| Cargo exposes another download feature | [^s1] | certain |\n"
        "| The knob was not found in the two references searched | [^s1] | certain |\n\n"
        "## References\n[^s1]: https://example.com (fetched 2026-06-01).\n"
    )
    result = _run(bundles / "briesearch.pyz", "ground-check", str(_write(tmp_path, body)))
    assert result.returncode == 0, result.stderr
    assert "ADVISORY" not in result.stderr
