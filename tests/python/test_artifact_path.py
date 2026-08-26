"""Behavioral contract for easy_cheese.shared.artifact_path.

Pins path resolution, phase-directory remapping, slug validation, corpus-root
derivation from the environment, and the CLI wrapper's exit codes. artifact_path
never touches the filesystem, so these assert on returned/printed paths only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from easy_cheese.shared import artifact_path as ap


def test_non_xdg_phase_resolves_under_cheese() -> None:
    assert ap.artifact_path("cook", "my-slug") == Path(".cheese/cook/my-slug.md")


def test_hard_phase_remaps_directory() -> None:
    assert ap.artifact_path("hard", "my-slug") == Path(".cheese/hard-cheese/my-slug.md")


def test_xdg_phase_resolves_under_corpus_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path))
    monkeypatch.setenv("EASY_CHEESE_PROJECT", "proj")
    assert ap.artifact_path("specs", "s") == tmp_path / "proj" / "specs" / "s.md"


def test_unknown_phase_raises() -> None:
    with pytest.raises(ValueError, match="unknown phase"):
        ap.artifact_path("bogus", "my-slug")


@pytest.mark.parametrize(
    "slug",
    ["", "Bad", "-lead", "trail-", "dou--ble", "a" * 65, "has/slash", "has space"],
)
def test_invalid_slug_raises(slug: str) -> None:
    with pytest.raises(ValueError, match="kebab-case"):
        ap.artifact_path("cook", slug)


@pytest.mark.parametrize("slug", ["a", "a" * 64, "a-b-c", "phase-1"])
def test_valid_slug_accepted(slug: str) -> None:
    assert ap.artifact_path("cook", slug) == Path(f".cheese/cook/{slug}.md")


def test_corpus_root_uses_easy_cheese_home_verbatim(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # EASY_CHEESE_HOME is used as-is; unlike the XDG/home fallbacks it gets no
    # trailing "cheese" component appended.
    monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path))
    monkeypatch.setenv("EASY_CHEESE_PROJECT", "proj")
    assert ap.project_corpus_root() == tmp_path / "proj"


def test_corpus_home_falls_back_to_xdg_data_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("EASY_CHEESE_HOME", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("EASY_CHEESE_PROJECT", "proj")
    assert ap.project_corpus_root() == tmp_path / "cheese" / "proj"


def test_project_key_sanitizes_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EASY_CHEESE_HOME", "/abs/home")
    monkeypatch.setenv("EASY_CHEESE_PROJECT", "My Proj!")
    assert ap.project_corpus_root() == Path("/abs/home/my-proj")


def test_main_prints_resolved_path(capsys: pytest.CaptureFixture[str]) -> None:
    assert ap.main(["cook", "my-slug"]) == 0
    out = capsys.readouterr().out.strip()
    assert out == str(Path(".cheese/cook/my-slug.md"))


def test_main_reports_error_on_bad_slug(capsys: pytest.CaptureFixture[str]) -> None:
    assert ap.main(["cook", "Bad"]) == 1
    assert "error:" in capsys.readouterr().err


def test_main_research_prints_corpus_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path))
    monkeypatch.setenv("EASY_CHEESE_PROJECT", "proj")
    assert ap.main(["research", "ignored-slug"]) == 0
    assert capsys.readouterr().out.strip() == str(tmp_path / "proj")
