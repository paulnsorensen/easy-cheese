"""Release notes are generated from main's real history, not the orphan release
tag. These tests pin the invariants that the empty-notes bug violated: the
previous tag's source SHA is recovered from its `main@<sha>` subject, the commit
range is the main range (not the single-commit orphan), and conventional-commit
types land in the right sections.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import release_notes  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, subject: str) -> str:
    (repo / "f").write_text(subject)
    _git(repo, "add", "f")
    _git(repo, "commit", "-m", subject)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    return r


def test_recovers_prev_source_and_categorizes(repo: Path) -> None:
    prev_source = _commit(repo, "feat(old): shipped in last release (#1)")
    # The orphan release snapshot: a commit whose subject records its main SHA.
    release_commit = _commit(repo, f"release: v0.1.0 from main@{prev_source}")
    _git(repo, "tag", "v0.1.0", release_commit)

    _commit(repo, "feat(paths): anchor durable corpus (#84)")
    _commit(repo, "fix(docs): stop token corruption (#89)")
    _commit(repo, "docs(readme): add badges (#91)")
    _commit(repo, "chore(deps): bump github/codeql-action from 4.35.5 to 4.36.0 (#87)")
    _commit(repo, "refactor: tidy internals (#92)")
    to_sha = _git(repo, "rev-parse", "HEAD")

    notes = release_notes.generate("v0.2.0", to_sha, "owner/repo", cwd=str(repo))

    # The prior-release feat must NOT appear — it predates prev_source.
    assert "shipped in last release" not in notes
    # Each type lands under its heading.
    assert "### Features\n- Anchor durable corpus (#84)" in notes
    assert "### Fixes\n- Stop token corruption (#89)" in notes
    assert "### Documentation\n- Add badges (#91)" in notes
    assert "### Dependencies\n- Bump github/codeql-action from 4.35.5 to 4.36.0 (#87)" in notes
    assert "### Maintenance\n- Tidy internals (#92)" in notes
    # Changelog link spans the real main range, not the orphan tag.
    assert f"compare/{prev_source}...{to_sha}" in notes


def test_breaking_change_promoted(repo: Path) -> None:
    _commit(repo, "feat(api)!: drop legacy flag (#5)")
    to_sha = _git(repo, "rev-parse", "HEAD")
    notes = release_notes.generate("v0.1.0", to_sha, "owner/repo", cwd=str(repo))
    assert "### Breaking changes\n- Drop legacy flag (#5)" in notes
    # A bang feat is breaking, not a plain feature.
    assert "### Features" not in notes


def test_no_previous_tag_lists_all_history(repo: Path) -> None:
    _commit(repo, "feat: first ever (#1)")
    to_sha = _git(repo, "rev-parse", "HEAD")
    notes = release_notes.generate("v0.1.0", to_sha, "owner/repo", cwd=str(repo))
    assert "- First ever (#1)" in notes
    # No prior tag means no changelog compare link.
    assert "Full Changelog" not in notes


def test_non_conventional_subject_falls_to_other(repo: Path) -> None:
    _commit(repo, "random uncategorized commit")
    to_sha = _git(repo, "rev-parse", "HEAD")
    notes = release_notes.generate("v0.1.0", to_sha, "owner/repo", cwd=str(repo))
    assert "### Other\n- Random uncategorized commit" in notes
