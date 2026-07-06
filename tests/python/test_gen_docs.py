"""Tests for scripts/gen_docs.py Starlight generation rules."""

from __future__ import annotations

import importlib.util
import re
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
    monkeypatch.setattr(gen_docs, "SHARED_DIR", tmp_path / "shared")
    monkeypatch.setattr(gen_docs, "CONTENT_ROOT", tmp_path / "src" / "content" / "docs")
    monkeypatch.setattr(gen_docs, "SIDEBAR_PATH", tmp_path / "src" / "sidebar.mjs")
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

    def test_local_reference_resolves_from_skill_route(self, gen_docs):
        assert gen_docs.rewrite_skill_link("references/foo.md", "cook") == "references/foo/"

    def test_local_reference_keeps_anchor(self, gen_docs):
        assert gen_docs.rewrite_skill_link("references/foo.md#part", "cook") == "references/foo/#part"

    def test_cross_skill_skill_md_routes_to_sibling_skill(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../press/SKILL.md", "cook") == "../press/"

    def test_cross_skill_skill_md_with_anchor(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../press/SKILL.md#auto-mode", "cook") == "../press/#auto-mode"

    def test_cross_skill_reference(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../press/references/quality-gates.md", "cook") == "../press/references/quality-gates/"

    def test_root_doc_resolves_to_root_route(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../../CONTRIBUTING.md", "cook") == "../../contributing/"
        assert gen_docs.rewrite_skill_link("../../SECURITY.md", "cook") == "../../security/"
        assert gen_docs.rewrite_skill_link("../../README.md", "cook") == "../../readme/"

    def test_license_becomes_absolute_repo_url(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../../LICENSE", "cook") == f"{gen_docs.REPO_URL}/blob/main/LICENSE"

    def test_unknown_path_is_untouched(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../../some/other/file.md", "cook") == "../../some/other/file.md"

    def test_shared_contract_link_climbs_to_root_shared_route(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../../shared/handoff-gate.md", "age") == "../../shared/handoff-gate/"

    def test_shared_contract_link_preserves_anchor(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../../shared/handoff-gate.md#vocabulary", "age") == "../../shared/handoff-gate/#vocabulary"


class TestRewriteRefLink:
    def test_external_urls_pass_through(self, gen_docs):
        for url in ("https://example.com", "mailto:x@y.z", "#anchor"):
            assert gen_docs.rewrite_ref_link(url, "press") == url

    def test_sibling_reference(self, gen_docs):
        assert gen_docs.rewrite_ref_link("adr.md", "mold") == "../adr/"

    def test_sibling_skill_md(self, gen_docs):
        assert gen_docs.rewrite_ref_link("../SKILL.md", "press") == "../../"
        assert gen_docs.rewrite_ref_link("../SKILL.md#auto", "press") == "../../#auto"

    def test_cross_skill_skill_md(self, gen_docs):
        assert gen_docs.rewrite_ref_link("../../cook/SKILL.md", "press") == "../../../cook/"

    def test_cross_skill_reference(self, gen_docs):
        assert gen_docs.rewrite_ref_link("../../cook/references/foo.md", "press") == "../../../cook/references/foo/"

    def test_root_doc(self, gen_docs):
        assert gen_docs.rewrite_ref_link("../../../CONTRIBUTING.md", "press") == "../../../../contributing/"
        assert gen_docs.rewrite_ref_link("../../../README.md", "press") == "../../../../readme/"

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
        assert gen_docs.rewrite_root_passthrough_link("skills/age/references/voice.md") == "../skills/age/references/voice/"

    def test_shared_reference(self, gen_docs):
        assert gen_docs.rewrite_root_passthrough_link("shared/formatting.md") == "../shared/formatting/"

    def test_unknown_path_untouched(self, gen_docs):
        assert gen_docs.rewrite_root_passthrough_link("skills/cook/SKILL.md") == "../skills/cook/"


class TestRewriteSharedLink:
    def test_external_pass_through(self, gen_docs):
        for url in ("https://example.com", "mailto:x@y.z", "#anchor"):
            assert gen_docs.rewrite_shared_link(url) == url

    def test_sibling_shared_doc(self, gen_docs):
        assert gen_docs.rewrite_shared_link("harness-portability.md") == "../harness-portability/"
        assert gen_docs.rewrite_shared_link("./harness-portability.md#tools") == "../harness-portability/#tools"

    def test_root_doc(self, gen_docs):
        assert gen_docs.rewrite_shared_link("../README.md") == "../../readme/"

    def test_skill_doc(self, gen_docs):
        assert gen_docs.rewrite_shared_link("../skills/cook/SKILL.md#flow") == "../../skills/cook/#flow"


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
        assert "# Install" in body
        assert "## gh skill" in body


class TestEmitSkillPage:
    def test_writes_skill_and_nested_reference_pages(self, gen_docs, isolated_docs):
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
        ref_out = isolated_docs / "src" / "content" / "docs" / "skills" / "cook" / "references" / "gate.md"
        assert page == gen_docs.GeneratedPage(
            "/cook",
            "skills/cook",
            "skills/cook/SKILL.md",
            [gen_docs.GeneratedPage("Gate", "skills/cook/references/gate", "skills/cook/references/gate.md")],
        )
        skill_body = skill_out.read_text(encoding="utf-8")
        assert "title: /cook" in skill_body
        assert ":::note[Skill metadata]" in skill_body
        assert "- **Source:** [`skills/cook/SKILL.md`](https://github.com/paulnsorensen/easy-cheese/blob/main/skills/cook/SKILL.md)" in skill_body
        assert "See [gate](references/gate/)." in skill_body
        assert "editUrl: https://github.com/paulnsorensen/easy-cheese/edit/main/skills/cook/SKILL.md" in skill_body
        assert "Back to [skill](../../)." in ref_out.read_text(encoding="utf-8")


class TestEmitSharedPages:
    def test_missing_dir_returns_empty(self, gen_docs, isolated_docs):
        assert gen_docs.emit_shared_pages() == []

    def test_empty_dir_returns_empty(self, gen_docs, isolated_docs):
        (isolated_docs / "shared").mkdir()
        assert gen_docs.emit_shared_pages() == []

    def test_emits_markdown_with_frontmatter_and_uses_h1_as_title(self, gen_docs, isolated_docs):
        shared = isolated_docs / "shared"
        shared.mkdir()
        (shared / "handoff-gate.md").write_text("# Handoff gate\n\nSee [portability](harness-portability.md).\n", encoding="utf-8")

        entries = gen_docs.emit_shared_pages()

        assert entries == [gen_docs.GeneratedPage("Handoff gate", "shared/handoff-gate", "shared/handoff-gate.md")]
        out = isolated_docs / "src" / "content" / "docs" / "shared" / "handoff-gate.md"
        assert out.read_text(encoding="utf-8").startswith("---\ntitle: Handoff gate\neditUrl:")
        assert "# Handoff gate\n\nSee [portability](../harness-portability/).\n" in out.read_text(encoding="utf-8")

    def test_falls_back_to_slug_when_no_h1(self, gen_docs, isolated_docs):
        shared = isolated_docs / "shared"
        shared.mkdir()
        (shared / "no-h1.md").write_text("just body, no heading\n", encoding="utf-8")

        entries = gen_docs.emit_shared_pages()

        assert entries == [gen_docs.GeneratedPage("No h1", "shared/no-h1", "shared/no-h1.md")]

    def test_skips_non_markdown_files(self, gen_docs, isolated_docs):
        shared = isolated_docs / "shared"
        shared.mkdir()
        (shared / "handoff-gate.md").write_text("# Gate\n", encoding="utf-8")
        (shared / "schema.json").write_text("{}", encoding="utf-8")
        (shared / "notes.txt").write_text("ignore me", encoding="utf-8")

        entries = gen_docs.emit_shared_pages()

        assert [entry.slug for entry in entries] == ["shared/handoff-gate"]
        assert sorted(p.name for p in (isolated_docs / "src" / "content" / "docs" / "shared").iterdir()) == ["handoff-gate.md"]

    def test_multiple_files_sorted(self, gen_docs, isolated_docs):
        shared = isolated_docs / "shared"
        shared.mkdir()
        (shared / "zebra.md").write_text("# Zebra\n", encoding="utf-8")
        (shared / "alpha.md").write_text("# Alpha\n", encoding="utf-8")

        entries = gen_docs.emit_shared_pages()

        assert [entry.slug for entry in entries] == ["shared/alpha", "shared/zebra"]


class TestEmitSidebar:
    def test_writes_sidebar_module_with_nested_refs(self, gen_docs, isolated_docs):
        skill = gen_docs.GeneratedPage(
            "/age",
            "skills/age",
            "skills/age/SKILL.md",
            [gen_docs.GeneratedPage("Voice", "skills/age/references/voice", "skills/age/references/voice.md")],
        )
        shared = gen_docs.GeneratedPage("Formatting", "shared/formatting", "shared/formatting.md")
        project = gen_docs.GeneratedPage("README", "readme", "README.md")

        gen_docs.emit_sidebar([skill], [shared], [project])

        out = (isolated_docs / "src" / "sidebar.mjs").read_text(encoding="utf-8")
        assert out.startswith("// Generated by scripts/gen_docs.py")
        assert "export const sidebar" in out
        assert '"label": "Skills"' in out
        assert '"slug": "skills/age"' in out
        assert '"slug": "skills/age/references/voice"' in out
        assert '"label": "Shared contracts"' in out
        assert "SUMMARY.md" not in out

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
        shared = isolated_docs / "shared"
        shared.mkdir()
        (shared / "formatting.md").write_text("# Formatting\n\nSee [portability](harness-portability.md).\n", encoding="utf-8")

        gen_docs.main()

        root = isolated_docs / "src" / "content" / "docs"
        assert (root / "index.md").read_text(encoding="utf-8") == "authored"
        assert (root / "install.md").exists()
        assert (root / "skills" / "index.md").exists()
        assert (root / "skills" / "age.md").exists()
        assert (root / "skills" / "age" / "references" / "voice.md").exists()
        assert (root / "shared" / "formatting.md").exists()
        assert (root / "readme.md").exists()
        assert (root / "contributing.md").exists()
        assert (isolated_docs / "src" / "sidebar.mjs").exists()
        assert not (root / "SUMMARY.md").exists()
        generated_markdown = "\n".join(p.read_text(encoding="utf-8") for p in root.rglob("*.md"))
        assert not re.search(r"\]\((?!https?://|mailto:|#)[^)]+\.md(?:#[^)]*)?\)", generated_markdown)
