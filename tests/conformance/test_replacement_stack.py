from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from easy_cheese.shared.handoffs import canonical_bytes
from easy_cheese_schemas import _schema_catalog, contracts, schema_runtime
from scripts import check_bundles
from scripts import build_pyz
from tests.schemas.python.test_handoff_contracts import (
    repaired_writer_text,
    writer_and_invocation,
)


def test_worktree_layout_has_one_same_named_archive_per_python_skill():
    assert check_bundles.check_layout_currency(snapshot="worktree") == ()


def test_index_head_materialization_uses_the_requested_snapshot(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("head", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=tmp_path, check=True)
    tracked.write_text("index", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    tracked.write_text("worktree", encoding="utf-8")
    monkeypatch.setattr(check_bundles, "REPO_ROOT", tmp_path)

    with check_bundles.materialize_snapshot("HEAD") as head:
        assert (head / "tracked.txt").read_text() == "head"
    with check_bundles.materialize_snapshot("index") as index:
        assert (index / "tracked.txt").read_text() == "index"


def test_snapshot_extraction_falls_back_when_data_filter_is_unavailable(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    tracked = repo / "tracked.txt"
    tracked.write_text("safe", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    monkeypatch.setattr(check_bundles, "REPO_ROOT", repo)
    monkeypatch.setattr(tarfile, "data_filter", None, raising=False)

    with check_bundles.materialize_snapshot("HEAD") as snapshot:
        assert (snapshot / "tracked.txt").read_text() == "safe"


def test_snapshot_currency_ignores_worktree_only_layout_changes(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    scripts = repo / "skills" / "mold" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "mold.pyz").write_bytes(b"head")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)

    # The staged index receives a doctrine violation, while the worktree
    # removes it. Currency must inspect the selected tree, not live files.
    (scripts / "common.pyz").write_bytes(b"index")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    (scripts / "common.pyz").unlink()
    monkeypatch.setattr(check_bundles, "REPO_ROOT", repo)

    assert check_bundles.check_layout_currency(snapshot="HEAD") == ()
    assert check_bundles.check_layout_currency(snapshot="index") == (
        "skills/mold/scripts/common.pyz",
    )


def test_currency_rebuilds_from_selected_snapshot_not_live_sources(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    bundle_dir = repo / "skills" / "mold" / "scripts"
    scripts.mkdir(parents=True)
    bundle_dir.mkdir(parents=True)
    (repo / ".gitignore").write_text("/vendor/\n", encoding="utf-8")
    (repo / "marker.txt").write_text("head", encoding="utf-8")
    (scripts / "build_pyz.py").write_text(
        "import pathlib, sys, zipfile\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--out-dir') + 1]); out.mkdir(exist_ok=True)\n"
        "with zipfile.ZipFile(out / 'mold.pyz', 'w') as z:\n"
        "    z.writestr('marker', pathlib.Path('vendor/marker.txt').read_text())\n",
        encoding="utf-8",
    )
    (repo / "requirements-vendor.txt").write_text("snapshot-lock\n", encoding="utf-8")
    (scripts / "vendor_deps.py").write_text(
        "import pathlib\n"
        "vendor = pathlib.Path('vendor'); vendor.mkdir()\n"
        "(vendor / 'marker.txt').write_text('snapshot')\n",
        encoding="utf-8",
    )
    live_vendor = repo / "vendor"
    live_vendor.mkdir()
    (live_vendor / "marker.txt").write_text("live", encoding="utf-8")
    with zipfile.ZipFile(bundle_dir / "mold.pyz", "w") as archive:
        archive.writestr("marker", "snapshot")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)

    # Stage a coherent index snapshot, then make both source and bundle differ
    # only in the live worktree. A live rebuild would report stale; HEAD must be
    # green because its own source rebuild reproduces its committed archive.
    (repo / "marker.txt").write_text("index", encoding="utf-8")
    with zipfile.ZipFile(bundle_dir / "mold.pyz", "w") as archive:
        archive.writestr("marker", "snapshot")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    (repo / "marker.txt").write_text("worktree", encoding="utf-8")
    with zipfile.ZipFile(bundle_dir / "mold.pyz", "w") as archive:
        archive.writestr("marker", "worktree")
    monkeypatch.setattr(check_bundles, "REPO_ROOT", repo)

    assert check_bundles.main(["--against", "index"]) == 0


def test_currency_reports_snapshot_rebuild_oserror_without_secondary_failure(
    tmp_path, monkeypatch, capsys
):
    repo = tmp_path / "repo"
    scripts = repo / "skills" / "mold" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "mold.pyz").write_bytes(b"bundle")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    monkeypatch.setattr(check_bundles, "REPO_ROOT", repo)

    def fail(_root):
        raise OSError("rebuild unavailable")

    monkeypatch.setattr(check_bundles, "_rebuild_snapshot", fail)
    assert check_bundles.main(["--against", "head"]) == 1
    assert "could not rebuild selected snapshot bundles" in capsys.readouterr().out


def test_stale_shell_closure_removes_replaced_archives_and_modules():
    for skill in ("mold", "cook", "age", "cure"):
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (Path("skills") / skill).rglob("*.md")
        )
        assert "common.pyz" not in text
    assert not list(Path("skills").glob("*/scripts/common.pyz"))
    for shell in (
        Path("src/mold/contract.py"),
        Path("src/cook/contract.py"),
        Path(".claude/workflows/node-runner.js"),
    ):
        assert not shell.exists()


def test_selected_429_decorator_catalog_assertions_remain_green():
    marked = {
        value
        for value in vars(contracts).values()
        if isinstance(value, type) and getattr(value, "__contract_slug__", None)
    }
    registered = {entry.contract for entry in schema_runtime._REGISTERED_CONTRACTS}
    registered_uris = {
        f"{schema_runtime.SCHEMA_ROOT}/{model.__contract_slug__}" for model in marked
    }
    assert registered == marked
    assert _schema_catalog.REGISTERED_CONTRACT_SCHEMA_URIS == registered_uris


def test_full_bundle_only_mold_to_cook_conformance(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    mold = build_pyz.build_layout_bundle("mold", tmp_path / "mold.pyz")
    cook = build_pyz.build_layout_bundle("cook", tmp_path / "cook.pyz")
    writer_path = tmp_path / "writer.jsonish"
    invocation_path = tmp_path / "invocation.json"
    writer_path.write_text(repaired_writer_text(writer), encoding="utf-8")
    invocation_path.write_bytes(canonical_bytes(invocation.to_mapping()))
    environment = {"PATH": "", "PYTHONPATH": "/does/not/exist"}

    produced = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(mold.resolve()),
            "contract",
            "publish",
            "--writer-view",
            str(writer_path),
            "--invocation",
            str(invocation_path),
            "--operation-id",
            "replacement-stack",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert produced.returncode == 0, produced.stderr
    pointer_path = tmp_path / "pointers" / "replacement-stack.json"
    assert json.loads(produced.stdout) == json.loads(pointer_path.read_text())

    consumed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(cook.resolve()),
            "contract",
            "accept",
            "--pointer",
            str(pointer_path),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert consumed.returncode == 0, consumed.stderr
    assert json.loads(consumed.stdout)["plan_id"] == "plan-1"
