"""Cut-owned RED tracers for the approved wheypoint phase rehydration spec."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import cast


REPO_ROOT = Path(__file__).resolve().parents[2]
SLUG = "phase-rehydration-tracer"


def _env(root: Path, project: str = SLUG) -> dict[str, str]:
    return {
        "EASY_CHEESE_HOME": str(root / "cheese"),
        "EASY_CHEESE_PROJECT": project,
    }


def _run(
    bundle: str,
    *args: str,
    cwd: Path,
    env: dict[str, str],
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    isolated = dict(os.environ)
    _ = isolated.pop("PYTHONPATH", None)
    isolated.update(env)
    return subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "skills" / bundle / "scripts" / f"{bundle}.pyz"),
            *args,
        ],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=isolated,
        input=stdin,
    )


def _json(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return cast(dict[str, object], json.loads(result.stdout))


def _artifact(root: Path, phase: str, slug: str = SLUG) -> Path:
    return root / ".cheese" / phase / f"{slug}.md"


def _writer_args(
    phase: str, *, slug: str = SLUG, grounded: tuple[str, ...] = ()
) -> list[str]:
    following = {"cook": "age", "press": "age", "age": "cure", "cure": "age"}
    args = [
        "write-handoff-artifact",
        "--slug",
        slug,
        "--status",
        "ok",
        "--phase",
        phase,
        "--next",
        following[phase],
        "--artifact",
        "",
        "--orientation",
        f"{phase} phase handoff",
        "--root",
        "{root}",
    ]
    for entry in grounded:
        args.extend(("--grounded", entry))
    return args


def _write_args(root: Path, phase: str, *, slug: str = SLUG, grounded: tuple[str, ...] = ()) -> list[str]:
    return [arg if arg != "{root}" else str(root) for arg in _writer_args(phase, slug=slug, grounded=grounded)]


def _seed_git(root: Path) -> None:
    _ = (root / ".gitignore").write_text(".cheese/\n", encoding="utf-8")
    _ = (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    for args in (
        ("init", "--initial-branch=main", "."),
        ("config", "user.email", "test@example.com"),
        ("config", "user.name", "Test"),
        ("add", "-A"),
        ("commit", "-m", "seed"),
    ):
        _ = subprocess.run(["git", *args], cwd=str(root), check=True, capture_output=True, text=True)


def test_curd_1_shared_kernel_is_present_in_every_bundle(tmp_path: Path) -> None:
    out = tmp_path / "bundles"
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "build_pyz.py"), "--out-dir", str(out)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    archives = sorted(out.glob("*.pyz"))
    assert archives
    for archive in archives:
        with zipfile.ZipFile(archive) as bundle:
            members = set(bundle.namelist())
        assert any(
            name.startswith("site-packages/easy_cheese/shared/wheypoint/") for name in members
        ), archive.name
        old_kernel_modules = {
            f"site-packages/easy_cheese/skills/wheypoint/{module}.py"
            for module in (
                "canonical",
                "checkpoint",
                "commit",
                "legacy",
                "lineage",
                "lint",
                "projection",
                "records",
                "resolve",
                "storage",
            )
        }
        assert members.isdisjoint(old_kernel_modules), archive.name


def test_curd_2_chain_writes_revisions_and_validates_grounded_genesis(
    tmp_path: Path,
) -> None:
    attempts: dict[str, subprocess.CompletedProcess[str]] = {}
    for phase in ("cook", "press", "age", "cure"):
        root = tmp_path / phase
        root.mkdir()
        _ = (root / "context.md").write_text("grounded\n", encoding="utf-8")
        if phase == "age":
            _seed_git(root)
            lock = _run("age", "review-lock", "--slug", SLUG, "--root", str(root), cwd=root, env=_env(tmp_path / "age"))
            assert lock.returncode == 0, lock.stderr
        attempts[phase] = _run(
            phase,
            *_write_args(root, phase, grounded=("context.md#1-1",)),
            cwd=root,
            env=_env(tmp_path / phase, f"{SLUG}-{phase}"),
        )

    assert all(result.returncode == 0 for result in attempts.values()), {
        phase: result.stderr for phase, result in attempts.items()
    }
    for phase in attempts:
        root = tmp_path / phase
        target = _artifact(root, phase)
        assert target.is_file()
        shown = _run(
            "wheypoint",
            "show",
            "--work-id",
            SLUG,
            cwd=root,
            env=_env(tmp_path / phase, f"{SLUG}-{phase}"),
        )
        assert shown.returncode == 0, shown.stderr
        record = cast(dict[str, object], _json(shown)["record"])
        next_action = cast(dict[str, object], record["next_action"])
        assert Path(cast(str, next_action["artifact"])).name == target.name
        links = cast(list[dict[str, object]], record["artifact_links"])
        assert any(
            link.get("digest") == "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest()
            for link in links
        )

    genesis = tmp_path / "grounded-genesis"
    genesis.mkdir()
    env = _env(genesis, f"{SLUG}-grounded")
    no_grounded = _run("cook", *_write_args(genesis, "cook"), cwd=genesis, env=env)
    assert no_grounded.returncode != 0 and not _artifact(genesis, "cook").exists()

    _ = (genesis / "infra.tf").write_text("resource\n", encoding="utf-8")
    (genesis / "scripts").mkdir()
    _ = (genesis / "scripts" / "tf.sh").write_text("terraform\n", encoding="utf-8")
    entries = ("infra.tf#1-1", "scripts/tf.sh#1-1")
    grounded = _run("cook", *_write_args(genesis, "cook", grounded=entries), cwd=genesis, env=env)
    assert grounded.returncode == 0, grounded.stderr
    shown = _run("wheypoint", "show", "--work-id", SLUG, cwd=genesis, env=env)
    assert shown.returncode == 0, shown.stderr
    record = cast(dict[str, object], _json(shown)["record"])
    assert record["working_context"] == list(entries)

    carried = _run("cook", *_write_args(genesis, "cook"), cwd=genesis, env=env)
    assert carried.returncode == 0, carried.stderr
    carried_show = _run("wheypoint", "show", "--work-id", SLUG, cwd=genesis, env=env)
    assert carried_show.returncode == 0, carried_show.stderr
    carried_record = cast(dict[str, object], _json(carried_show)["record"])
    assert carried_record["working_context"] == list(entries)


def test_curd_3_resolves_phase_artifacts_and_reports_stale_inputs(tmp_path: Path) -> None:
    root = tmp_path / "fallback"
    root.mkdir()
    env = _env(root, f"{SLUG}-fallback")
    artifact = _artifact(root, "cook")
    artifact.parent.mkdir(parents=True)
    _ = artifact.write_text(
        "status: ok\nnext: press\nartifact: \nbare phase report\n",
        encoding="utf-8",
    )
    resolved = _json(_run("wheypoint", "resolve", "--ref", SLUG, cwd=root, env=env))

    phase_slug = cast(dict[str, object], resolved.get("phase_slug"))
    assert phase_slug["status"] == "ok"
    assert phase_slug["next"] == "press"
    assert resolved["outcome"] == "legacy"
    assert resolved["source"] == "phase-artifact"
    assert resolved["dispatchable"] is False

    notes = root / ".cheese" / "notes"
    notes.mkdir(parents=True)
    _ = (notes / f"{SLUG}.md").write_text(
        "status: ok\nnext: cook\nartifact: \nlegacy note\n", encoding="utf-8"
    )
    preferred = _json(_run("wheypoint", "resolve", "--ref", SLUG, cwd=root, env=env))
    assert preferred["outcome"] == "legacy" and preferred["source"] == "phase-artifact"

    lint_root = tmp_path / "lint"
    lint_root.mkdir()
    lint_env = _env(lint_root, f"{SLUG}-lint")
    context = lint_root / "context.md"
    linked = lint_root / "linked.md"
    _ = context.write_text("context\n", encoding="utf-8")
    _ = linked.write_text("original\n", encoding="utf-8")
    original_digest = "sha256:" + hashlib.sha256(linked.read_bytes()).hexdigest()
    intent: dict[str, object] = {
        "work_id": SLUG,
        "orientation": "lint inputs",
        "working_context": ["context.md#1-1"],
        "next": "cook",
        "artifact": ".cheese/cook/phase.md",
        "artifact_links": [{"path": "linked.md", "digest": original_digest, "covers_entry_ids": []}],
        "notes": "Lint record.",
    }
    checkpoint = _run(
        "wheypoint",
        "checkpoint",
        "--no-note",
        cwd=lint_root,
        env=lint_env,
        stdin=json.dumps(intent),
    )
    assert checkpoint.returncode == 0, checkpoint.stderr
    _ = context.unlink()
    _ = linked.write_text("edited\n", encoding="utf-8")
    checked = _run(
        "wheypoint",
        "resolve",
        "--ref",
        SLUG,
        cwd=lint_root,
        env=lint_env,
    )
    payload = _json(checked)
    codes = {cast(dict[str, str], item)["code"] for item in cast(list[object], payload["findings"])}
    assert {"stale-artifact-link", "grounded-path-missing"} <= codes

    carried = _run("cook", *_write_args(lint_root, "cook"), cwd=lint_root, env=lint_env)
    assert carried.returncode == 0, carried.stderr
    shown = _run("wheypoint", "show", "--work-id", SLUG, cwd=lint_root, env=lint_env)
    assert shown.returncode == 0, shown.stderr
    carried_record = cast(dict[str, object], _json(shown)["record"])
    assert carried_record["revision_number"] == 2
    assert carried_record["working_context"] == ["context.md#1-1"]


def test_curd_4_documents_entry_resolution_and_preserves_publication_guard(
    tmp_path: Path,
) -> None:
    phase_skills = ("cook", "press", "age", "cure", "plate")
    for phase in phase_skills:
        text = (REPO_ROOT / "skills" / phase / "SKILL.md").read_text(encoding="utf-8")
        assert f"{phase}.pyz wheypoint-resolve" in text
        assert all(word in text for word in ("authoritative", "not-found", "legacy", "gated", "ambiguous", "error"))
        assert re.search(
            r"working_context.{0,160}first.{0,160}tilth_read|first.{0,160}tilth_read.{0,160}working_context",
            text,
            re.IGNORECASE | re.DOTALL,
        )

    writer_docs = (
        REPO_ROOT / "skills" / "cook" / "SKILL.md",
        REPO_ROOT / "skills" / "press" / "SKILL.md",
        REPO_ROOT / "skills" / "age" / "SKILL.md",
        REPO_ROOT / "skills" / "cure" / "SKILL.md",
        REPO_ROOT / "skills" / "cook" / "references" / "commands.md",
        REPO_ROOT / "skills" / "age" / "references" / "commands.md",
        REPO_ROOT / "skills" / "cure" / "references" / "commands.md",
    )
    for path in writer_docs:
        text = path.read_text(encoding="utf-8")
        for match in re.finditer("write-handoff-artifact", text):
            assert "--grounded" in text[match.start() : match.start() + 500], path

    root = tmp_path / "guard"
    root.mkdir()
    env = _env(root, f"{SLUG}-guard")
    artifact_root = root / "published"
    publish = _run(
        "mold",
        "publish",
        str(REPO_ROOT / "tests" / "python" / "fixtures" / "cook_payloads" / "clean_writer_view.json"),
        "--invocation",
        str(REPO_ROOT / "tests" / "python" / "fixtures" / "cook_payloads" / "clean_invocation.json"),
        "--operation-id",
        "phase-rehydration-guard",
        "--artifact-root",
        str(artifact_root),
        cwd=root,
        env=env,
    )
    assert publish.returncode == 0, publish.stderr
    corpus = Path(env["EASY_CHEESE_HOME"]) / env["EASY_CHEESE_PROJECT"]
    assert not (corpus / "work").exists()
    manifest = cast(dict[str, object], json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text()))
    assert "hooks" not in manifest
