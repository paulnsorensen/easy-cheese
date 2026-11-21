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

import fromargs
import pytest

from easy_cheese.skills.age import review_evidence

BASE = "def load(path):\n    return read(path)\n\n\ndef drop():\n    pass\n"
HEAD = "def load(path):\n    try:\n        return read(path)\n    except Exception:\n        pass\n"


def _git(repo: Path, *args: str) -> None:
    _ = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    _ = (root / "src" / "store.py").write_text(BASE, encoding="utf-8")
    _git(root, "init", "-q")
    _commit(root, "base")
    _ = (root / "src" / "store.py").write_text(HEAD, encoding="utf-8")
    return root


def _tool_path() -> str:
    binary = shutil.which("ast-grep")
    git = shutil.which("git")
    assert binary is not None, "ast-grep must be on PATH"
    assert git is not None
    return os.pathsep.join({str(Path(binary).parent), str(Path(git).parent)})


def _evidence(
    archive: Path, repo: Path, path_env: str, tmp_path: Path, base: str = "HEAD"
) -> dict[str, object]:
    env = {**os.environ, "PATH": path_env, "SHIV_ROOT": str(tmp_path / "shiv")}
    result = subprocess.run(
        [sys.executable, str(archive), "review-evidence", "--repo", str(repo), base],
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
    assert facts["tests"] == {"value": "yes", "detail": {"untested": ["src/store.py"], "sources": 1}}
    for name in ("compat", "dependencies", "scope"):
        assert facts[name] == {"value": "unknown", "detail": {"reason": "ast-grep ast-grep-missing"}}, name


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


@pytest.mark.parametrize(
    ("attributes", "name", "body", "rule_id"),
    [
        pytest.param("*.py -diff\n", "run.py", "def run(x):\n    return eval(x)\n", "py-eval-exec", id="py-minus-diff"),
        pytest.param("", "run.ts", "// a\0b\nexport function run(x: string) {\n  return eval(x);\n}\n", "ts-eval", id="ts-nul"),
    ],
)
def test_review_evidence_keeps_hits_in_files_git_calls_binary(
    skill_archive: Callable[[str], Path], tmp_path: Path, attributes: str, name: str, body: str, rule_id: str
) -> None:
    """A `-diff` attribute or a NUL byte in the reviewed tree does not hide a rule hit."""
    root = tmp_path / "binary"
    root.mkdir()
    _ = (root / name).write_text("// base\n" if name.endswith(".ts") else "# base\n", encoding="utf-8")
    _git(root, "init", "-q")
    _commit(root, "base")
    if attributes:
        _ = (root / ".gitattributes").write_text(attributes, encoding="utf-8")
    _ = (root / name).write_text(body, encoding="utf-8")
    _commit(root, "head")

    evidence = _evidence(skill_archive("age"), root, _tool_path(), tmp_path, base="HEAD~1")

    assert evidence["scan"] == {"status": "ok"}
    hits = cast(list[dict[str, object]], evidence["hits"])
    assert [(hit["rule_id"], hit["path"]) for hit in hits] == [(rule_id, name)]


def test_review_evidence_reads_export_ignore_base_files(
    skill_archive: Callable[[str], Path], tmp_path: Path
) -> None:
    """A base file marked `export-ignore` still counts for `compat`."""
    root = tmp_path / "ignored"
    root.mkdir()
    _ = (root / ".gitattributes").write_text("lib.py export-ignore\n", encoding="utf-8")
    _ = (root / "lib.py").write_text("def public():\n    pass\n\n\ndef keep():\n    pass\n", encoding="utf-8")
    _git(root, "init", "-q")
    _commit(root, "base")
    _ = (root / "lib.py").write_text("def keep():\n    pass\n", encoding="utf-8")

    evidence = _evidence(skill_archive("age"), root, _tool_path(), tmp_path)

    facts = cast(dict[str, dict[str, object]], evidence["facts"])
    assert facts["compat"] == {"value": "yes", "detail": {"removed": [{"path": "lib.py", "name": "public"}]}}


def test_review_evidence_counts_imports_of_base_mts_files(
    skill_archive: Callable[[str], Path], tmp_path: Path
) -> None:
    """A module that only a base `.mts` file imports is not a new dependency."""
    root = tmp_path / "mts"
    root.mkdir()
    _ = (root / "lib.mts").write_text('import pad from "left-pad";\nexport const a = pad;\n', encoding="utf-8")
    _git(root, "init", "-q")
    _commit(root, "base")
    _ = (root / "app.ts").write_text(
        'import pad from "left-pad";\nimport fresh from "fresh-pkg";\nexport const b = [pad, fresh];\n',
        encoding="utf-8",
    )

    evidence = _evidence(skill_archive("age"), root, _tool_path(), tmp_path)

    facts = cast(dict[str, dict[str, object]], evidence["facts"])
    detail = cast(dict[str, object], facts["dependencies"]["detail"])
    assert detail["added_imports"] == [{"path": "app.ts", "module": "fresh-pkg"}]


def test_extract_base_writes_only_code_files(tmp_path: Path) -> None:
    """The base tree holds the code files of the base revision and no other file or link."""
    root = tmp_path / "assets"
    (root / "pkg").mkdir(parents=True)
    _ = (root / "pkg" / "mod.py").write_text("import os\n", encoding="utf-8")
    _ = (root / "web.ts").write_text("export const a = 1;\n", encoding="utf-8")
    _ = (root / "logo.png").write_bytes(b"\x89PNG\0" * 1000)
    _ = (root / "README.md").write_text("# r\n", encoding="utf-8")
    (root / "link.py").symlink_to("pkg/mod.py")
    _git(root, "init", "-q")
    _commit(root, "base")
    target = tmp_path / "base"
    target.mkdir()

    review_evidence._extract_base(root, "HEAD", target)  # pyright: ignore[reportPrivateUsage]

    written = sorted(path.relative_to(target).as_posix() for path in target.rglob("*") if not path.is_dir())
    assert written == ["pkg/mod.py", "web.ts"]
    assert (target / "pkg" / "mod.py").read_text(encoding="utf-8") == "import os\n"


def test_extract_base_reports_a_bad_revision(tmp_path: Path) -> None:
    root = tmp_path / "bad"
    root.mkdir()
    _ = (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "init", "-q")
    _commit(root, "base")

    with pytest.raises(fromargs.CliError, match="no-such-rev"):
        review_evidence._extract_base(root, "no-such-rev", tmp_path)  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize("path", ["", "../x.py", "a/../../x.py", "/etc/x.py", "out/x.py"])
def test_a_base_path_that_leaves_the_target_is_refused(tmp_path: Path, path: str) -> None:
    target = tmp_path / "base"
    target.mkdir()
    (target / "out").symlink_to(tmp_path)

    assert review_evidence._inside(target, path) is None  # pyright: ignore[reportPrivateUsage]


def test_a_base_path_inside_the_target_is_kept(tmp_path: Path) -> None:
    destination = review_evidence._inside(tmp_path, "src/store.py")  # pyright: ignore[reportPrivateUsage]

    assert destination == tmp_path / "src" / "store.py"
