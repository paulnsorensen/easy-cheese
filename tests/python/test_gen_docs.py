"""Tests for scripts/gen_docs.py Starlight generation rules."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GEN_DOCS = REPO_ROOT / "scripts" / "gen_docs.py"


@pytest.fixture(scope="module")
def gen_docs() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_docs", GEN_DOCS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules["gen_docs"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def isolated_docs(gen_docs, tmp_path, monkeypatch):
    monkeypatch.setattr(gen_docs, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gen_docs, "SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(gen_docs, "CONTENT_ROOT", tmp_path / "src" / "content" / "docs")
    monkeypatch.setattr(gen_docs, "SIDEBAR_PATH", tmp_path / "src" / "sidebar.mjs")
    gen_docs._ref_title.cache_clear()
    return tmp_path


class TestRewriteSkillLink:
    def test_external_urls_pass_through(self, gen_docs):
        for url in (
            "https://example.com",
            "http://example.com",
            "mailto:x@y.z",
            "#section",
        ):
            assert gen_docs.rewrite_skill_link(url, "cook") == url

    def test_local_reference_resolves_to_anchor(self, gen_docs):
        # No SKILLS_DIR fixture populated here — title resolution degrades to
        # a stem-derived slug.
        assert gen_docs.rewrite_skill_link("references/foo.md", "cook") == "#foo"

    def test_local_reference_with_explicit_anchor_overrides_title(self, gen_docs):
        assert gen_docs.rewrite_skill_link("references/foo.md#part", "cook") == "#part"

    def test_cross_skill_skill_md_routes_to_sibling_skill(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../press/SKILL.md", "cook") == "../press/"

    def test_cross_skill_skill_md_with_anchor(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../press/SKILL.md#auto-mode", "cook") == "../press/#auto-mode"

    def test_cross_skill_reference_resolves_to_anchor(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../press/references/quality-gates.md", "cook") == "../press/#quality-gates"

    def test_cross_skill_reference_with_explicit_anchor_overrides_title(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../press/references/quality-gates.md#x", "cook") == "../press/#x"

    def test_root_doc_resolves_to_root_route(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../../CONTRIBUTING.md", "cook") == "../../contributing/"
        assert gen_docs.rewrite_skill_link("../../SECURITY.md", "cook") == "../../security/"
        assert gen_docs.rewrite_skill_link("../../README.md", "cook") == "../../readme/"

    def test_license_becomes_absolute_repo_url(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../../LICENSE", "cook") == f"{gen_docs.REPO_URL}/blob/main/LICENSE"

    def test_unknown_path_is_untouched(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../../some/other/file.md", "cook") == "../../some/other/file.md"

    def test_cross_skill_reference_resolves_via_sibling_title_not_stem_fallback(self, gen_docs, isolated_docs):
        # Positive path for _ref_title: a REAL sibling skill+ref exists, so the
        # anchor must come from that ref's actual title, not the stem-derived
        # fallback slug the degrade-path tests above exercise. The em-dash title
        # coincidentally slugs to the same string as the stem fallback would for
        # a plain "quality-gates" stem, so also assert against a stem-diverging
        # title to prove real resolution, not a fallback that happens to match.
        press_refs = isolated_docs / "skills" / "press" / "references"
        press_refs.mkdir(parents=True)
        (press_refs / "quality-gates.md").write_text(
            "---\ntitle: Quality Gates — the bar\n---\n\n# Ignored\n\nBody.\n",
            encoding="utf-8",
        )
        gen_docs._ref_title.cache_clear()

        result = gen_docs.rewrite_skill_link("../press/references/quality-gates.md", "cook")

        assert result == "../press/#quality-gates--the-bar"
        stem_fallback = f"#{gen_docs._heading_slug('quality-gates'.replace('-', ' '))}"
        assert result != f"../press/{stem_fallback}"


class TestRewriteRefLink:
    def test_external_urls_pass_through(self, gen_docs):
        for url in ("https://example.com", "mailto:x@y.z", "#anchor"):
            assert gen_docs.rewrite_ref_link(url, "press") == url

    def test_sibling_reference_resolves_to_anchor(self, gen_docs):
        assert gen_docs.rewrite_ref_link("foo.md", "mold") == "#foo"

    def test_sibling_reference_with_explicit_anchor_overrides_title(self, gen_docs):
        assert gen_docs.rewrite_ref_link("foo.md#part", "mold") == "#part"

    def test_sibling_skill_md_points_to_top_of_same_page(self, gen_docs):
        assert gen_docs.rewrite_ref_link("../SKILL.md", "press") == "#"
        assert gen_docs.rewrite_ref_link("../SKILL.md#auto", "press") == "#auto"

    def test_cross_skill_skill_md(self, gen_docs):
        assert gen_docs.rewrite_ref_link("../../cook/SKILL.md", "press") == "../cook/"

    def test_cross_skill_skill_md_with_anchor(self, gen_docs):
        assert gen_docs.rewrite_ref_link("../../cook/SKILL.md#auto", "press") == "../cook/#auto"

    def test_cross_skill_reference_resolves_to_anchor(self, gen_docs):
        assert gen_docs.rewrite_ref_link("../../cook/references/foo.md", "press") == "../cook/#foo"

    def test_cross_skill_reference_with_explicit_anchor_overrides_title(self, gen_docs):
        assert gen_docs.rewrite_ref_link("../../cook/references/foo.md#x", "press") == "../cook/#x"

    def test_root_doc(self, gen_docs):
        assert gen_docs.rewrite_ref_link("../../../CONTRIBUTING.md", "press") == "../../contributing/"
        assert gen_docs.rewrite_ref_link("../../../README.md", "press") == "../../readme/"

    def test_license(self, gen_docs):
        assert gen_docs.rewrite_ref_link("../../../LICENSE", "press") == f"{gen_docs.REPO_URL}/blob/main/LICENSE"


class TestRewriteRootPassthroughLink:
    def test_external_pass_through(self, gen_docs):
        for url in ("https://example.com", "mailto:x@y.z", "#anchor"):
            assert gen_docs.rewrite_root_passthrough_link(url) == url

    def test_known_root_doc(self, gen_docs):
        assert gen_docs.rewrite_root_passthrough_link("CONTRIBUTING.md") == "../contributing/"
        assert gen_docs.rewrite_root_passthrough_link("./SECURITY.md") == "../security/"
        assert gen_docs.rewrite_root_passthrough_link("CODE_OF_CONDUCT.md") == "../code-of-conduct/"

    def test_known_root_doc_with_anchor(self, gen_docs):
        assert gen_docs.rewrite_root_passthrough_link("./CONTRIBUTING.md#pull-requests") == "../contributing/#pull-requests"

    def test_license(self, gen_docs):
        assert gen_docs.rewrite_root_passthrough_link("LICENSE") == f"{gen_docs.REPO_URL}/blob/main/LICENSE"

    def test_skill_reference(self, gen_docs):
        assert gen_docs.rewrite_root_passthrough_link("skills/age/references/voice.md") == "../skills/age/#voice"

    def test_shared_path_untouched(self, gen_docs):
        # shared/*.md docs moved to skills/cheese/references/; no rewrite branch remains.
        assert gen_docs.rewrite_root_passthrough_link("shared/scripts/handoff.py") == "shared/scripts/handoff.py"

    def test_unknown_path_untouched(self, gen_docs):
        assert gen_docs.rewrite_root_passthrough_link("skills/cook/SKILL.md") == "../skills/cook/"


class TestApplyLinkRewrite:
    def test_rewrites_markdown_link(self, gen_docs):
        text = "See [the press skill](../press/SKILL.md) for more."
        out = gen_docs.apply_link_rewrite(text, lambda u: gen_docs.rewrite_skill_link(u, "cook"))
        assert out == "See [the press skill](../press/) for more."

    def test_rewrites_link_with_title(self, gen_docs):
        text = '[link](../press/SKILL.md "Press skill")'
        out = gen_docs.apply_link_rewrite(text, lambda u: gen_docs.rewrite_skill_link(u, "cook"))
        assert out == '[link](../press/ "Press skill")'

    def test_leaves_inline_images_alone(self, gen_docs):
        text = "![alt](references/diagram.png)"
        out = gen_docs.apply_link_rewrite(text, lambda u: gen_docs.rewrite_skill_link(u, "cook"))
        assert out == "![alt](references/diagram.png)"

    def test_rewrites_nested_image_link(self, gen_docs):
        text = "[![alt](logo.png)](../press/SKILL.md)"
        out = gen_docs.apply_link_rewrite(text, lambda u: gen_docs.rewrite_skill_link(u, "cook"))
        assert out == "[![alt](logo.png)](../press/)"


class TestMarkdownConversion:
    def test_mkdocs_admonition_becomes_starlight_aside(self, gen_docs):
        out = gen_docs.convert_mkdocs_admonitions('before\n\n!!! info "Skill metadata"\n    - item\n    body\n\nafter\n')
        assert '!!! info' not in out
        assert ':::info[Skill metadata]' in out
        assert '- item' in out
        assert ':::' in out

    def test_frontmatter_supports_source_edit_url(self, gen_docs):
        out = gen_docs.starlight_frontmatter(
            title="Title",
            description="Desc.",
            edit_url="https://example.com/edit/source.md",
        )
        assert "title: Title" in out
        assert "description: Desc." in out
        assert "editUrl: https://example.com/edit/source.md" in out


    def test_frontmatter_can_disable_edit_url(self, gen_docs):
        out = gen_docs.starlight_frontmatter(title="Generated", edit_url=False)
        assert "editUrl: false" in out

class TestFirstSentence:
    def test_grabs_first_sentence(self, gen_docs):
        assert gen_docs.first_sentence("First sentence. Second.") == "First sentence."

    def test_handles_newlines(self, gen_docs):
        assert gen_docs.first_sentence("First\nsentence.\n\nSecond.") == "First sentence."

    def test_caps_at_240_chars(self, gen_docs):
        assert len(gen_docs.first_sentence("x" * 300)) == 240


class TestParseFrontmatter:
    def test_extracts_metadata(self, gen_docs):
        meta, body = gen_docs.parse_frontmatter("---\nname: foo\ndescription: bar\n---\nbody")
        assert meta == {"name": "foo", "description": "bar"}
        assert body == "body"

    def test_no_frontmatter(self, gen_docs):
        meta, body = gen_docs.parse_frontmatter("just body")
        assert meta == {}
        assert body == "just body"

    def test_malformed_yaml_does_not_raise(self, gen_docs):
        meta, _ = gen_docs.parse_frontmatter("---\nname: : foo\n---\nbody")
        assert meta == {}


class TestWriteDoc:
    def test_drops_leading_h1_duplicating_starlight_title(self, gen_docs, isolated_docs):
        gen_docs.write_doc("page.md", "# Page title\n\nBody.\n", title="Page title")
        text = (isolated_docs / "src" / "content" / "docs" / "page.md").read_text(encoding="utf-8")
        _, body = gen_docs.parse_frontmatter(text)
        assert body.lstrip() == "Body.\n"

    def test_keeps_non_leading_headings(self, gen_docs, isolated_docs):
        gen_docs.write_doc("page.md", "Intro.\n\n## Section\n", title="T")
        text = (isolated_docs / "src" / "content" / "docs" / "page.md").read_text(encoding="utf-8")
        _, body = gen_docs.parse_frontmatter(text)
        assert body.lstrip() == "Intro.\n\n## Section\n"


class TestExtractH2Section:
    def test_basic_extraction(self, gen_docs):
        text = "## A\nbody-a\n\n## B\nbody-b\n"
        assert gen_docs.extract_h2_section(text, "A") == "## A\nbody-a\n\n"

    def test_drop_header_omits_h2_line(self, gen_docs):
        text = "## A\nbody-a\n\n## B\nbody-b\n"
        assert gen_docs.extract_h2_section(text, "A", drop_header=True) == "body-a\n\n"

    def test_bump_headings_promotes_h3_to_h2(self, gen_docs):
        text = "## A\n### Sub\nbody\n\n## B\n"
        out = gen_docs.extract_h2_section(text, "A", drop_header=True, bump_headings=True)
        assert "## Sub\n" in out
        assert "### Sub" not in out

    def test_bump_headings_promotes_h4_to_h3(self, gen_docs):
        text = "## A\n### Sub\n#### Deep\nbody\n\n## B\n"
        out = gen_docs.extract_h2_section(text, "A", drop_header=True, bump_headings=True)
        assert "## Sub\n" in out
        assert "### Deep\n" in out
        assert "#### Deep" not in out

    def test_missing_section_returns_empty(self, gen_docs):
        assert gen_docs.extract_h2_section("## A\nbody-a\n", "Z") == ""

    def test_section_runs_to_eof_when_no_next_h2(self, gen_docs):
        assert gen_docs.extract_h2_section("## A\nbody-a\nstill-a\n", "A") == "## A\nbody-a\nstill-a\n"

    def test_ignores_h3_with_matching_text(self, gen_docs):
        text = "## A\nbody-a\n### A\nstill-a\n\n## B\nbody-b\n"
        out = gen_docs.extract_h2_section(text, "A")
        assert "still-a" in out
        assert "body-b" not in out


class TestEmitInstallPage:
    def _write_full_readme(self, path: Path):
        path.write_text(
            "# Title\n\n"
            "## Optional tools\n\n"
            "| Tool | Helps |\n| --- | --- |\n| ripgrep | search |\n\n"
            "## Install\n\n"
            "### gh skill\n\n"
            "install steps\n\n"
            "## Installing MCP servers\n\n"
            "mcp steps\n\n"
            "## Installing CLI tools\n\n"
            "cli steps\n",
            encoding="utf-8",
        )

    def test_missing_readme_returns_none(self, gen_docs, isolated_docs):
        assert gen_docs.emit_install_page() is None

    def test_missing_section_raises_with_named_section(self, gen_docs, isolated_docs):
        (isolated_docs / "README.md").write_text(
            "## Optional tools\n\ntable\n\n"
            "## Install\n\ninstall\n\n"
            "## Installing MCP servers\n\nmcp\n",
            encoding="utf-8",
        )
        with pytest.raises(RuntimeError, match=r"Installing CLI tools"):
            gen_docs.emit_install_page()

    def test_missing_section_message_names_all_gaps(self, gen_docs, isolated_docs):
        (isolated_docs / "README.md").write_text("## Install\n\ninstall\n", encoding="utf-8")
        with pytest.raises(RuntimeError) as exc:
            gen_docs.emit_install_page()
        msg = str(exc.value)
        assert "Installing MCP servers" in msg
        assert "Optional tools" in msg
        assert "Installing CLI tools" in msg

    def test_all_sections_write_starlight_file(self, gen_docs, isolated_docs):
        self._write_full_readme(isolated_docs / "README.md")
        page = gen_docs.emit_install_page()
        out = isolated_docs / "src" / "content" / "docs" / "install.md"
        assert page == gen_docs.GeneratedPage("Install", "install", "README.md")
        body = out.read_text(encoding="utf-8")
        assert "title: Install" in body
        assert "editUrl: https://github.com/paulnsorensen/easy-cheese/edit/main/README.md" in body
        assert not body.lstrip().startswith("# ")  # Starlight renders the title H1
        assert "## gh skill" in body


class TestHeadingSlug:
    def test_lowercases_and_hyphenates(self, gen_docs):
        assert gen_docs._heading_slug("Go De-slop Catalog") == "go-de-slop-catalog"

    def test_strips_punctuation(self, gen_docs):
        assert gen_docs._heading_slug("Auto Mode (v2)!") == "auto-mode-v2"

    def test_does_not_collapse_separators(self, gen_docs):
        # github-slugger turns each space into its own hyphen and never collapses
        # repeats, so a run of spaces yields a run of hyphens.
        assert gen_docs._heading_slug("Quality   Gates") == "quality---gates"

    def test_keeps_underscores(self, gen_docs):
        # Regression: a naive slugger strips underscores; github-slugger keeps them.
        assert gen_docs._heading_slug("tilth_write JSON cookbook") == "tilth_write-json-cookbook"

    def test_em_dash_leaves_double_hyphen(self, gen_docs):
        # The space-em-dash-space idiom (`A — B`) drops the em-dash but keeps both
        # surrounding spaces, so github-slugger emits a double hyphen.
        assert gen_docs._heading_slug("Cascade stages — branch-specific steps") == "cascade-stages--branch-specific-steps"


class TestFoldReferences:
    def test_missing_refs_dir_returns_empty(self, gen_docs, isolated_docs):
        folded, titles = gen_docs.fold_references("cook", isolated_docs / "skills" / "cook" / "references")
        assert folded == ""
        assert titles == {}

    def test_promotes_h1_to_h2_and_bumps_inner_headings(self, gen_docs, isolated_docs):
        refs_dir = isolated_docs / "skills" / "cook" / "references"
        refs_dir.mkdir(parents=True)
        (refs_dir / "gate.md").write_text(
            "---\ntitle: Quality gates\n---\n"
            "# Original H1\n\nIntro text.\n\n### Sub heading\n\nBody text.\n",
            encoding="utf-8",
        )

        folded, titles = gen_docs.fold_references("cook", refs_dir)

        assert "## Quality gates" in folded
        assert "# Original H1" not in folded
        assert "#### Sub heading" in folded
        assert not re.search(r"(?m)^### Sub heading$", folded)
        assert "Intro text." in folded
        assert titles == {"gate": "Quality gates"}

    def test_title_precedence_falls_back_to_first_h1_then_stem(self, gen_docs, isolated_docs):
        refs_dir = isolated_docs / "skills" / "cook" / "references"
        refs_dir.mkdir(parents=True)
        (refs_dir / "first-h1.md").write_text("# From body\n\nBody.\n", encoding="utf-8")
        (refs_dir / "no-heading.md").write_text("Just prose.\n", encoding="utf-8")

        _, titles = gen_docs.fold_references("cook", refs_dir)

        assert titles["first-h1"] == "From body"
        assert titles["no-heading"] == "No heading"

    def test_sections_are_sorted_by_filename(self, gen_docs, isolated_docs):
        refs_dir = isolated_docs / "skills" / "cook" / "references"
        refs_dir.mkdir(parents=True)
        (refs_dir / "b.md").write_text("# B title\n\nB body.\n", encoding="utf-8")
        (refs_dir / "a.md").write_text("# A title\n\nA body.\n", encoding="utf-8")

        folded, _ = gen_docs.fold_references("cook", refs_dir)

        assert folded.index("A title") < folded.index("B title")

    def test_skips_non_markdown_files(self, gen_docs, isolated_docs):
        refs_dir = isolated_docs / "skills" / "cook" / "references"
        refs_dir.mkdir(parents=True)
        (refs_dir / "diagram.png").write_bytes(b"not markdown")

        folded, titles = gen_docs.fold_references("cook", refs_dir)

        assert folded == ""
        assert titles == {}


class TestEmitSkillPage:
    def test_writes_single_page_with_folded_reference_and_no_ref_files(self, gen_docs, isolated_docs):
        skill_dir = isolated_docs / "skills" / "cook"
        refs_dir = skill_dir / "references"
        refs_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: cook\ndescription: Build the feature. Then ship it.\nlicense: MIT\n---\n"
            "# /cook\n\nSee [gate](references/gate.md).\n",
            encoding="utf-8",
        )
        (refs_dir / "gate.md").write_text("# Gate\n\nBack to [skill](../SKILL.md).\n", encoding="utf-8")

        page = gen_docs.emit_skill_page(skill_dir)

        skill_out = isolated_docs / "src" / "content" / "docs" / "skills" / "cook.md"
        assert page == gen_docs.GeneratedPage("/cook", "skills/cook", "skills/cook/SKILL.md")
        skill_body = skill_out.read_text(encoding="utf-8")
        assert "title: /cook" in skill_body
        assert ":::note[Skill metadata]" in skill_body
        assert "- **Source:** [`skills/cook/SKILL.md`](https://github.com/paulnsorensen/easy-cheese/blob/main/skills/cook/SKILL.md)" in skill_body
        assert "See [gate](#gate)." in skill_body
        assert "## Gate" in skill_body
        assert "Back to [skill](#)." in skill_body
        assert "editUrl: https://github.com/paulnsorensen/easy-cheese/edit/main/skills/cook/SKILL.md" in skill_body
        assert not (isolated_docs / "src" / "content" / "docs" / "skills" / "cook" / "references").exists()


class TestEmitSidebar:
    def test_writes_flat_sidebar_links(self, gen_docs, isolated_docs):
        skill = gen_docs.GeneratedPage("/age", "skills/age", "skills/age/SKILL.md")
        project = gen_docs.GeneratedPage("README", "readme", "README.md")
        install = gen_docs.GeneratedPage("Install", "install", "README.md")

        gen_docs.emit_sidebar([skill], [project], install)

        out = (isolated_docs / "src" / "sidebar.mjs").read_text(encoding="utf-8")
        assert out.startswith("// Generated by scripts/gen_docs.py")
        sidebar = json.loads(out.split("export const sidebar = ", 1)[1].rstrip(";\n"))

        skills_group = next(g for g in sidebar if g["label"] == "Skills")
        assert skills_group["items"] == [
            {"label": "Skills index", "slug": "skills"},
            {"slug": "skills/age", "label": "/age"},
        ]
        start_group = next(g for g in sidebar if g["label"] == "Start")
        assert {"label": "Install", "slug": "install"} in start_group["items"]

    def test_skill_entries_have_no_items_overview_or_collapsed(self, gen_docs, isolated_docs):
        skill = gen_docs.GeneratedPage("/age", "skills/age", "skills/age/SKILL.md")

        gen_docs.emit_sidebar([skill], [], None)

        out = (isolated_docs / "src" / "sidebar.mjs").read_text(encoding="utf-8")
        sidebar = json.loads(out.split("export const sidebar = ", 1)[1].rstrip(";\n"))
        skills_group = next(g for g in sidebar if g["label"] == "Skills")
        skill_entry = next(item for item in skills_group["items"] if item.get("slug") == "skills/age")
        assert "items" not in skill_entry
        assert "collapsed" not in skill_entry
        assert skill_entry == {"slug": "skills/age", "label": "/age"}


    def test_omits_install_link_when_no_install_page(self, gen_docs, isolated_docs):
        skill = gen_docs.GeneratedPage("/age", "skills/age", "skills/age/SKILL.md")
        project = gen_docs.GeneratedPage("README", "readme", "README.md")

        gen_docs.emit_sidebar([skill], [project], None)

        out = (isolated_docs / "src" / "sidebar.mjs").read_text(encoding="utf-8")
        assert '"label": "Install"' not in out

    def test_generated_skills_index_disables_edit_link(self, gen_docs, isolated_docs):
        skill_dir = isolated_docs / "skills" / "age"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: age\ndescription: Review a diff. Find bugs.\n---\n# /age\n\nBody.\n",
            encoding="utf-8",
        )
        skills = [gen_docs.emit_skill_page(skill_dir)]

        gen_docs.emit_skills_index(skills)

        out = (isolated_docs / "src" / "content" / "docs" / "skills" / "index.md").read_text(encoding="utf-8")
        assert "editUrl: false" in out
        assert "[`/age`](age/)" in out


class TestCleanGeneratedDocs:
    def test_preserves_authored_homepage_and_removes_generated_files(self, gen_docs, isolated_docs):
        docs = isolated_docs / "src" / "content" / "docs"
        (docs / "skills").mkdir(parents=True)
        (docs / "index.md").write_text("authored", encoding="utf-8")
        (docs / "install.md").write_text("generated", encoding="utf-8")
        (docs / "skills" / "age.md").write_text("generated", encoding="utf-8")
        sidebar = isolated_docs / "src" / "sidebar.mjs"
        sidebar.parent.mkdir(parents=True, exist_ok=True)
        sidebar.write_text("generated", encoding="utf-8")

        gen_docs.clean_generated_docs()

        assert (docs / "index.md").read_text(encoding="utf-8") == "authored"
        assert not (docs / "install.md").exists()
        assert not (docs / "skills").exists()
        assert not sidebar.exists()


class TestMainGeneration:
    def test_main_writes_physical_starlight_tree_and_sidebar(self, gen_docs, isolated_docs):
        (isolated_docs / "src" / "content" / "docs").mkdir(parents=True)
        (isolated_docs / "src" / "content" / "docs" / "index.md").write_text("authored", encoding="utf-8")
        (isolated_docs / "README.md").write_text(
            "# Title\n\n"
            "## Optional tools\n\ntools\n\n"
            "## Install\n\n### Setup\n\ninstall\n\n"
            "## Installing MCP servers\n\nmcp\n\n"
            "## Installing CLI tools\n\ncli\n",
            encoding="utf-8",
        )
        (isolated_docs / "CONTRIBUTING.md").write_text("# Contributing\n\ncontrib\n", encoding="utf-8")
        (isolated_docs / "SECURITY.md").write_text("# Security\n\nsecurity\n", encoding="utf-8")
        (isolated_docs / "CODE_OF_CONDUCT.md").write_text("# Code of conduct\n\ncode\n", encoding="utf-8")
        skill_dir = isolated_docs / "skills" / "age" / "references"
        skill_dir.mkdir(parents=True)
        (skill_dir.parent / "SKILL.md").write_text(
            "---\nname: age\ndescription: Review a diff. Find bugs.\n---\n# /age\n\nSee [Voice](references/voice.md).\n",
            encoding="utf-8",
        )
        (skill_dir / "voice.md").write_text("# Voice\n\nReference.\n", encoding="utf-8")
        (skill_dir / "formatting.md").write_text("# Formatting\n\nShared house style.\n", encoding="utf-8")

        gen_docs.main()

        root = isolated_docs / "src" / "content" / "docs"
        assert (root / "index.md").read_text(encoding="utf-8") == "authored"
        assert (root / "install.md").exists()
        assert (root / "skills" / "index.md").exists()
        assert (root / "skills" / "age.md").exists()
        assert not (root / "skills" / "age" / "references").exists()
        assert not (root / "shared").exists()
        assert (root / "readme.md").exists()
        assert (root / "contributing.md").exists()
        assert (isolated_docs / "src" / "sidebar.mjs").exists()
        assert not (root / "SUMMARY.md").exists()

        age_body = (root / "skills" / "age.md").read_text(encoding="utf-8")
        assert "## Voice" in age_body
        assert "## Formatting" in age_body
        assert "See [Voice](#voice)." in age_body

        generated_markdown = "\n".join(p.read_text(encoding="utf-8") for p in root.rglob("*.md"))
        assert not re.search(r"\]\((?!https?://|mailto:|#)[^)]+\.md(?:#[^)]*)?\)", generated_markdown)
        # Non-.md dead routes: a reference sub-page URL leaking through would
        # still 404 even though it has no .md suffix (the High-severity gap
        # the `.md`-only guard above missed).
        assert not re.search(r"\]\([^)]*references/[^)]*\)", generated_markdown)
        for page in root.rglob("*.md"):
            if page == root / "index.md":
                continue  # authored homepage, not generated
            _, page_body = gen_docs.parse_frontmatter(page.read_text(encoding="utf-8"))
            assert not page_body.lstrip().startswith("# "), page


class TestMainGenerationRealCheeseKernelDocs:
    """Integration-shaped check: the five real shared docs that moved to
    skills/cheese/references/ in the cheese-kernel-shared-refs change must
    actually render as folded sections inside cheese's single Starlight page,
    and no src/content/docs/shared/ section may reappear. Copies the real
    repo files into the isolated tmp tree rather than a synthetic fixture, so
    a doc that's dropped or renamed in skills/cheese/references/ fails this
    test even if the synthetic TestMainGeneration fixture above still
    passes."""

    MOVED_DOC_NAMES = (
        "formatting",
        "handoff-gate",
        "harness-portability",
        "optional-plugins",
        "skill-authoring",
    )

    def test_moved_docs_fold_into_cheese_page_no_shared_dir(self, gen_docs, isolated_docs):
        real_cheese_dir = REPO_ROOT / "skills" / "cheese"
        real_refs_dir = real_cheese_dir / "references"
        for name in self.MOVED_DOC_NAMES:
            assert (real_refs_dir / f"{name}.md").is_file(), (
                f"expected {name}.md in the real skills/cheese/references/ — "
                "has the cheese-kernel-shared-refs move regressed?"
            )

        cheese_dir = isolated_docs / "skills" / "cheese"
        cheese_dir.mkdir(parents=True)
        shutil.copy(real_cheese_dir / "SKILL.md", cheese_dir / "SKILL.md")
        refs_dir = cheese_dir / "references"
        refs_dir.mkdir()
        for name in self.MOVED_DOC_NAMES:
            shutil.copy(real_refs_dir / f"{name}.md", refs_dir / f"{name}.md")

        gen_docs.main()

        root = isolated_docs / "src" / "content" / "docs"
        assert not (root / "skills" / "cheese" / "references").exists()
        assert not (root / "shared").exists()
        cheese_body = (root / "skills" / "cheese.md").read_text(encoding="utf-8")
        for name in self.MOVED_DOC_NAMES:
            heading = re.compile(r"^## .+\n", re.MULTILINE)
            assert heading.search(cheese_body), "expected at least one folded ## section"
        assert cheese_body.count("## ") >= len(self.MOVED_DOC_NAMES)


class TestAnchorResolution:
    """End-to-end seam between the link rewriters and fold_references: an
    emitted `](#anchor)` must resolve to a real folded heading, not just look
    plausible in isolation. Regression this guards: a slugger divergence once
    made references/tilth_write.md-style links resolve to nonexistent anchors
    because the anchor-generating path and the heading-rendering path could
    drift apart on underscore/em-dash handling. The generic
    anchor-equals-heading-slug check alone would NOT catch a regression in
    _heading_slug itself (both sides would recompute with the same regressed
    function and still agree) -- the hardcoded literal anchor strings below are
    what actually pin the underscore- and em-dash-idiom behavior; if
    _heading_slug reverts to stripping underscores, EXPECTED_FOO_ANCHOR stops
    appearing in the emitted links and those asserts fail.
    """

    EXPECTED_FOO_ANCHOR = "#tilth_write-json-cookbook"
    EXPECTED_BAR_ANCHOR = "#cascade-stages--branch-specific-steps"

    def test_emitted_anchors_resolve_to_real_folded_headings(self, gen_docs, isolated_docs):
        skill_dir = isolated_docs / "skills" / "demo"
        refs_dir = skill_dir / "references"
        refs_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: demo\ndescription: Demo skill for anchor integration testing.\n---\n"
            "# /demo\n\n"
            "See the [tilth_write JSON cookbook](references/foo.md) for details, "
            "or jump to [a specific section](references/bar.md#some-section) directly.\n",
            encoding="utf-8",
        )
        (refs_dir / "foo.md").write_text(
            "---\ntitle: tilth_write JSON cookbook\n---\n\n"
            "# Ignored\n\nFoo body. See also [the bar](bar.md).\n",
            encoding="utf-8",
        )
        (refs_dir / "bar.md").write_text(
            "---\ntitle: Cascade stages — branch-specific steps\n---\n\n"
            "# Ignored\n\nBar body.\n\n## Some section\n\n"
            "More detail. Back to [demo](../SKILL.md).\n",
            encoding="utf-8",
        )

        page = gen_docs.emit_skill_page(skill_dir)

        assert page is not None
        body = (isolated_docs / "src" / "content" / "docs" / "skills" / "demo.md").read_text(encoding="utf-8")

        headings = re.findall(r"^#{2,6}\s+(.+?)\s*$", body, re.MULTILINE)
        heading_slugs = {gen_docs._heading_slug(h) for h in headings}
        assert heading_slugs, "expected at least one folded heading in the generated page"

        anchors = re.findall(r"\]\(#([^)]*)\)", body)
        assert anchors, "expected at least one intra-page anchor link in the generated page"

        # "#" (bare, empty anchor) is the deliberate back-to-top-of-page link
        # produced for a same-skill ../SKILL.md reference -- it has no heading
        # to resolve against by design, so it's excluded from the resolution
        # check below rather than silently satisfied by it.
        section_anchors = [a for a in anchors if a]
        assert section_anchors, "expected at least one non-top-of-page anchor"
        for anchor in section_anchors:
            assert anchor in heading_slugs, (
                f"anchor #{anchor} does not resolve to any real folded heading; "
                f"available headings slug to {sorted(heading_slugs)}"
            )

        # Literal pins on the exact regression: these must be present verbatim
        # in the emitted links, independent of whatever _heading_slug computes
        # at test time (see class docstring for why the generic check above
        # can't catch a regression in _heading_slug on its own).
        assert f"](#{self.EXPECTED_FOO_ANCHOR[1:]})" in body
        assert f"](#{self.EXPECTED_BAR_ANCHOR[1:]})" in body
        assert "_" in self.EXPECTED_FOO_ANCHOR  # underscore survives
        assert "--" in self.EXPECTED_BAR_ANCHOR  # em-dash idiom keeps a double hyphen