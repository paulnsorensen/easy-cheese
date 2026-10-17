"""Cross-root continuity keeps Wheypoint identity with the explicit target repository."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from easy_cheese.shared import paths
from easy_cheese.shared.wheypoint import resolve, storage
from easy_cheese.shared.write_handoff_artifact import write_artifact


def _git_repository(root: Path, *, context: str) -> None:
    root.mkdir()
    _ = subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    _ = subprocess.run(
        ["git", "config", "user.email", "tests@example.com"], cwd=root, check=True
    )
    _ = subprocess.run(
        ["git", "config", "user.name", "Tests"], cwd=root, check=True
    )
    _ = (root / "context.md").write_text(context, encoding="utf-8")
    _ = subprocess.run(["git", "add", "context.md"], cwd=root, check=True)
    _ = subprocess.run(
        ["git", "commit", "-q", "-m", "seed"], cwd=root, check=True
    )


def test_explicit_target_root_owns_default_corpus_and_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    caller = tmp_path / "caller-a"
    target = tmp_path / "target-b"
    _git_repository(caller, context="caller context\n")
    _git_repository(target, context="target context\n")
    monkeypatch.chdir(caller)
    monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path / "corpus"))
    monkeypatch.delenv("EASY_CHEESE_PROJECT", raising=False)

    written = write_artifact(
        slug="cross-root",
        status="ok",
        next_skill="press",
        artifact="",
        orientation="target repository checkpoint",
        body=None,
        root=target,
        phase="cook",
        grounded=("context.md#1-1",),
    )

    target_project = paths.project_key(target)
    target_corpus = paths.project_corpus_root(target_project)
    record = storage.WorkStore.open(
        "cross-root", corpus_root=target_corpus
    ).read_record()
    assert written == target / ".cheese" / "cook" / "cross-root.md"
    assert record is not None
    assert record.project_key == target_project
    assert not (paths.project_corpus_root(paths.project_key(caller)) / "work").exists()

    result = resolve.resolve("cross-root", workspace_root=target)
    assert result.outcome is resolve.ResolutionOutcome.AUTHORITATIVE
    assert result.record is not None
    assert result.record.project_key == target_project


def test_explicit_corpus_and_project_overrides_remain_authoritative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    caller = tmp_path / "caller-a"
    target = tmp_path / "target-b"
    _git_repository(caller, context="caller context\n")
    _git_repository(target, context="target context\n")
    monkeypatch.chdir(caller)
    monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path / "corpus"))
    monkeypatch.setenv("EASY_CHEESE_PROJECT", "explicit-project")

    explicit_corpus = tmp_path / "explicit-corpus"
    _ = write_artifact(
        slug="explicit-root",
        status="ok",
        next_skill="press",
        artifact="",
        orientation="explicit corpus checkpoint",
        body=None,
        root=target,
        phase="cook",
        grounded=("context.md#1-1",),
        corpus_root=explicit_corpus,
    )

    result = resolve.resolve(
        "explicit-root",
        corpus_root=explicit_corpus,
        project_key="explicit-project",
        workspace_root=target,
    )
    assert result.outcome is resolve.ResolutionOutcome.AUTHORITATIVE
    assert result.record is not None
    assert result.record.project_key == "explicit-project"
