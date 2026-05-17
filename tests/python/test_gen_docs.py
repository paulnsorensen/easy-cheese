"""Tests for scripts/gen_docs.py link-rewrite rules.

The generator's only non-trivial logic is link rewriting between three
coordinate spaces (skill body, reference body, root passthrough). A regression
here silently produces broken docs links, so each case gets a targeted test.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GEN_DOCS = REPO_ROOT / "scripts" / "gen_docs.py"


@pytest.fixture(scope="module")
def gen_docs() -> ModuleType:
    """Import gen_docs.py without executing main() (mkdocs_gen_files isn't on PATH outside the docs venv)."""
    sys.modules.setdefault("mkdocs_gen_files", _stub_mkdocs_gen_files())
    spec = importlib.util.spec_from_file_location("gen_docs", GEN_DOCS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Block main() from running on import — it would try to walk skills/ and write into the stub.
    src = GEN_DOCS.read_text(encoding="utf-8").replace("\nmain()\n", "\n")
    exec(compile(src, str(GEN_DOCS), "exec"), module.__dict__)
    return module


def _stub_mkdocs_gen_files() -> ModuleType:
    import types

    mod = types.ModuleType("mkdocs_gen_files")

    class _Sink:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def write(self, _data):
            return None

    setattr(mod, "open", lambda *_a, **_kw: _Sink())
    setattr(mod, "set_edit_path", lambda *_a, **_kw: None)
    return mod


class TestRewriteSkillLink:
    def test_external_urls_pass_through(self, gen_docs):
        for url in (
            "https://example.com",
            "http://example.com",
            "mailto:x@y.z",
            "#section",
        ):
            assert gen_docs.rewrite_skill_link(url, "cook") == url

    def test_local_reference_resolves_under_skill(self, gen_docs):
        assert gen_docs.rewrite_skill_link("references/foo.md", "cook") == "cook/references/foo.md"

    def test_local_reference_keeps_anchor(self, gen_docs):
        assert (
            gen_docs.rewrite_skill_link("references/foo.md#part", "cook")
            == "cook/references/foo.md#part"
        )

    def test_cross_skill_skill_md_flattens(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../press/SKILL.md", "cook") == "press.md"

    def test_cross_skill_skill_md_with_anchor(self, gen_docs):
        assert (
            gen_docs.rewrite_skill_link("../press/SKILL.md#auto-mode", "cook")
            == "press.md#auto-mode"
        )

    def test_cross_skill_reference(self, gen_docs):
        assert (
            gen_docs.rewrite_skill_link("../press/references/quality-gates.md", "cook")
            == "press/references/quality-gates.md"
        )

    def test_root_doc_resolves_up_one_level(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../../CONTRIBUTING.md", "cook") == "../contributing.md"
        assert gen_docs.rewrite_skill_link("../../SECURITY.md", "cook") == "../security.md"
        assert gen_docs.rewrite_skill_link("../../README.md", "cook") == "../readme.md"

    def test_license_becomes_absolute_repo_url(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../../LICENSE", "cook") == f"{gen_docs.REPO_URL}/blob/main/LICENSE"

    def test_unknown_path_is_untouched(self, gen_docs):
        assert gen_docs.rewrite_skill_link("../../some/other/file.md", "cook") == "../../some/other/file.md"

    def test_shared_contract_link_climbs_one_level(self, gen_docs):
        # Source skills/<name>/SKILL.md uses ../../shared/<file>.md (two ups:
        # skills/<name>/ -> skills/ -> repo_root, then shared/). After
        # flattening to docs/skills/<name>.md the `<name>/` directory is gone,
        # so only one `..` is needed to reach docs/shared/<file>.md.
        assert (
            gen_docs.rewrite_skill_link("../../shared/handoff-gate.md", "age")
            == "../shared/handoff-gate.md"
        )

    def test_shared_contract_link_preserves_anchor(self, gen_docs):
        assert (
            gen_docs.rewrite_skill_link("../../shared/handoff-gate.md#vocabulary", "age")
            == "../shared/handoff-gate.md#vocabulary"
        )


class TestRewriteRefLink:
    def test_external_urls_pass_through(self, gen_docs):
        for url in ("https://example.com", "mailto:x@y.z", "#anchor"):
            assert gen_docs.rewrite_ref_link(url, "press") == url

    def test_sibling_skill_md(self, gen_docs):
        assert gen_docs.rewrite_ref_link("../SKILL.md", "press") == "../../press.md"
        assert gen_docs.rewrite_ref_link("../SKILL.md#auto", "press") == "../../press.md#auto"

    def test_cross_skill_skill_md(self, gen_docs):
        assert gen_docs.rewrite_ref_link("../../cook/SKILL.md", "press") == "../../cook.md"

    def test_cross_skill_reference(self, gen_docs):
        assert (
            gen_docs.rewrite_ref_link("../../cook/references/foo.md", "press")
            == "../../cook/references/foo.md"
        )

    def test_root_doc(self, gen_docs):
        assert gen_docs.rewrite_ref_link("../../../CONTRIBUTING.md", "press") == "../../../contributing.md"
        assert gen_docs.rewrite_ref_link("../../../README.md", "press") == "../../../readme.md"

    def test_license(self, gen_docs):
        assert (
            gen_docs.rewrite_ref_link("../../../LICENSE", "press")
            == f"{gen_docs.REPO_URL}/blob/main/LICENSE"
        )


class TestRewriteRootPassthroughLink:
    def test_external_pass_through(self, gen_docs):
        for url in ("https://example.com", "mailto:x@y.z", "#anchor"):
            assert gen_docs.rewrite_root_passthrough_link(url) == url

    def test_known_root_doc(self, gen_docs):
        assert gen_docs.rewrite_root_passthrough_link("CONTRIBUTING.md") == "./contributing.md"
        assert gen_docs.rewrite_root_passthrough_link("./SECURITY.md") == "./security.md"
        assert gen_docs.rewrite_root_passthrough_link("CODE_OF_CONDUCT.md") == "./code-of-conduct.md"

    def test_known_root_doc_with_anchor(self, gen_docs):
        assert (
            gen_docs.rewrite_root_passthrough_link("./CONTRIBUTING.md#pull-requests")
            == "./contributing.md#pull-requests"
        )

    def test_license(self, gen_docs):
        assert (
            gen_docs.rewrite_root_passthrough_link("LICENSE")
            == f"{gen_docs.REPO_URL}/blob/main/LICENSE"
        )

    def test_unknown_path_untouched(self, gen_docs):
        assert gen_docs.rewrite_root_passthrough_link("skills/cook/SKILL.md") == "skills/cook/SKILL.md"


class TestApplyLinkRewrite:
    def test_rewrites_markdown_link(self, gen_docs):
        text = "See [the press skill](../press/SKILL.md) for more."
        out = gen_docs.apply_link_rewrite(text, lambda u: gen_docs.rewrite_skill_link(u, "cook"))
        assert out == "See [the press skill](press.md) for more."

    def test_rewrites_link_with_title(self, gen_docs):
        text = '[link](../press/SKILL.md "Press skill")'
        out = gen_docs.apply_link_rewrite(text, lambda u: gen_docs.rewrite_skill_link(u, "cook"))
        assert out == '[link](press.md "Press skill")'

    def test_leaves_inline_images_alone(self, gen_docs):
        text = "![alt](references/diagram.png)"
        out = gen_docs.apply_link_rewrite(text, lambda u: gen_docs.rewrite_skill_link(u, "cook"))
        assert out == "![alt](references/diagram.png)"

    def test_rewrites_nested_image_link(self, gen_docs):
        text = "[![alt](logo.png)](../press/SKILL.md)"
        out = gen_docs.apply_link_rewrite(text, lambda u: gen_docs.rewrite_skill_link(u, "cook"))
        assert out == "[![alt](logo.png)](press.md)"


class TestFirstSentence:
    def test_grabs_first_sentence(self, gen_docs):
        assert gen_docs.first_sentence("First sentence. Second.") == "First sentence."

    def test_handles_newlines(self, gen_docs):
        assert gen_docs.first_sentence("First\nsentence.\n\nSecond.") == "First sentence."

    def test_caps_at_240_chars(self, gen_docs):
        long = "x" * 300
        assert len(gen_docs.first_sentence(long)) == 240


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

    def test_missing_section_returns_empty(self, gen_docs):
        text = "## A\nbody-a\n\n## B\nbody-b\n"
        assert gen_docs.extract_h2_section(text, "Z") == ""

    def test_section_runs_to_eof_when_no_next_h2(self, gen_docs):
        text = "## A\nbody-a\nstill-a\n"
        assert gen_docs.extract_h2_section(text, "A") == "## A\nbody-a\nstill-a\n"

    def test_ignores_h3_with_matching_text(self, gen_docs):
        # Only H2s anchor the section boundary; H3 with same name shouldn't trip it.
        text = "## A\nbody-a\n### A\nstill-a\n\n## B\nbody-b\n"
        out = gen_docs.extract_h2_section(text, "A")
        assert "still-a" in out
        assert "body-b" not in out


class TestEmitInstallPage:
    def _write_full_readme(self, path):
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

    def test_missing_readme_returns_false(self, gen_docs, tmp_path, monkeypatch):
        monkeypatch.setattr(gen_docs, "REPO_ROOT", tmp_path)
        assert gen_docs.emit_install_page() is False

    def test_missing_section_raises_with_named_section(self, gen_docs, tmp_path, monkeypatch):
        (tmp_path / "README.md").write_text(
            "## Optional tools\n\ntable\n\n"
            "## Install\n\ninstall\n\n"
            "## Installing MCP servers\n\nmcp\n"
            # "Installing CLI tools" intentionally absent
        )
        monkeypatch.setattr(gen_docs, "REPO_ROOT", tmp_path)
        with pytest.raises(RuntimeError, match=r"Installing CLI tools"):
            gen_docs.emit_install_page()

    def test_missing_section_message_names_all_gaps(self, gen_docs, tmp_path, monkeypatch):
        (tmp_path / "README.md").write_text("## Install\n\ninstall\n")
        monkeypatch.setattr(gen_docs, "REPO_ROOT", tmp_path)
        with pytest.raises(RuntimeError) as exc:
            gen_docs.emit_install_page()
        msg = str(exc.value)
        assert "Installing MCP servers" in msg
        assert "Optional tools" in msg
        assert "Installing CLI tools" in msg

    def test_all_sections_present_returns_true(self, gen_docs, tmp_path, monkeypatch):
        self._write_full_readme(tmp_path / "README.md")
        monkeypatch.setattr(gen_docs, "REPO_ROOT", tmp_path)
        assert gen_docs.emit_install_page() is True


class TestEmitSharedPages:
    """emit_shared_pages mirrors shared/*.md into the docs tree.

    The function is what makes the ``../../shared/<file>.md`` links from
    skill SKILL.md bodies actually resolve under mkdocs --strict. We test
    the contract end-to-end: an empty dir is a no-op, files get copied,
    non-Markdown files are skipped, and titles fall back to the slug.
    """

    def _capture_writes(self, gen_docs, monkeypatch):
        """Intercept mkdocs_gen_files.open() so we can assert on its writes."""
        writes: dict[str, str] = {}

        class _Capturing:
            def __init__(self, key):
                self.key = key
                self.buf: list[str] = []

            def __enter__(self):
                return self

            def __exit__(self, *_):
                writes[self.key] = "".join(self.buf)
                return False

            def write(self, data):
                self.buf.append(data)

        import mkdocs_gen_files

        monkeypatch.setattr(mkdocs_gen_files, "open", lambda key, *_a, **_kw: _Capturing(key))
        monkeypatch.setattr(mkdocs_gen_files, "set_edit_path", lambda *_a, **_kw: None)
        return writes

    def test_missing_dir_returns_empty(self, gen_docs, tmp_path, monkeypatch):
        monkeypatch.setattr(gen_docs, "SHARED_DIR", tmp_path / "nope")
        assert gen_docs.emit_shared_pages() == []

    def test_empty_dir_returns_empty(self, gen_docs, tmp_path, monkeypatch):
        (tmp_path / "shared").mkdir()
        monkeypatch.setattr(gen_docs, "SHARED_DIR", tmp_path / "shared")
        monkeypatch.setattr(gen_docs, "REPO_ROOT", tmp_path)
        assert gen_docs.emit_shared_pages() == []

    def test_emits_markdown_and_uses_h1_as_title(self, gen_docs, tmp_path, monkeypatch):
        shared = tmp_path / "shared"
        shared.mkdir()
        (shared / "handoff-gate.md").write_text("# Handoff gate\n\nbody\n", encoding="utf-8")
        monkeypatch.setattr(gen_docs, "SHARED_DIR", shared)
        monkeypatch.setattr(gen_docs, "REPO_ROOT", tmp_path)
        writes = self._capture_writes(gen_docs, monkeypatch)

        entries = gen_docs.emit_shared_pages()

        assert entries == [("Handoff gate", "shared/handoff-gate.md")]
        assert writes["shared/handoff-gate.md"] == "# Handoff gate\n\nbody\n"

    def test_falls_back_to_slug_when_no_h1(self, gen_docs, tmp_path, monkeypatch):
        shared = tmp_path / "shared"
        shared.mkdir()
        (shared / "no-h1.md").write_text("just body, no heading\n", encoding="utf-8")
        monkeypatch.setattr(gen_docs, "SHARED_DIR", shared)
        monkeypatch.setattr(gen_docs, "REPO_ROOT", tmp_path)
        self._capture_writes(gen_docs, monkeypatch)

        entries = gen_docs.emit_shared_pages()

        assert entries == [("No h1", "shared/no-h1.md")]

    def test_skips_non_markdown_files(self, gen_docs, tmp_path, monkeypatch):
        shared = tmp_path / "shared"
        shared.mkdir()
        (shared / "handoff-gate.md").write_text("# Gate\n", encoding="utf-8")
        (shared / "schema.json").write_text("{}", encoding="utf-8")
        (shared / "notes.txt").write_text("ignore me", encoding="utf-8")
        monkeypatch.setattr(gen_docs, "SHARED_DIR", shared)
        monkeypatch.setattr(gen_docs, "REPO_ROOT", tmp_path)
        writes = self._capture_writes(gen_docs, monkeypatch)

        entries = gen_docs.emit_shared_pages()

        # Only the .md file lands in the docs tree (and the nav).
        assert [path for _, path in entries] == ["shared/handoff-gate.md"]
        assert set(writes) == {"shared/handoff-gate.md"}

    def test_multiple_files_sorted(self, gen_docs, tmp_path, monkeypatch):
        shared = tmp_path / "shared"
        shared.mkdir()
        (shared / "zebra.md").write_text("# Zebra\n", encoding="utf-8")
        (shared / "alpha.md").write_text("# Alpha\n", encoding="utf-8")
        monkeypatch.setattr(gen_docs, "SHARED_DIR", shared)
        monkeypatch.setattr(gen_docs, "REPO_ROOT", tmp_path)
        self._capture_writes(gen_docs, monkeypatch)

        entries = gen_docs.emit_shared_pages()

        # Sorted by source filename — keeps the generated nav stable across runs.
        assert [path for _, path in entries] == ["shared/alpha.md", "shared/zebra.md"]


class TestEmitNav:
    """emit_nav renders the literate-nav SUMMARY.md.

    The shared-contracts section is only added when at least one shared
    page exists; otherwise mkdocs --strict would warn about an empty group.
    """

    def _captured_summary(self, gen_docs, monkeypatch):
        buf: list[str] = []

        class _Sink:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def write(self, data):
                buf.append(data)

        import mkdocs_gen_files

        monkeypatch.setattr(mkdocs_gen_files, "open", lambda *_a, **_kw: _Sink())
        monkeypatch.setattr(mkdocs_gen_files, "set_edit_path", lambda *_a, **_kw: None)
        return buf

    def test_includes_shared_section_when_present(self, gen_docs, monkeypatch):
        buf = self._captured_summary(gen_docs, monkeypatch)
        gen_docs.emit_nav(
            skills=[{"name": "age", "refs": []}],
            shared=[("Handoff gate", "shared/handoff-gate.md")],
            extras=[],
        )
        out = "".join(buf)
        assert "* Shared contracts" in out
        assert "* [Handoff gate](shared/handoff-gate.md)" in out

    def test_omits_shared_section_when_empty(self, gen_docs, monkeypatch):
        buf = self._captured_summary(gen_docs, monkeypatch)
        gen_docs.emit_nav(
            skills=[{"name": "age", "refs": []}],
            shared=[],
            extras=[("README", "readme.md")],
        )
        out = "".join(buf)
        assert "Shared contracts" not in out
