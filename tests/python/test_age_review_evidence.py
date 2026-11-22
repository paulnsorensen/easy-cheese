"""The /age `review-evidence` command, run from the built age archive (AC-3)."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tracemalloc
from collections.abc import Callable
from pathlib import Path
from typing import cast

import fromargs
import pytest

from easy_cheese.skills.age import review_evidence
from easy_cheese_review import MAX_FILE_BYTES

BASE = "def load(path):\n    return read(path)\n\n\ndef drop():\n    pass\n"
HEAD = "def load(path):\n    try:\n        return read(path)\n    except Exception:\n        pass\n"


def _git(repo: Path, *args: str) -> None:
    _ = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", message)


def _write_raw_name(root: Path, name: bytes, body: str) -> None:
    """Write a file whose name is not UTF-8; skip the test when the file system refuses the name."""
    try:
        _ = (root / os.fsdecode(name)).write_text(body, encoding="utf-8")
    except (OSError, UnicodeError):
        pytest.skip("the file system refuses a file name that is not UTF-8")


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

    assert evidence["scan"] == {"status": "ok", "skipped": []}
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

    assert evidence["scan"] == {"status": "failed:ast-grep-missing", "skipped": []}
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

    assert evidence["scan"] == {"status": "ok", "skipped": []}
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

    assert evidence["scan"] == {"status": "ok", "skipped": []}
    hits = cast(list[dict[str, object]], evidence["hits"])
    assert [(hit["rule_id"], hit["path"]) for hit in hits] == [(rule_id, name)]


@pytest.mark.parametrize(
    "separator", [pytest.param(b"\x0c", id="form-feed"), pytest.param(b"\r", id="lone-cr")]
)
def test_review_evidence_keeps_the_hit_after_a_line_break_character(
    skill_archive: Callable[[str], Path], tmp_path: Path, separator: bytes
) -> None:
    """A form feed or a lone carriage return in a changed line does not end its diff line."""
    root = tmp_path / "feed"
    root.mkdir()
    _ = (root / "run.py").write_bytes(b"x = 0\na = 1\nb = 2\nc = 3\nprint(x)\n")
    _git(root, "init", "-q")
    _commit(root, "base")
    _ = (root / "run.py").write_bytes(b"x = 1" + separator + b"+++ /dev/null\na = 1\nb = 2\nc = 3\neval(x)\n")

    evidence = _evidence(skill_archive("age"), root, _tool_path(), tmp_path)

    assert evidence["scan"] == {"status": "ok", "skipped": []}
    hits = cast(list[dict[str, object]], evidence["hits"])
    assert [(hit["rule_id"], hit["path"], hit["line"]) for hit in hits] == [("py-eval-exec", "run.py", 5)]


@pytest.fixture
def raw_name_repo(tmp_path: Path) -> Path:
    """A repository with a changed file and an untracked file whose names are not UTF-8."""
    root = tmp_path / "raw"
    root.mkdir()
    _write_raw_name(root, b"t\xff.py", "# base\n")
    _git(root, "init", "-q")
    _commit(root, "base")
    _write_raw_name(root, b"t\xff.py", "eval(x)\n")
    _write_raw_name(root, b"u\xfe.py", "exec(y)\n")
    return root


def test_review_evidence_passes_names_that_are_not_utf8_to_the_scan(
    skill_archive: Callable[[str], Path], raw_name_repo: Path, tmp_path: Path
) -> None:
    """Each name reaches the scan as the name on disk, and the JSON spells its raw byte as a lone surrogate."""
    evidence = _evidence(skill_archive("age"), raw_name_repo, _tool_path(), tmp_path)

    facts = cast(dict[str, dict[str, object]], evidence["facts"])
    assert facts["tests"]["detail"] == {"untested": ["t\udcff.py", "u\udcfe.py"], "sources": 2}


@pytest.mark.xfail(
    strict=True,
    reason="ast-grep 0.51.3 panics (exit 101) on an argument that is not UTF-8, so the whole scan fails",
)
def test_review_evidence_keeps_the_hits_of_files_whose_names_are_not_utf8(
    skill_archive: Callable[[str], Path], raw_name_repo: Path, tmp_path: Path
) -> None:
    """A changed file and an untracked file keep their hits when their names are not UTF-8."""
    evidence = _evidence(skill_archive("age"), raw_name_repo, _tool_path(), tmp_path)

    assert evidence["scan"] == {"status": "ok", "skipped": []}
    hits = cast(list[dict[str, object]], evidence["hits"])
    assert [(hit["rule_id"], hit["line"]) for hit in hits] == [("py-eval-exec", 1), ("py-eval-exec", 1)]


def test_review_evidence_never_drops_a_file_with_a_raw_name_in_silence(
    skill_archive: Callable[[str], Path], raw_name_repo: Path, tmp_path: Path
) -> None:
    """A scan that reports `ok` keeps the hits of both files whose names are not UTF-8."""
    evidence = _evidence(skill_archive("age"), raw_name_repo, _tool_path(), tmp_path)

    hits = cast(list[dict[str, object]], evidence["hits"])
    rule_ids = [hit["rule_id"] for hit in hits]
    scan = cast(dict[str, object], evidence["scan"])
    assert scan["status"] != "ok" or rule_ids == ["py-eval-exec", "py-eval-exec"]


def test_review_evidence_ignores_a_textconv_driver(
    skill_archive: Callable[[str], Path], tmp_path: Path
) -> None:
    """A textconv driver that `.gitattributes` selects does not move a hunk off the real line."""
    root = tmp_path / "conv"
    root.mkdir()
    driver = tmp_path / "pad.py"
    _ = driver.write_text(
        'import sys\n\n_ = sys.stdout.write("pad\\n" * 50 + open(sys.argv[1], encoding="utf-8").read())\n',
        encoding="utf-8",
    )
    _ = (root / ".gitattributes").write_text("*.py diff=pad\n", encoding="utf-8")
    _ = (root / "run.py").write_text("a = 1\nb = 2\nc = 3\nprint(a)\n", encoding="utf-8")
    _git(root, "init", "-q")
    _commit(root, "base")
    _git(root, "config", "diff.pad.textconv", f"{shlex.quote(sys.executable)} {shlex.quote(str(driver))}")
    _ = (root / "run.py").write_text("a = 1\nb = 2\nc = 3\neval(a)\n", encoding="utf-8")

    evidence = _evidence(skill_archive("age"), root, _tool_path(), tmp_path)

    assert evidence["scan"] == {"status": "ok", "skipped": []}
    hits = cast(list[dict[str, object]], evidence["hits"])
    assert [(hit["rule_id"], hit["path"], hit["line"]) for hit in hits] == [("py-eval-exec", "run.py", 4)]


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


def test_review_evidence_skips_and_reports_oversized_files(
    skill_archive: Callable[[str], Path], tmp_path: Path
) -> None:
    """A file above the size limit is not scanned, in head or in base, and the result names it."""
    root = tmp_path / "huge"
    root.mkdir()
    filler = "x = 1\n" * (MAX_FILE_BYTES // 6 + 1)
    _ = (root / "vendor.py").write_text("import requests\n" + filler, encoding="utf-8")
    _ = (root / "lib.py").write_text("def keep():\n    pass\n", encoding="utf-8")
    _git(root, "init", "-q")
    _commit(root, "base")
    _ = (root / "gen.py").write_text("eval(token)\n" + filler, encoding="utf-8")
    _ = (root / "app.py").write_text("import requests\n\n\ndef run():\n    return eval(token)\n", encoding="utf-8")

    evidence = _evidence(skill_archive("age"), root, _tool_path(), tmp_path)

    scan = cast(dict[str, object], evidence["scan"])
    assert scan["status"] == "ok"
    assert scan["skipped"] == [
        {"tree": "base", "path": "vendor.py", "bytes": (root / "vendor.py").stat().st_size},
        {"tree": "head", "path": "gen.py", "bytes": (root / "gen.py").stat().st_size},
    ]
    hits = cast(list[dict[str, object]], evidence["hits"])
    assert [(hit["rule_id"], hit["path"]) for hit in hits] == [("py-eval-exec", "app.py")]
    facts = cast(dict[str, dict[str, object]], evidence["facts"])
    # Only the skipped base file imports `requests`, so `added_imports` cannot be trusted.
    assert facts["dependencies"]["value"] == "unknown"
    dependencies = cast(dict[str, object], facts["dependencies"]["detail"])
    assert (dependencies["reason"], dependencies["skipped"]) == ("file-too-large", ["vendor.py"])
    assert dependencies["added_imports"] == [{"path": "app.py", "module": "requests"}]
    # `gen.py` has no visible imports, so it looks like a second group.
    assert facts["scope"]["value"] == "unknown"
    scope = cast(dict[str, object], facts["scope"]["detail"])
    assert (scope["reason"], scope["skipped"]) == ("file-too-large", ["gen.py"])
    assert facts["tests"] == {"value": "yes", "detail": {"untested": ["app.py", "gen.py"], "sources": 2}}


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


def test_extract_base_keeps_names_that_are_not_utf8_apart(tmp_path: Path) -> None:
    """Two base files whose names differ only in a byte that is not UTF-8 go to two files."""
    root = tmp_path / "raw-base"
    root.mkdir()
    _write_raw_name(root, b"bad\xfe.py", "a = 1\n")
    _write_raw_name(root, b"bad\xff.py", "b = 2\n")
    _git(root, "init", "-q")
    _commit(root, "base")
    target = tmp_path / "base"
    target.mkdir()

    review_evidence._extract_base(root, "HEAD", target)  # pyright: ignore[reportPrivateUsage]

    written = {os.fsencode(path.name): path.read_text(encoding="utf-8") for path in target.iterdir()}
    assert written == {b"bad\xfe.py": "a = 1\n", b"bad\xff.py": "b = 2\n"}


def test_extract_base_holds_one_blob_at_a_time(tmp_path: Path) -> None:
    """The peak memory of the extraction stays below the size of all base blobs together."""
    root = tmp_path / "big"
    root.mkdir()
    size, count = 2 * 1024 * 1024, 8
    bodies = {f"m{index}.py": bytes([ord("a") + index]) * (size - 1) + b"\n" for index in range(count)}
    for name, body in bodies.items():
        _ = (root / name).write_bytes(body)
    _git(root, "init", "-q")
    _commit(root, "base")
    target = tmp_path / "base"
    target.mkdir()

    tracemalloc.start()
    try:
        review_evidence._extract_base(root, "HEAD", target)  # pyright: ignore[reportPrivateUsage]
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert {path.name: path.read_bytes() for path in target.iterdir()} == bodies
    assert peak < size * count // 2


def test_extract_base_reports_a_missing_blob(tmp_path: Path) -> None:
    """A base blob that the object store lost stops the run with the path of the blob."""
    root = tmp_path / "lost"
    root.mkdir()
    _ = (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    _ = (root / "b.py").write_text("y = 2\n", encoding="utf-8")
    _git(root, "init", "-q")
    _commit(root, "base")
    object_id = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD:a.py"], capture_output=True, text=True, check=True
    ).stdout.strip()
    (root / ".git" / "objects" / object_id[:2] / object_id[2:]).unlink()
    target = tmp_path / "base"
    target.mkdir()

    with pytest.raises(fromargs.CliError, match=r"no blob for a\.py"):
        review_evidence._extract_base(root, "HEAD", target)  # pyright: ignore[reportPrivateUsage]


def test_extract_base_stops_a_cat_file_run_at_the_time_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `cat-file` process that prints nothing ends at the time limit."""
    root = tmp_path / "slow"
    root.mkdir()
    _ = (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "init", "-q")
    _commit(root, "base")
    git = shutil.which("git")
    assert git is not None
    slow = tmp_path / "bin"
    slow.mkdir()
    _ = (slow / "git").write_text(
        f'#!/bin/sh\ncase " $* " in *" cat-file "*) exec sleep 60 ;; esac\nexec {shlex.quote(git)} "$@"\n',
        encoding="utf-8",
    )
    (slow / "git").chmod(0o755)
    monkeypatch.setenv("PATH", f"{slow}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(review_evidence, "_GIT_TIMEOUT_SECONDS", 0.5)

    with pytest.raises(subprocess.TimeoutExpired):
        review_evidence._extract_base(root, "HEAD", tmp_path)  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize("path", ["", "../x.py", "a/../../x.py", "/etc/x.py", "out/x.py"])
def test_a_base_path_that_leaves_the_target_is_refused(tmp_path: Path, path: str) -> None:
    target = tmp_path / "base"
    target.mkdir()
    (target / "out").symlink_to(tmp_path)

    assert review_evidence._inside(target, path) is None  # pyright: ignore[reportPrivateUsage]


def test_a_base_path_inside_the_target_is_kept(tmp_path: Path) -> None:
    destination = review_evidence._inside(tmp_path, "src/store.py")  # pyright: ignore[reportPrivateUsage]

    assert destination == tmp_path / "src" / "store.py"
