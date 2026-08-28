from __future__ import annotations

import base64
import contextlib
import importlib
from typing import Any
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import textwrap
import zipfile

import yaml

from scripts import check_bundles


ROOT = Path(__file__).parents[2]


def _roots(tmp_path: Path) -> tuple[Path, Path]:
    built = tmp_path / "built" / "skills" / "demo" / "scripts"
    baseline = tmp_path / "baseline" / "skills" / "demo" / "scripts"
    built.mkdir(parents=True)
    baseline.mkdir(parents=True)
    (built / "demo.pyz").write_bytes(b"built")
    (baseline / "demo.pyz").write_bytes(b"baseline")
    return built.parents[2], baseline.parents[2]


def test_local_pair_and_stale_bundle_are_distinguished(tmp_path, monkeypatch) -> None:
    built, baseline = _roots(tmp_path)
    monkeypatch.setattr(check_bundles, "_manifest", lambda data: {"payload": data})
    assert check_bundles._check_roots(built, built, require_baseline=True) == []
    problems = check_bundles._check_roots(built, baseline, require_baseline=True)
    assert any("content differs" in problem for problem in problems)


def test_index_comparison_reports_missing_and_new_expected_bundles(tmp_path) -> None:
    built = tmp_path / "built"
    baseline = tmp_path / "baseline"
    (built / "skills" / "demo" / "scripts").mkdir(parents=True)
    (baseline / "skills" / "old" / "scripts").mkdir(parents=True)
    (built / "skills" / "demo" / "scripts" / "demo.pyz").write_bytes(b"x")
    (baseline / "skills" / "old" / "scripts" / "old.pyz").write_bytes(b"x")
    problems = check_bundles._check_roots(built, baseline, require_baseline=True)
    assert any("expected bundle missing" in problem for problem in problems)
    assert any("not staged" in problem for problem in problems)


def test_local_check_is_not_head_based() -> None:
    justfile = (ROOT / "justfile").read_text()
    assert "check-bundles-local" not in justfile
    assert "check-bundles" in justfile
    assert "check_bundles_local.py" in justfile
    assert " bundle " not in justfile.split("check:", 1)[1].splitlines()[0]


def test_hook_scope_covers_bundle_inputs_and_archives() -> None:
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text())
    hook = config["repos"][0]["hooks"][0]
    assert hook["always_run"] is True
    trigger = re.compile(hook["files"])
    for path in (
        "src/easy_cheese/skills/demo/commands.py",
        "skills/demo/phase-contract.yaml",
        "skills/demo/scripts/demo.pyz",
        "requirements/runtime.txt",
        "requirements/bundles/demo.txt",
        "requirements-build.txt",
        "pyproject.toml",
    ):
        assert trigger.search(path), path



def test_bundle_build_commands_include_runtime_requirements() -> None:
    from scripts import check_bundles_local, precommit_bundle_currency

    for command in (check_bundles_local.BUILD_COMMAND, precommit_bundle_currency.BUILD_COMMAND):
        assert "requirements-build.txt" in command
        assert "requirements/runtime.txt" in command


def _bundle(marker: str) -> bytes:
    members = {
        "_bootstrap/__init__.py": b"",
        "_bootstrap/environment.py": b"",
        "_bootstrap/filelock.py": b"",
        "_bootstrap/interpreter.py": b"",
        "__main__.py": b"",
        "site-packages/demo.py": marker.encode(),
        "site-packages/demo-1.dist-info/RECORD": b"demo.py,,\\n",
    }
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    with zipfile.ZipFile(io.BytesIO(raw.getvalue())) as archive:
        build_id = check_bundles._site_packages_hash(
            archive, normalize_wrappers=False, include_record=True
        )
    with zipfile.ZipFile(raw, "a") as archive:
        archive.writestr(
            "environment.json",
            ('{"build_id": "' + build_id + '"}').encode(),
        )
    return raw.getvalue()


def _repo(tmp_path: Path, *, source: str, artifact: bytes) -> tuple[Path, dict[str, str]]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "src").mkdir()
    (repo / "src" / "input.py").write_text(source)
    bundle = repo / "skills" / "demo" / "scripts"
    bundle.mkdir(parents=True)
    (bundle / "demo.pyz").write_bytes(artifact)
    (repo / "scripts").mkdir()
    for name in ("check_bundles.py", "check_bundles_local.py", "precommit_bundle_currency.py"):
        shutil.copy2(ROOT / "scripts" / name, repo / "scripts" / name)
    builder = repo / "fake_builder.py"
    encoded = {key: base64.b64encode(value).decode() for key, value in {
        "one": _bundle("one"), "two": _bundle("two")
    }.items()}
    builder.write_text(textwrap.dedent(f"""        import base64
        from pathlib import Path
        if Path("link.py").exists():
            assert Path("link.py").is_symlink()
        source = Path("src/input.py").read_text().strip()
        data = base64.b64decode({encoded!r}[source])
        target = Path("skills/demo/scripts/demo.pyz")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    """))
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
    return repo, os.environ.copy()


def _run(repo: Path, script: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    module: Any = importlib.import_module(f"scripts.{script}")
    module.REPO_ROOT = repo
    module.BUILD_COMMAND = (sys.executable, str(repo / "fake_builder.py"))
    previous = os.environ.get("GIT_INDEX_FILE")
    if "GIT_INDEX_FILE" in env:
        os.environ["GIT_INDEX_FILE"] = env["GIT_INDEX_FILE"]
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            returncode = module.main()
    finally:
        if previous is None:
            os.environ.pop("GIT_INDEX_FILE", None)
        else:
            os.environ["GIT_INDEX_FILE"] = previous
    return subprocess.CompletedProcess([], returncode, stdout.getvalue(), stderr.getvalue())


def _stage(repo: Path, *paths: str, env: dict[str, str]) -> None:
    subprocess.run(["git", "add", *paths], cwd=repo, env=env, check=True)


def test_precommit_staged_source_and_matching_artifact_pass(tmp_path) -> None:
    repo, env = _repo(tmp_path, source="one", artifact=_bundle("one"))
    (repo / "src/input.py").write_text("two")
    (repo / "skills/demo/scripts/demo.pyz").write_bytes(_bundle("two"))
    _stage(repo, "src/input.py", "skills/demo/scripts/demo.pyz", env=env)
    result = _run(repo, "precommit_bundle_currency", env)
    assert result.returncode == 0, result.stderr


def test_precommit_staged_source_without_regenerated_artifact_fails(tmp_path) -> None:
    repo, env = _repo(tmp_path, source="one", artifact=_bundle("one"))
    (repo / "src/input.py").write_text("two")
    _stage(repo, "src/input.py", env=env)
    result = _run(repo, "precommit_bundle_currency", env)
    assert result.returncode != 0


def test_precommit_ignores_unstaged_worktree_edits(tmp_path) -> None:
    repo, env = _repo(tmp_path, source="one", artifact=_bundle("one"))
    (repo / "src/input.py").write_text("two")
    (repo / "skills/demo/scripts/demo.pyz").write_bytes(_bundle("two"))
    _stage(repo, "src/input.py", "skills/demo/scripts/demo.pyz", env=env)
    (repo / "src/input.py").write_text("one")
    result = _run(repo, "precommit_bundle_currency", env)
    assert result.returncode == 0, result.stderr


def test_precommit_detects_staged_bundle_deletion(tmp_path) -> None:
    repo, env = _repo(tmp_path, source="one", artifact=_bundle("one"))
    (repo / "skills/demo/scripts/demo.pyz").unlink()
    _stage(repo, "skills/demo/scripts/demo.pyz", env=env)
    result = _run(repo, "precommit_bundle_currency", env)
    assert result.returncode != 0


def test_precommit_honors_alternate_git_index(tmp_path) -> None:
    repo, env = _repo(tmp_path, source="one", artifact=_bundle("one"))
    default_env = os.environ.copy()
    (repo / "src/input.py").write_text("two")
    _stage(repo, "src/input.py", env=default_env)

    alternate = repo / "alternate-index"
    env["GIT_INDEX_FILE"] = str(alternate)
    subprocess.run(["git", "read-tree", "HEAD"], cwd=repo, env=env, check=True)
    (repo / "skills/demo/scripts/demo.pyz").write_bytes(_bundle("two"))
    _stage(repo, "src/input.py", "skills/demo/scripts/demo.pyz", env=env)

    assert _run(repo, "precommit_bundle_currency", default_env).returncode != 0
    assert _run(repo, "precommit_bundle_currency", env).returncode == 0


def test_local_matching_and_stale_artifact(tmp_path) -> None:
    repo, env = _repo(tmp_path, source="one", artifact=_bundle("one"))
    result = _run(repo, "check_bundles_local", env)
    assert result.returncode == 0, result.stderr
    (repo / "src/input.py").write_text("two")
    result = _run(repo, "check_bundles_local", env)
    assert result.returncode != 0


def test_local_materialization_preserves_symlinks(tmp_path) -> None:
    repo, env = _repo(tmp_path, source="one", artifact=_bundle("one"))
    (repo / "link.py").symlink_to("src/input.py")
    _stage(repo, "link.py", env=env)
    result = _run(repo, "check_bundles_local", env)
    assert result.returncode == 0, result.stderr


def test_hook_uses_staged_diff_for_deletion_paths(monkeypatch) -> None:
    from scripts import precommit_bundle_currency

    monkeypatch.setattr(precommit_bundle_currency, "REPO_ROOT", Path("."))
    monkeypatch.setattr(
        precommit_bundle_currency.subprocess,
        "check_output",
        lambda *args, **kwargs: (
            b"skills/demo/scripts/demo.pyz"
            + bytes((0,))
            + b"src/name"
            + bytes((10,))
            + b"with-newline.py"
            + bytes((0,))
        ),
    )
    assert precommit_bundle_currency._staged_inputs() == [
        "skills/demo/scripts/demo.pyz",
        "src/name" + chr(10) + "with-newline.py",
    ]