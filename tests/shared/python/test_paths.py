"""Tests for shared/scripts/paths.py — slug validation and artifact paths."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest


class TestValidateSlug:
    @pytest.mark.parametrize(
        "slug",
        ["a", "feature", "fix-auth-retry", "x1", "abc-123-def", "a" * 64],
    )
    def test_accepts_valid_kebab(self, paths: ModuleType, slug: str) -> None:
        assert paths.validate_slug(slug) is None

    @pytest.mark.parametrize(
        "slug",
        [
            "",  # empty
            "-leading",  # leading hyphen
            "trailing-",  # trailing hyphen
            "double--hyphen",  # double hyphen
            "UPPER",  # uppercase
            "with space",  # whitespace
            "with_underscore",
            "a" * 65,  # too long
            "snake_case",
        ],
    )
    def test_rejects_invalid(self, paths: ModuleType, slug: str) -> None:
        assert paths.validate_slug(slug) is not None

    def test_non_string_rejected(self, paths: ModuleType) -> None:
        assert paths.validate_slug(None) is not None  # type: ignore[arg-type]
        assert paths.validate_slug(42) is not None  # type: ignore[arg-type]


@pytest.fixture
def xdg_corpus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Pin the per-project corpus to a deterministic tmp location.

    Sets EASY_CHEESE_HOME + EASY_CHEESE_PROJECT so resolution never shells out
    to git, and returns the project corpus root (``<home>/<project>``).
    """
    home = tmp_path / "corpus-home"
    monkeypatch.setenv("EASY_CHEESE_HOME", str(home))
    monkeypatch.setenv("EASY_CHEESE_PROJECT", "owner-repo")
    return home / "owner-repo"


class TestArtifactPath:
    def test_builds_canonical_path(self, paths: ModuleType) -> None:
        result = paths.artifact_path("age", "fix-auth-retry")
        assert result == Path(".cheese/age/fix-auth-retry.md")

    def test_custom_root(self, paths: ModuleType, tmp_path: Path) -> None:
        result = paths.artifact_path("cure", "demo", root=tmp_path)
        assert result == tmp_path / "cure" / "demo.md"

    def test_transient_phase_stays_repo_local(
        self, paths: ModuleType, xdg_corpus: Path
    ) -> None:
        # Even with the XDG corpus pinned, transient phases stay under .cheese/.
        assert paths.artifact_path("cook", "demo") == Path(".cheese/cook/demo.md")

    @pytest.mark.parametrize("phase", ["specs", "research"])
    def test_durable_phase_root_anchors_at_xdg_corpus(
        self, paths: ModuleType, xdg_corpus: Path, phase: str
    ) -> None:
        # Durable phases route their root to the per-project XDG corpus.
        assert paths.default_root_for_phase(phase) == xdg_corpus

    def test_spec_artifact_is_flat_under_corpus(
        self, paths: ModuleType, xdg_corpus: Path
    ) -> None:
        # specs/<slug>.md is flat. Research long-form uses a nested
        # research/<slug>/<slug>.md layout composed by /briesearch from
        # project_corpus_root(), not from this flat helper.
        assert paths.artifact_path("specs", "demo") == xdg_corpus / "specs" / "demo.md"

    def test_rejects_unknown_phase(self, paths: ModuleType) -> None:
        with pytest.raises(ValueError, match="unknown phase"):
            paths.artifact_path("bogus", "fix-x")

    def test_rejects_bad_slug(self, paths: ModuleType) -> None:
        with pytest.raises(ValueError, match="kebab-case"):
            paths.artifact_path("age", "Bad_Slug")


class TestCorpusResolution:
    def test_xdg_data_home_env(
        self, paths: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("EASY_CHEESE_HOME", raising=False)
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        assert paths.corpus_home() == tmp_path / "cheese"

    def test_xdg_data_home_ignores_relative(
        self, paths: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Per the spec, a non-absolute XDG value is ignored for the default.
        monkeypatch.setenv("XDG_DATA_HOME", "relative/path")
        assert paths.xdg_data_home() == Path.home() / ".local" / "share"

    def test_easy_cheese_home_overrides_xdg(
        self, paths: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", "/should/be/ignored")
        monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path / "override"))
        assert paths.corpus_home() == tmp_path / "override"

    def test_easy_cheese_home_ignores_relative(
        self, paths: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # A relative override is ignored, matching the XDG convention.
        monkeypatch.delenv("EASY_CHEESE_HOME", raising=False)
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        monkeypatch.setenv("EASY_CHEESE_HOME", "relative/corpus")
        assert paths.corpus_home() == tmp_path / "cheese"

    def test_project_key_override(
        self, paths: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EASY_CHEESE_PROJECT", "My Repo!!")
        assert paths.project_key() == "my-repo"


class TestSlugFromRemote:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("git@github.com:owner/repo.git", "owner/repo"),
            ("https://github.com/owner/repo.git", "owner/repo"),
            ("https://github.com/owner/repo", "owner/repo"),
            ("ssh://git@host.example.com/owner/repo.git", "owner/repo"),
            ("https://user:tok@host/proxy/prefix/owner/repo", "owner/repo"),
            ("https://gitlab.com/group/subgroup/repo.git", "subgroup/repo"),
        ],
    )
    def test_extracts_owner_repo(
        self, paths: ModuleType, url: str, expected: str
    ) -> None:
        assert paths._slug_from_remote(url) == expected
