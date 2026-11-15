"""The /age `review-evidence` command, run from the built age archive (AC-3)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

BASE = "def load(path):\n    return read(path)\n\n\ndef drop():\n    pass\n"
HEAD = "def load(path):\n    try:\n        return read(path)\n    except Exception:\n        pass\n"


def _git(repo: Path, *args: str) -> None:
    _ = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    _ = (root / "src" / "store.py").write_text(BASE, encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "base")
    _ = (root / "src" / "store.py").write_text(HEAD, encoding="utf-8")
    return root


def _evidence(archive: Path, repo: Path, path_env: str, tmp_path: Path) -> dict[str, object]:
    env = {**os.environ, "PATH": path_env, "SHIV_ROOT": str(tmp_path / "shiv")}
    result = subprocess.run(
        [sys.executable, str(archive), "review-evidence", "--repo", str(repo), "HEAD"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return cast(dict[str, object], json.loads(result.stdout))


def test_review_evidence_reports_hits_and_facts(
    skill_archive: Callable[[str], Path], repo: Path, tmp_path: Path
) -> None:
    binary = shutil.which("ast-grep")
    assert binary is not None, "ast-grep must be on PATH"
    git = shutil.which("git")
    assert git is not None
    path_env = os.pathsep.join({str(Path(binary).parent), str(Path(git).parent)})
    evidence = _evidence(skill_archive("age"), repo, path_env, tmp_path)

    assert evidence["scan"] == {"status": "ok"}
    hits = cast(list[dict[str, object]], evidence["hits"])
    assert [(hit["rule_id"], hit["dimension"], hit["line"]) for hit in hits] == [
        ("py-swallowed-exception", "correctness", 4)
    ]
    facts = cast(dict[str, dict[str, object]], evidence["facts"])
    assert facts["compat"] == {
        "value": "yes",
        "detail": {"removed": [{"path": "src/store.py", "name": "drop"}]},
    }
    assert facts["tests"]["value"] == "yes"


def test_review_evidence_without_ast_grep_still_completes(
    skill_archive: Callable[[str], Path], repo: Path, tmp_path: Path
) -> None:
    git = shutil.which("git")
    assert git is not None
    no_ast_grep = tmp_path / "bin"
    no_ast_grep.mkdir()
    (no_ast_grep / "git").symlink_to(git)
    evidence = _evidence(skill_archive("age"), repo, str(no_ast_grep), tmp_path)

    assert evidence["scan"] == {"status": "failed:ast-grep-missing"}
    assert evidence["hits"] == []
    facts = cast(dict[str, dict[str, object]], evidence["facts"])
    assert {name: fact["value"] for name, fact in facts.items()} == {
        "compat": "unknown",
        "dependencies": "unknown",
        "tests": "unknown",
        "scope": "unknown",
    }


def test_review_evidence_rejects_an_option_as_base(
    skill_archive: Callable[[str], Path], repo: Path
) -> None:
    result = subprocess.run(
        [sys.executable, str(skill_archive("age")), "review-evidence", "--repo", str(repo), "--", "--output=x"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "must not start with '-'" in result.stderr


def test_review_evidence_scans_untracked_files_and_skips_base_links(
    skill_archive: Callable[[str], Path], tmp_path: Path
) -> None:
    """An untracked file counts as changed, and an absolute link in base does not stop the run."""
    root = tmp_path / "linked"
    (root / "src").mkdir(parents=True)
    _ = (root / "src" / "store.py").write_text(BASE, encoding="utf-8")
    (root / "etc-link").symlink_to("/etc/hostname")
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "base")
    _ = (root / "src" / "fresh.py").write_text("eval(token)\n", encoding="utf-8")
    binary = shutil.which("ast-grep")
    git = shutil.which("git")
    assert binary is not None and git is not None
    path_env = os.pathsep.join({str(Path(binary).parent), str(Path(git).parent)})

    evidence = _evidence(skill_archive("age"), root, path_env, tmp_path)

    assert evidence["scan"] == {"status": "ok"}
    hits = cast(list[dict[str, object]], evidence["hits"])
    assert [(hit["rule_id"], hit["path"]) for hit in hits] == [("py-eval-exec", "src/fresh.py")]
    facts = cast(dict[str, dict[str, object]], evidence["facts"])
    assert facts["tests"]["detail"] == {"untested": ["src/fresh.py"], "sources": 1}
