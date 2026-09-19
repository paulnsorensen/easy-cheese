"""Behavior tests for the scoped /age review-instructions helper."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.skills.age import review_instructions


def _sources(result: dict[str, object]) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", result["sources"])


def test_diff_scope_collects_nested_rules_and_preserves_scopes(tmp_path: Path) -> None:
    _ = (tmp_path / "AGENTS.md").write_text("root one\nroot two\n", encoding="utf-8")
    _ = (tmp_path / "CLAUDE.md").write_text("root one\nroot two\n", encoding="utf-8")
    nested = tmp_path / "src" / "pkg"
    nested.mkdir(parents=True)
    _ = (nested / "CLAUDE.local.md").write_text("nested\n", encoding="utf-8")
    _ = (nested / "changed.py").write_text("pass\n", encoding="utf-8")
    _ = (tmp_path / "README.md").write_text("readme\n", encoding="utf-8")

    result = review_instructions.collect_instructions(
        tmp_path,
        scope="diff",
        changed_paths=["src/pkg/changed.py", "README.md"],
        external_sources=[],
    )

    sources = _sources(result)
    assert [source["path"] for source in sources] == [
        "AGENTS.md",
        "CLAUDE.md",
        "src/pkg/CLAUDE.local.md",
    ]
    assert sources[0]["scope"] == ["README.md", "src/pkg/changed.py"]
    assert sources[2]["scope"] == ["src/pkg/changed.py"]
    assert sources[0]["authority"] == "candidate"
    assert sources[0]["content"] == "root one\nroot two\n"
    assert "1: root one\n2: root two\n" in review_instructions.render_text(result)
    expected_hash = "sha256:" + hashlib.sha256(b"root one\nroot two\n").hexdigest()
    assert sources[0]["content_hash"] == expected_hash
    # Equal bytes in two differently named sources remain two source identities.
    assert sources[0]["id"] != sources[1]["id"]


def test_overall_scope_prunes_vcs_vendor_and_cache_trees(tmp_path: Path) -> None:
    _ = (tmp_path / "AGENTS.md").write_text("root\n", encoding="utf-8")
    nested = tmp_path / "lib"
    nested.mkdir()
    _ = (nested / "CLAUDE.md").write_text("lib\n", encoding="utf-8")
    for excluded in (".git", "vendor", "node_modules", ".venv", ".claude/worktrees"):
        directory = tmp_path / excluded
        directory.mkdir(parents=True)
        _ = (directory / "AGENTS.md").write_text("must not collect\n", encoding="utf-8")
    for ordinary, filename in (("build", "CLAUDE.md"), ("env", "AGENTS.md")):
        directory = tmp_path / ordinary
        directory.mkdir()
        _ = (directory / filename).write_text("first-party rule\n", encoding="utf-8")

    result = review_instructions.collect_instructions(
        tmp_path,
        scope="overall",
        changed_paths=[],
        external_sources=[],
    )

    sources = _sources(result)
    assert [source["path"] for source in sources] == [
        "AGENTS.md",
        "build/CLAUDE.md",
        "env/AGENTS.md",
        "lib/CLAUDE.md",
    ]
    assert {
        source["path"]: source["scope"] for source in sources
    } == {
        "AGENTS.md": ["."],
        "build/CLAUDE.md": ["build"],
        "env/AGENTS.md": ["env"],
        "lib/CLAUDE.md": ["lib"],
    }


def test_explicit_external_sources_keep_alias_scopes_and_provenance(tmp_path: Path) -> None:
    external = tmp_path.parent / "host-instructions.md"
    _ = external.write_text("host rule\n", encoding="utf-8")
    _ = (tmp_path / "app.py").write_text("pass\n", encoding="utf-8")

    result = review_instructions.collect_instructions(
        tmp_path,
        scope="diff",
        changed_paths=["app.py"],
        external_sources=[
            {
                "path": str(external),
                "applies_to": ["app.py"],
                "provenance": "host-explicit",
            },
            {"path": str(external), "applies_to": ["docs"], "provenance": "host-explicit"},
        ],
    )

    sources = _sources(result)
    assert len(sources) == 2
    assert {tuple(cast(list[str], source["scope"])) for source in sources} == {
        ("app.py",),
        ("docs",),
    }
    assert {source["kind"] for source in sources} == {"external"}
    assert {source["provenance"] for source in sources} == {"host-explicit"}


def test_deleted_changed_path_still_collects_existing_ancestors(tmp_path: Path) -> None:
    nested = tmp_path / "removed" / "feature"
    nested.mkdir(parents=True)
    _ = (tmp_path / "AGENTS.md").write_text("root\n", encoding="utf-8")
    _ = (nested / "CLAUDE.md").write_text("feature\n", encoding="utf-8")

    result = review_instructions.collect_instructions(
        tmp_path,
        scope="diff",
        changed_paths=["removed/feature/deleted.py"],
        external_sources=[],
    )

    assert [source["path"] for source in _sources(result)] == [
        "AGENTS.md",
        "removed/feature/CLAUDE.md",
    ]


@pytest.mark.parametrize("setup", ["invalid-relative", "nonregular", "invalid-utf8", "unreadable"])
def test_source_boundaries_fail_loudly(tmp_path: Path, setup: str) -> None:
    if setup == "invalid-relative":
        with pytest.raises(review_instructions.InstructionCollectionError):
            _ = review_instructions.collect_instructions(
                tmp_path,
                scope="diff",
                changed_paths=["../outside.py"],
                external_sources=[],
            )
        return

    source = tmp_path / "CLAUDE.md"
    if setup == "nonregular":
        _ = source.mkdir()
    elif setup == "invalid-utf8":
        _ = source.write_bytes(b"bad\xff\n")
    else:
        _ = source.write_text("secret\n", encoding="utf-8")
        _ = source.chmod(0)

    try:
        with pytest.raises(review_instructions.InstructionCollectionError):
            _ = review_instructions.collect_instructions(
                tmp_path,
                scope="diff",
                changed_paths=["changed.py"],
                external_sources=[],
            )
    finally:
        _ = source.chmod(0o600)


def test_external_scope_must_be_repo_relative(tmp_path: Path) -> None:
    external = tmp_path.parent / "host-scope.md"
    _ = external.write_text("host rule\n", encoding="utf-8")

    with pytest.raises(review_instructions.InstructionCollectionError):
        _ = review_instructions.collect_instructions(
            tmp_path,
            scope="diff",
            changed_paths=[],
            external_sources=[{"path": str(external), "applies_to": ["../outside"]}],
        )

    with pytest.raises(review_instructions.InstructionCollectionError):
        _ = review_instructions.collect_instructions(
            tmp_path,
            scope="diff",
            changed_paths=[],
            external_sources=[{"path": str(external), "applies_to": []}],
        )


def test_symlink_escape_is_not_traversed(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-review-instructions.py"
    _ = outside.write_text("outside\n", encoding="utf-8")
    link = tmp_path / "escape"
    try:
        _ = link.symlink_to(outside)
    except (NotImplementedError, OSError):
        pytest.skip("symlinks are unavailable")

    with pytest.raises(review_instructions.InstructionCollectionError):
        _ = review_instructions.collect_instructions(
            tmp_path,
            scope="diff",
            changed_paths=["escape/file.py"],
            external_sources=[],
        )


def test_cli_accepts_json_path_and_text_mode(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _ = (tmp_path / "AGENTS.md").write_text("rule\n", encoding="utf-8")
    request = tmp_path / "request.json"
    _ = request.write_text(
        json.dumps(
            {
                "repo_root": str(tmp_path),
                "scope": "diff",
                "changed_paths": ["changed.py"],
                "external_sources": [],
            }
        ),
        encoding="utf-8",
    )

    assert review_instructions.main([str(request)]) == 0
    payload = cast("dict[str, object]", json.loads(capsys.readouterr().out))
    payload_sources = cast("list[dict[str, object]]", payload["sources"])
    assert payload["policy_version"] == "age-review-instructions.v1"
    assert payload_sources[0]["path"] == "AGENTS.md"

    assert review_instructions.main(["--text", str(request)]) == 0
    rendered = capsys.readouterr().out
    assert "authority: candidate" in rendered
    assert "1: rule" in rendered

    _ = request.write_text(
        json.dumps(
            {
                "repo_root": str(tmp_path),
                "scope": "diff",
                "changed_paths": ["../outside.py"],
                "external_sources": [],
            }
        ),
        encoding="utf-8",
    )
    assert review_instructions.main([str(request)]) == 1
    assert "ERROR:" in capsys.readouterr().err
