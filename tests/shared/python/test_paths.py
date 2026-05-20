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


class TestArtifactPath:
    def test_builds_canonical_path(self, paths: ModuleType) -> None:
        result = paths.artifact_path("age", "fix-auth-retry")
        assert result == Path(".cheese/age/fix-auth-retry.md")

    def test_custom_root(self, paths: ModuleType, tmp_path: Path) -> None:
        result = paths.artifact_path("cure", "demo", root=tmp_path)
        assert result == tmp_path / "cure" / "demo.md"

    def test_rejects_unknown_phase(self, paths: ModuleType) -> None:
        with pytest.raises(ValueError, match="unknown phase"):
            paths.artifact_path("bogus", "fix-x")

    def test_rejects_bad_slug(self, paths: ModuleType) -> None:
        with pytest.raises(ValueError, match="kebab-case"):
            paths.artifact_path("age", "Bad_Slug")


class TestParseArtifactPath:
    def test_round_trip(self, paths: ModuleType) -> None:
        original = paths.artifact_path("press", "demo-slug")
        phase, slug = paths.parse_artifact_path(original)
        assert phase == "press"
        assert slug == "demo-slug"

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
