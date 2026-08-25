from __future__ import annotations

import json
import subprocess
import sys
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

    assert (check_bundles.materialize_snapshot("HEAD") / "tracked.txt").read_text() == "head"
    assert (check_bundles.materialize_snapshot("index") / "tracked.txt").read_text() == "index"


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
