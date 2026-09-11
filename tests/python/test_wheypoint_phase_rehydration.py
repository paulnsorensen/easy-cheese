"""Cut-owned RED tracers for the approved wheypoint phase rehydration spec."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest
from attrs import evolve
from easy_cheese_schemas import (
    SCHEMA_VERSION,
    Durability,
    NextAction,
    NextMove,
    RepositoryProvenance,
    WheypointRecord,
    WheypointRevision,
)

from easy_cheese.shared.git_utils import run_git
from easy_cheese.shared.wheypoint import canonical, projection, records, storage


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


def _write_args(
    root: Path, phase: str, *, slug: str = SLUG, grounded: tuple[str, ...] = ()
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
        str(root),
    ]
    for entry in grounded:
        args.extend(("--grounded", entry))
    return args


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
        result = run_git(list(args), cwd=root)
        assert result.returncode == 0, result.stderr


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
            lock = _run(
                "age",
                "review-lock",
                "--slug",
                SLUG,
                "--root",
                str(root),
                cwd=root,
                env=_env(tmp_path / "age"),
            )
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
        assert next_action["artifact"] == f".cheese/{phase}/{SLUG}.md"
        links = cast(list[dict[str, object]], record["artifact_links"])
        assert any(
            link.get("digest")
            == "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest()
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
    grounded = _run(
        "cook", *_write_args(genesis, "cook", grounded=entries), cwd=genesis, env=env
    )
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


def test_curd_3_resolves_phase_artifacts_and_reports_stale_inputs(
    tmp_path: Path,
) -> None:
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

    order_root = tmp_path / "order"
    order_root.mkdir()
    order_env = _env(order_root, f"{SLUG}-order")
    order_slug = f"{SLUG}-order"
    for phase in ("cure", "age", "press", "cook"):
        target = _artifact(order_root, phase, slug=order_slug)
        target.parent.mkdir(parents=True)
        _ = target.write_text(
            f"status: ok\nnext: press\nartifact: \n{phase} orientation marker\n",
            encoding="utf-8",
        )
    for phase in ("cure", "age", "press", "cook"):
        found = _json(
            _run(
                "wheypoint",
                "resolve",
                "--ref",
                order_slug,
                cwd=order_root,
                env=order_env,
            )
        )
        assert found["outcome"] == "legacy"
        assert found["source"] == "phase-artifact"
        found_slug = cast(dict[str, object], found["phase_slug"])
        assert phase in cast(str, found_slug["orientation"])
        _artifact(order_root, phase, slug=order_slug).unlink()

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
        "artifact_links": [
            {"path": "linked.md", "digest": original_digest, "covers_entry_ids": []}
        ],
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
    codes = {
        cast(dict[str, str], item)["code"]
        for item in cast(list[object], payload["findings"])
    }
    assert {"stale-artifact-link", "grounded-path-missing"} <= codes
    assert payload["outcome"] == "gated"
    assert payload["dispatchable"] is False

    carried = _run("cook", *_write_args(lint_root, "cook"), cwd=lint_root, env=lint_env)
    assert carried.returncode == 0, carried.stderr
    shown = _run("wheypoint", "show", "--work-id", SLUG, cwd=lint_root, env=lint_env)
    assert shown.returncode == 0, shown.stderr
    carried_record = cast(dict[str, object], _json(shown)["record"])
    assert carried_record["revision_number"] == 2
    assert carried_record["working_context"] == ["context.md#1-1"]


def test_curd_3b_grounded_path_missing_alone_stays_authoritative(
    tmp_path: Path,
) -> None:
    lint_root = tmp_path / "lint-alone"
    lint_root.mkdir()
    lint_env = _env(lint_root, f"{SLUG}-lint-alone")
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
        "artifact_links": [
            {"path": "linked.md", "digest": original_digest, "covers_entry_ids": []}
        ],
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
    checked = _run(
        "wheypoint",
        "resolve",
        "--ref",
        SLUG,
        cwd=lint_root,
        env=lint_env,
    )
    payload = _json(checked)
    codes = {
        cast(dict[str, str], item)["code"]
        for item in cast(list[object], payload["findings"])
    }
    assert codes == {"grounded-path-missing"}
    assert payload["outcome"] == "authoritative"
    assert payload["dispatchable"] is True


PHASE_SKILLS = ("cook", "press", "age", "cure", "plate")


def _resolve(
    phase: str, ref: str, *, cwd: Path, env: dict[str, str]
) -> dict[str, object]:
    return _json(_run(phase, "wheypoint-resolve", "--ref", ref, cwd=cwd, env=env))


def _seed_ambiguous_slug(corpus_root: Path, slug: str, project_key: str) -> None:
    """Two work ids answering to `slug` in one corpus, the ambiguity itself."""
    placeholder_digest = "sha256:" + "0" * 64
    for suffix in ("a", "b"):
        work_id = f"{slug}-{suffix}"
        record = WheypointRecord(
            schema_version=SCHEMA_VERSION,
            work_id=work_id,
            slug=slug,
            title=slug,
            created="2026-08-02T00:00:00Z",
            project_key=project_key,
            revision_id="rev-0001",
            revision_number=1,
            revision_digest=placeholder_digest,
            orientation="ambiguous seed",
            working_context=[],
            next_action=NextAction(move=NextMove.COOK, orientation="proceed"),
            decisions=[],
            questions=[],
            blockers=[],
            artifact_links=[],
            decision_dossier=[],
        )
        projected, markdown = projection.build_projection(
            record, durability=Durability.CANONICAL_LOCAL
        )
        revision = WheypointRevision(
            schema_version=SCHEMA_VERSION,
            work_id=work_id,
            parent_revision_id=None,
            parent_revision_digest=None,
            revision_id=record.revision_id,
            revision_number=record.revision_number,
            request_digest=canonical.digest_text(f"seed-{work_id}"),
            record_digest=records.record_digest(record),
            applied_additions=[],
            applied_transitions=[],
            preserved_entry_ids=[],
            projection_path=f"projections/{record.revision_number}-{record.revision_id}.md",
            projection_digest=projected.projection_digest,
            repository=RepositoryProvenance(
                branch="claude/wheypoint", commit="abc1234"
            ),
        )
        seeded = evolve(record, revision_digest=records.revision_digest(revision))
        storage.WorkStore.open(work_id, corpus_root=corpus_root).promote(
            seeded, revision, markdown
        )


@pytest.mark.parametrize("phase", PHASE_SKILLS)
def test_curd_4b_resolves_entry_outcomes_per_phase_bundle(
    phase: str, tmp_path: Path
) -> None:
    slug = f"{SLUG}-{phase}"

    not_found_root = tmp_path / "not-found"
    not_found_root.mkdir()
    not_found_env = _env(not_found_root, f"{slug}-not-found")
    not_found = _resolve(
        phase, "nonexistent-slug-xyz", cwd=not_found_root, env=not_found_env
    )
    assert not_found["outcome"] == "not-found"

    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir()
    legacy_env = _env(legacy_root, f"{slug}-legacy")
    legacy_artifact = _artifact(legacy_root, "cook", slug=slug)
    legacy_artifact.parent.mkdir(parents=True)
    _ = legacy_artifact.write_text(
        "status: ok\nnext: press\nartifact: \nbare phase report\n",
        encoding="utf-8",
    )
    legacy = _resolve(phase, slug, cwd=legacy_root, env=legacy_env)
    assert legacy["outcome"] == "legacy"
    assert legacy["source"] == "phase-artifact"

    ambiguous_root = tmp_path / "ambiguous"
    ambiguous_root.mkdir()
    ambiguous_env = _env(ambiguous_root, f"{slug}-ambiguous")
    ambiguous_corpus = (
        Path(ambiguous_env["EASY_CHEESE_HOME"]) / ambiguous_env["EASY_CHEESE_PROJECT"]
    )
    _seed_ambiguous_slug(ambiguous_corpus, slug, ambiguous_env["EASY_CHEESE_PROJECT"])
    ambiguous = _resolve(phase, slug, cwd=ambiguous_root, env=ambiguous_env)
    assert ambiguous["outcome"] == "ambiguous"
    assert ambiguous["dispatchable"] is False

    gated_root = tmp_path / "gated"
    gated_root.mkdir()
    gated_env = _env(gated_root, f"{slug}-gated")
    context = gated_root / "context.md"
    linked = gated_root / "linked.md"
    _ = context.write_text("context\n", encoding="utf-8")
    _ = linked.write_text("original\n", encoding="utf-8")
    original_digest = "sha256:" + hashlib.sha256(linked.read_bytes()).hexdigest()
    gated_intent: dict[str, object] = {
        "work_id": slug,
        "orientation": "lint inputs",
        "working_context": ["context.md#1-1"],
        "next": "cook",
        "artifact": ".cheese/cook/phase.md",
        "artifact_links": [
            {"path": "linked.md", "digest": original_digest, "covers_entry_ids": []}
        ],
        "notes": "Lint record.",
    }
    checkpoint = _run(
        "wheypoint",
        "checkpoint",
        "--no-note",
        cwd=gated_root,
        env=gated_env,
        stdin=json.dumps(gated_intent),
    )
    assert checkpoint.returncode == 0, checkpoint.stderr
    _ = linked.write_text("edited\n", encoding="utf-8")
    gated = _resolve(phase, slug, cwd=gated_root, env=gated_env)
    codes = {
        cast(dict[str, str], item)["code"]
        for item in cast(list[object], gated["findings"])
    }
    assert "stale-artifact-link" in codes
    assert gated["outcome"] == "gated"
    assert gated["dispatchable"] is False

    authoritative_root = tmp_path / "authoritative"
    authoritative_root.mkdir()
    authoritative_env = _env(authoritative_root, f"{slug}-authoritative")
    if phase == "plate":
        auth_intent: dict[str, object] = {
            "work_id": slug,
            "orientation": "plate genesis",
            "working_context": [],
            "next": "cook",
            "artifact": ".cheese/cook/phase.md",
            "notes": "Plate genesis record.",
        }
        genesis = _run(
            "wheypoint",
            "checkpoint",
            "--no-note",
            cwd=authoritative_root,
            env=authoritative_env,
            stdin=json.dumps(auth_intent),
        )
        assert genesis.returncode == 0, genesis.stderr
    else:
        _ = (authoritative_root / "context.md").write_text(
            "grounded\n", encoding="utf-8"
        )
        if phase == "age":
            _seed_git(authoritative_root)
            lock = _run(
                "age",
                "review-lock",
                "--slug",
                slug,
                "--root",
                str(authoritative_root),
                cwd=authoritative_root,
                env=authoritative_env,
            )
            assert lock.returncode == 0, lock.stderr
        genesis = _run(
            phase,
            *_write_args(
                authoritative_root, phase, slug=slug, grounded=("context.md#1-1",)
            ),
            cwd=authoritative_root,
            env=authoritative_env,
        )
        assert genesis.returncode == 0, genesis.stderr
    authoritative = _resolve(phase, slug, cwd=authoritative_root, env=authoritative_env)
    assert authoritative["outcome"] == "authoritative"
    assert authoritative["dispatchable"] is True


@pytest.mark.parametrize("phase", PHASE_SKILLS)
def test_curd_4c_resolves_error_outcome_per_phase_bundle(
    phase: str, tmp_path: Path
) -> None:
    root = tmp_path / "error"
    root.mkdir()
    env = _env(root, f"{SLUG}-{phase}-error")
    result = _run(phase, "wheypoint-resolve", "--ref", "", cwd=root, env=env)
    payload = _json(result)
    assert payload["outcome"] == "error"
    assert payload["ok"] is False
    assert result.returncode == 1, result.stderr


PHASE_ENTRY_OUTCOMES = (
    "authoritative",
    "not-found",
    "legacy",
    "gated",
    "ambiguous",
    "error",
)

ENTRY_SKILLS = ("cook", "press", "age", "cure", "plate", "affinage")

WRITER_DOCS = tuple(
    REPO_ROOT / "skills" / phase / part
    for phase in ("cook", "press", "age", "cure")
    for part in ("SKILL.md", "references/commands.md")
)


def _phase_entry_section(phase: str) -> str:
    lines = (
        (REPO_ROOT / "skills" / phase / "SKILL.md")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert "## Phase entry" in lines, phase
    start = lines.index("## Phase entry")
    for offset, line in enumerate(lines[start + 1 :], start=start + 1):
        if line.startswith("## "):
            return "\n".join(lines[start:offset])
    return "\n".join(lines[start:])


def _command_blocks(text: str) -> list[str]:
    """Fenced code blocks and blank-line-delimited paragraphs, in file order."""
    blocks: list[str] = []
    current: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.startswith("```"):
            if fenced:
                current.append(line)
                blocks.append("\n".join(current))
                current = []
            else:
                if current:
                    blocks.append("\n".join(current))
                current = [line]
            fenced = not fenced
            continue
        if not fenced and not line.strip():
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


@pytest.mark.parametrize("phase", ENTRY_SKILLS)
def test_curd_4_phase_skill_documents_wheypoint_resolve_entry(phase: str) -> None:
    section = _phase_entry_section(phase)
    assert f"skills/{phase}/scripts/{phase}.pyz wheypoint-resolve" in section, phase
    for outcome in PHASE_ENTRY_OUTCOMES:
        assert f"`{outcome}`" in section, (phase, outcome)
    assert "`working_context` is the first batched `tilth_read`" in section, phase


@pytest.mark.parametrize(
    "doc",
    WRITER_DOCS,
    ids=[str(doc.relative_to(REPO_ROOT)) for doc in WRITER_DOCS],
)
def test_curd_4_writer_docs_pair_grounded_with_every_handoff_command(doc: Path) -> None:
    blocks = [
        block
        for block in _command_blocks(doc.read_text(encoding="utf-8"))
        if "write-handoff-artifact" in block
    ]
    assert blocks, doc
    for block in blocks:
        assert "--grounded" in block, (doc, block)


def test_curd_4_mold_publication_creates_no_wheypoint_revision(tmp_path: Path) -> None:
    root = tmp_path / "guard"
    root.mkdir()
    env = _env(root, f"{SLUG}-guard")
    artifact_root = root / "published"
    publish = _run(
        "mold",
        "publish",
        str(
            REPO_ROOT
            / "tests"
            / "python"
            / "fixtures"
            / "cook_payloads"
            / "clean_writer_view.json"
        ),
        "--invocation",
        str(
            REPO_ROOT
            / "tests"
            / "python"
            / "fixtures"
            / "cook_payloads"
            / "clean_invocation.json"
        ),
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


def test_curd_4_plugin_manifest_declares_no_hooks() -> None:
    manifest = cast(
        dict[str, object],
        json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text()),
    )
    assert "hooks" not in manifest
