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


class TestSlugify:
    def test_basic_conversion(self, paths: ModuleType) -> None:
        assert paths.slugify("Fix Auth Retry Bug") == "fix-auth-retry-bug"

    def test_drops_stopwords(self, paths: ModuleType) -> None:
        # "of", "the", "to" are stopwords; "rate" and "limit" survive.
        result = paths.slugify("Add rate limit to the API")
        assert result == "add-rate-limit-api"

    def test_strips_punctuation(self, paths: ModuleType) -> None:
        result = paths.slugify("Don't break!!! User-facing API.")
        assert result == "dont-break-user-facing-api"

    def test_caps_word_count(self, paths: ModuleType) -> None:
        result = paths.slugify("one two three four five six seven", max_words=3)
        assert result == "one-two-three"

    def test_caps_length_at_64(self, paths: ModuleType) -> None:
        # 20 long words; should still slug to <=64 chars.
        result = paths.slugify(" ".join(["alpha"] * 20))
        assert len(result) <= 64
        # And must round-trip through the validator.
        assert paths.validate_slug(result) is None


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
    def test_durable_phase_anchors_at_xdg_corpus(
        self, paths: ModuleType, xdg_corpus: Path, phase: str
    ) -> None:
        result = paths.artifact_path(phase, "demo")
        assert result == xdg_corpus / phase / "demo.md"

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

    def test_project_key_override(
        self, paths: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EASY_CHEESE_PROJECT", "My Repo!!")
        assert paths.project_key() == "my-repo"

    def test_config_path_layout(self, paths: ModuleType, xdg_corpus: Path) -> None:
        # xdg_corpus pins EASY_CHEESE_PROJECT=owner-repo.
        result = paths.project_config_path()
        assert result.parts[-3:] == ("cheese", "owner-repo", "config.toml")


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


class TestParseArtifactPath:
    def test_round_trip(self, paths: ModuleType) -> None:
        original = paths.artifact_path("press", "demo-slug")
        phase, slug = paths.parse_artifact_path(original)
        assert phase == "press"
        assert slug == "demo-slug"

    def test_round_trip_xdg_corpus(
        self, paths: ModuleType, xdg_corpus: Path
    ) -> None:
        original = paths.artifact_path("specs", "demo-slug")
        assert original == xdg_corpus / "specs" / "demo-slug.md"
        phase, slug = paths.parse_artifact_path(original)
        assert (phase, slug) == ("specs", "demo-slug")

    def test_rejects_non_cheese_path(self, paths: ModuleType) -> None:
        with pytest.raises(ValueError, match=".cheese"):
            paths.parse_artifact_path("some/other/dir/age/x.md")

    def test_rejects_non_md_suffix(self, paths: ModuleType) -> None:
        with pytest.raises(ValueError, match=".md"):
            paths.parse_artifact_path(".cheese/age/x.txt")


class TestExistingArtifacts:
    def test_scans_chain_phases(self, paths: ModuleType, tmp_path: Path) -> None:
        for phase in ("cook", "age"):
            (tmp_path / phase).mkdir(parents=True)
            (tmp_path / phase / "demo.md").write_text("body", encoding="utf-8")

        result = paths.existing_artifacts("demo", root=tmp_path)
        assert set(result.keys()) == {"cook", "age"}
        assert result["cook"].is_file()

    def test_empty_when_none_present(self, paths: ModuleType, tmp_path: Path) -> None:
        assert paths.existing_artifacts("demo", root=tmp_path) == {}

    def test_invalid_slug_rejected(self, paths: ModuleType, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            paths.existing_artifacts("Bad_Slug", root=tmp_path)
