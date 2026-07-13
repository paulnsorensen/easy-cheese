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


class TestHardDirReconciliation:
    """`hard` token stays stable; on-disk dir is `hard-cheese`."""

    def test_artifact_path_uses_hard_cheese_dir(self, paths: ModuleType) -> None:
        assert paths.artifact_path("hard", "demo") == Path(".cheese/hard-cheese/demo.md")

    def test_roundtrip_parse(self, paths: ModuleType) -> None:
        path = paths.artifact_path("hard", "demo")
        assert path == Path(".cheese/hard-cheese/demo.md")
        assert paths.parse_artifact_path(path) == ("hard", "demo")

    def test_existing_artifacts_finds_hard(
        self, paths: ModuleType, tmp_path: Path
    ) -> None:
        target = tmp_path / "hard-cheese" / "demo.md"
        target.parent.mkdir(parents=True)
        target.write_text("x", encoding="utf-8")
        found = paths.existing_artifacts("demo", root=tmp_path, phases=("hard",))
        assert found == {"hard": target}


class TestPhaseSkill:
    @pytest.mark.parametrize(
        ("phase", "skill"),
        [
            ("hard", "/hard-cheese"),
            ("specs", "/mold"),
            ("notes", "/wheypoint"),
            ("research", "/briesearch"),
            ("affinage", "/affinage"),
            ("cook", "/cook"),
            ("press", "/press"),
        ],
    )
    def test_maps_phase_to_skill(
        self, paths: ModuleType, phase: str, skill: str
    ) -> None:
        assert paths.phase_skill(phase) == skill


class TestDomainModelTarget:
    """`domain_model_target()` — read-probe cascade then create precedence.

    Focus: acceptance criterion #3, the create-path resolution. WHY the create
    branch must be gated: an existing model at any store must be returned as-is,
    never forked into a fresh store, or the ubiquitous language fragments.
    """

    def test_create_uses_docs_when_tracked_docs_dir_exists(
        self, paths: ModuleType, tmp_path: Path, xdg_corpus: Path
    ) -> None:
        # No model anywhere yet, but a tracked docs/ dir exists: create there.
        (tmp_path / "docs").mkdir()
        backend, location = paths.domain_model_target(repo_root=tmp_path)
        assert backend == "file"
        assert location == tmp_path / "docs" / "domain-model.md"

    def test_create_uses_xdg_when_no_docs_dir(
        self, paths: ModuleType, tmp_path: Path, xdg_corpus: Path
    ) -> None:
        # No docs/ dir: the first write lands in the XDG durable corpus.
        backend, location = paths.domain_model_target(repo_root=tmp_path)
        assert backend == "file"
        assert location == xdg_corpus / "domain-model.md"

    def test_existing_docs_model_wins_over_create(
        self, paths: ModuleType, tmp_path: Path, xdg_corpus: Path
    ) -> None:
        # An existing docs model is returned verbatim; the create branch must
        # NOT fire and must not fork a second store under the XDG corpus.
        model = tmp_path / "docs" / "domain-model.md"
        model.parent.mkdir()
        model.write_text("**Term** — x.\n", encoding="utf-8")
        assert paths.domain_model_target(repo_root=tmp_path) == ("file", model)

    def test_existing_xdg_model_wins_over_docs_create(
        self, paths: ModuleType, tmp_path: Path, xdg_corpus: Path
    ) -> None:
        # A docs/ dir exists (create would pick it) but a model already lives in
        # the XDG corpus: the existing model wins, no new docs/ model is forged.
        (tmp_path / "docs").mkdir()
        model = xdg_corpus / "domain-model.md"
        model.parent.mkdir(parents=True)
        model.write_text("**Term** — x.\n", encoding="utf-8")
        assert paths.domain_model_target(repo_root=tmp_path) == ("file", model)

    def test_existing_split_directory_is_returned(
        self, paths: ModuleType, tmp_path: Path, xdg_corpus: Path
    ) -> None:
        # The second bounded context splits the store into a domain-model/ dir.
        # The probe must recognise that layout and return the directory, not
        # create a fresh single-file model beside it.
        split = tmp_path / "docs" / "domain-model"
        (split).mkdir(parents=True)
        (split / "index.md").write_text("# contexts\n", encoding="utf-8")
        assert paths.domain_model_target(repo_root=tmp_path) == ("file", split)

    def test_single_file_wins_over_split_dir_in_same_store(
        self, paths: ModuleType, tmp_path: Path, xdg_corpus: Path
    ) -> None:
        # Migration debt: both layouts somehow coexist in the same store. Per
        # the single->split lazy-migration order documented on
        # `_existing_domain_model`, the file must win — a mutation that probes
        # the split dir first would silently orphan the single-file model.
        docs = tmp_path / "docs"
        docs.mkdir()
        single = docs / "domain-model.md"
        single.write_text("**Term** — x.\n", encoding="utf-8")
        split = docs / "domain-model"
        split.mkdir()
        (split / "index.md").write_text("# contexts\n", encoding="utf-8")
        assert paths.domain_model_target(repo_root=tmp_path) == ("file", single)

    def test_docs_store_precedes_xdg_store_on_read(
        self, paths: ModuleType, tmp_path: Path, xdg_corpus: Path
    ) -> None:
        # Both file stores hold a model: docs/ (tier 2) wins over XDG (tier 3).
        docs_model = tmp_path / "docs" / "domain-model.md"
        docs_model.parent.mkdir()
        docs_model.write_text("**A** — x.\n", encoding="utf-8")
        xdg_model = xdg_corpus / "domain-model.md"
        xdg_model.parent.mkdir(parents=True)
        xdg_model.write_text("**B** — y.\n", encoding="utf-8")
        assert paths.domain_model_target(repo_root=tmp_path) == ("file", docs_model)

    def test_wiki_probe_wins_when_corpus_listed(
        self, paths: ModuleType, tmp_path: Path, xdg_corpus: Path
    ) -> None:
        # A reachable probe listing the repo's wiki corpus routes to hallouminate,
        # even though a docs/ dir exists — wiki is the top of the create precedence.
        (tmp_path / "docs").mkdir()
        corpus = f"repo:{tmp_path.name}:wiki"
        backend, location = paths.domain_model_target(
            repo_root=tmp_path,
            list_corpora=lambda: ["repo:other:wiki", corpus],
        )
        assert (backend, location) == ("hallouminate", corpus)

    def test_wiki_corpus_name_is_dynamic_not_hardcoded(
        self, paths: ModuleType, tmp_path: Path, xdg_corpus: Path
    ) -> None:
        # The corpus name is keyed to the repo under work: a wiki for a DIFFERENT
        # repo must not match, so resolution falls through to the file stores.
        backend, location = paths.domain_model_target(
            repo_root=tmp_path,
            list_corpora=lambda: ["repo:someone-else:wiki"],
        )
        assert backend == "file"
        assert location == xdg_corpus / "domain-model.md"

    def test_unreachable_probe_degrades_to_file_stores(
        self, paths: ModuleType, tmp_path: Path, xdg_corpus: Path
    ) -> None:
        # A probe that raises must not block resolution: degrade to the files.
        def boom() -> list[str]:
            raise RuntimeError("hallouminate unreachable")

        (tmp_path / "docs").mkdir()
        backend, location = paths.domain_model_target(
            repo_root=tmp_path, list_corpora=boom
        )
        assert (backend, location) == ("file", tmp_path / "docs" / "domain-model.md")

    def test_none_probe_skips_wiki_leg(
        self, paths: ModuleType, tmp_path: Path, xdg_corpus: Path
    ) -> None:
        # The default: no probe injected → wiki leg skipped, file stores only.
        backend, _ = paths.domain_model_target(repo_root=tmp_path)
        assert backend == "file"


class TestResolveSlug:
    def test_tier1_exact_repo_local(
        self, paths: ModuleType, tmp_path: Path
    ) -> None:
        art = tmp_path / ".cheese" / "cook" / "demo.md"
        art.parent.mkdir(parents=True)
        art.write_text("x", encoding="utf-8")
        result = paths.resolve_slug("demo", repo_root=tmp_path)
        assert result["fallback_roots"] == []
        assert result["matches"] == [
            {
                "abs_path": str(art),
                "phase": "cook",
                "skill": "/cook",
                "confidence": 1.0,
            }
        ]

    def test_tier1_research_nested_xdg(
        self, paths: ModuleType, tmp_path: Path, xdg_corpus: Path
    ) -> None:
        art = xdg_corpus / "research" / "foo" / "foo.md"
        art.parent.mkdir(parents=True)
        art.write_text("x", encoding="utf-8")
        result = paths.resolve_slug("foo", repo_root=tmp_path)
        assert result["matches"] == [
            {
                "abs_path": str(art),
                "phase": "research",
                "skill": "/briesearch",
                "confidence": 1.0,
            }
        ]

    def test_tier1_ultracook_manifest(
        self, paths: ModuleType, tmp_path: Path
    ) -> None:
        art = tmp_path / ".cheese" / "ultracook" / "widget" / "manifest.yaml"
        art.parent.mkdir(parents=True)
        art.write_text("name: widget", encoding="utf-8")
        result = paths.resolve_slug("widget", repo_root=tmp_path)
        assert result["matches"] == [
            {
                "abs_path": str(art),
                "phase": "ultracook",
                "skill": "/ultracook",
                "confidence": 1.0,
            }
        ]

    def test_tier1_affinage_pr_key(
        self, paths: ModuleType, tmp_path: Path
    ) -> None:
        art = tmp_path / ".cheese" / "affinage" / "pr-7.md"
        art.parent.mkdir(parents=True)
        art.write_text("x", encoding="utf-8")
        result = paths.resolve_slug("pr-7", repo_root=tmp_path)
        assert result["matches"] == [
            {
                "abs_path": str(art),
                "phase": "affinage",
                "skill": "/affinage",
                "confidence": 1.0,
            }
        ]

    def test_tier1_hard_found_under_hard_cheese(
        self, paths: ModuleType, tmp_path: Path
    ) -> None:
        art = tmp_path / ".cheese" / "hard-cheese" / "demo.md"
        art.parent.mkdir(parents=True)
        art.write_text("x", encoding="utf-8")
        result = paths.resolve_slug("demo", repo_root=tmp_path)
        assert result["matches"] == [
            {
                "abs_path": str(art),
                "phase": "hard",
                "skill": "/hard-cheese",
                "confidence": 1.0,
            }
        ]

    def test_phase_hint_restricts_search(
        self, paths: ModuleType, tmp_path: Path
    ) -> None:
        cook = tmp_path / ".cheese" / "cook" / "demo.md"
        cook.parent.mkdir(parents=True)
        cook.write_text("x", encoding="utf-8")
        age = tmp_path / ".cheese" / "age" / "demo.md"
        age.parent.mkdir(parents=True)
        age.write_text("x", encoding="utf-8")
        result = paths.resolve_slug("demo", phase_hint="age", repo_root=tmp_path)
        assert [m["phase"] for m in result["matches"]] == ["age"]

    def test_tier2_fuzzy(self, paths: ModuleType, tmp_path: Path) -> None:
        art = tmp_path / ".cheese" / "cook" / "slug-resolver.md"
        art.parent.mkdir(parents=True)
        art.write_text("x", encoding="utf-8")
        result = paths.resolve_slug("slug-resolvr", repo_root=tmp_path)
        assert len(result["matches"]) == 1
        match = result["matches"][0]
        assert match["abs_path"] == str(art)
        assert match["phase"] == "cook"
        assert 0.6 <= match["confidence"] < 1.0
        assert result["fallback_roots"] == []

    def test_tier3_fallback_roots(
        self, paths: ModuleType, tmp_path: Path
    ) -> None:
        result = paths.resolve_slug("nowhere", repo_root=tmp_path)
        assert result["matches"] == []
        cook_dir = str(tmp_path / ".cheese" / "cook")
        affinage_dir = str(tmp_path / ".cheese" / "affinage")
        assert cook_dir in result["fallback_roots"]
        assert affinage_dir in result["fallback_roots"]
        assert result["fallback_roots"] == sorted(result["fallback_roots"])

    def test_rejects_bad_slug(self, paths: ModuleType) -> None:
        with pytest.raises(ValueError, match="kebab-case"):
            paths.resolve_slug("Bad_Slug")

    def test_tier2_fuzzy_ranked_by_confidence_descending(
        self, paths: ModuleType, tmp_path: Path
    ) -> None:
        # Two near-misses in one phase: the closer stem must come first.
        cook = tmp_path / ".cheese" / "cook"
        cook.mkdir(parents=True)
        near = cook / "slug-resolvr.md"  # ratio 0.96
        far = cook / "slug-resolxxx.md"  # ratio 0.769
        near.write_text("x", encoding="utf-8")
        far.write_text("x", encoding="utf-8")
        matches = paths.resolve_slug("slug-resolver", repo_root=tmp_path)["matches"]
        assert [m["abs_path"] for m in matches] == [str(near), str(far)]
        assert matches[0]["confidence"] > matches[1]["confidence"]
        assert matches[0]["confidence"] == 0.96

    def test_tier2_below_cutoff_excluded(
        self, paths: ModuleType, tmp_path: Path
    ) -> None:
        # ratio('abcde','abxyz') == 0.4 < 0.6 cutoff: not a match, fall to tier 3.
        cook = tmp_path / ".cheese" / "cook"
        cook.mkdir(parents=True)
        (cook / "abxyz.md").write_text("x", encoding="utf-8")
        result = paths.resolve_slug("abcde", repo_root=tmp_path)
        assert result["matches"] == []
        assert str(cook) in result["fallback_roots"]

    def test_tier2_at_cutoff_is_inclusive(
        self, paths: ModuleType, tmp_path: Path
    ) -> None:
        # ratio('payment','pay') == 0.6 exactly: cutoff is `>=`, so it matches.
        cook = tmp_path / ".cheese" / "cook"
        cook.mkdir(parents=True)
        art = cook / "pay.md"
        art.write_text("x", encoding="utf-8")
        matches = paths.resolve_slug("payment", repo_root=tmp_path)["matches"]
        assert [m["abs_path"] for m in matches] == [str(art)]
        assert matches[0]["confidence"] == 0.6

    def test_collision_same_slug_two_phases(
        self, paths: ModuleType, tmp_path: Path
    ) -> None:
        # An exact slug present in two phases returns both, ordered by phase.
        cook = tmp_path / ".cheese" / "cook" / "demo.md"
        cook.parent.mkdir(parents=True)
        cook.write_text("x", encoding="utf-8")
        age = tmp_path / ".cheese" / "age" / "demo.md"
        age.parent.mkdir(parents=True)
        age.write_text("x", encoding="utf-8")
        result = paths.resolve_slug("demo", repo_root=tmp_path)
        assert [m["phase"] for m in result["matches"]] == ["age", "cook"]
        assert {m["abs_path"] for m in result["matches"]} == {str(age), str(cook)}
        assert all(m["confidence"] == 1.0 for m in result["matches"])

    def test_phase_hint_miss_does_not_fall_through(
        self, paths: ModuleType, tmp_path: Path
    ) -> None:
        # Slug lives in cook, but the hint names press: the search stays restricted
        # to press, misses, and the fallback lists only the hinted root.
        cook = tmp_path / ".cheese" / "cook" / "demo.md"
        cook.parent.mkdir(parents=True)
        cook.write_text("x", encoding="utf-8")
        result = paths.resolve_slug("demo", phase_hint="press", repo_root=tmp_path)
        assert result["matches"] == []
        assert result["fallback_roots"] == [str(tmp_path / ".cheese" / "press")]

    def test_unknown_phase_hint_raises(
        self, paths: ModuleType, tmp_path: Path
    ) -> None:
        # Fail-fast: a typo/unknown hint raises rather than silently widening the
        # search to every phase, matching the `existing`/`artifact_path` contracts.
        cook = tmp_path / ".cheese" / "cook" / "demo.md"
        cook.parent.mkdir(parents=True)
        cook.write_text("x", encoding="utf-8")
        with pytest.raises(ValueError, match=r"unknown phase 'bogus'"):
            paths.resolve_slug("demo", phase_hint="bogus", repo_root=tmp_path)

    def test_literal_hard_dir_is_not_resolved(
        self, paths: ModuleType, tmp_path: Path
    ) -> None:
        # The `hard` token resolves to hard-cheese/ only; a literal .cheese/hard/
        # artifact must NOT be found.
        stray = tmp_path / ".cheese" / "hard" / "demo.md"
        stray.parent.mkdir(parents=True)
        stray.write_text("x", encoding="utf-8")
        result = paths.resolve_slug("demo", repo_root=tmp_path)
        assert result["matches"] == []
        assert str(stray.parent) not in result["fallback_roots"]

    def test_all_emitted_paths_are_absolute(
        self, paths: ModuleType, tmp_path: Path, xdg_corpus: Path
    ) -> None:
        # Invariant across all three tiers: every path the resolver emits is absolute.
        exact = tmp_path / ".cheese" / "cook" / "demo.md"
        exact.parent.mkdir(parents=True)
        exact.write_text("x", encoding="utf-8")
        for slug in ("demo", "slug-resolvr", "nowhere"):
            result = paths.resolve_slug(slug, repo_root=tmp_path)
            for match in result["matches"]:
                assert Path(match["abs_path"]).is_absolute(), (slug, match)
            for root in result["fallback_roots"]:
                assert Path(root).is_absolute(), (slug, root)
