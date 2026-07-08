"""Generate Starlight docs pages from skill sources at build time."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
CONTENT_ROOT = REPO_ROOT / "src" / "content" / "docs"
SIDEBAR_PATH = REPO_ROOT / "src" / "sidebar.mjs"
REPO_URL = "https://github.com/paulnsorensen/easy-cheese"
EDIT_URL_BASE = f"{REPO_URL}/edit/main/"
LICENSE_URL = f"{REPO_URL}/blob/main/LICENSE"

LINK_RE = re.compile(r"(?<!\!)\[([^\]]+)\]\(([^)\s]+)(\s+\"[^\"]*\")?\)")
NESTED_IMAGE_LINK_RE = re.compile(r"(\[!\[[^\]]*\]\([^)]+\)\]\()([^)\s]+)(\))")
ADMONITION_RE = re.compile(r'^!!!\s+(\w+)(?:\s+"([^"]+)")?\n((?:    .*\n?|\s*\n)+)', re.MULTILINE)

ROOT_DOC_MAP = {
    "README.md": "readme/",
    "CONTRIBUTING.md": "contributing/",
    "SECURITY.md": "security/",
    "CODE_OF_CONDUCT.md": "code-of-conduct/",
}

AUTHORED_DOCS = {
    "index.md",
}


@dataclass(frozen=True)
class GeneratedPage:
    title: str
    slug: str
    source_rel: str | None


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + 5 :]
    try:
        meta = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, body


def first_sentence(desc: str) -> str:
    desc = desc.replace("\n", " ").strip()
    match = re.search(r"^(.*?[.!?])(\s|$)", desc)
    return (match.group(1) if match else desc)[:240]


def _split_anchor(path: str) -> tuple[str, str]:
    if "#" in path:
        base, anchor = path.split("#", 1)
        return base, "#" + anchor
    return path, ""


def _is_external(url: str) -> bool:
    return url.startswith(("http://", "https://", "mailto:", "#"))


@lru_cache(maxsize=None)
def _read_text_cached(path: Path, _mtime: float) -> str:
    return path.read_text(encoding="utf-8")


def _read_text(path: Path) -> str:
    # README.md is consumed by both emit_install_page and emit_root_passthrough;
    # cache so each repo file is read from disk once per build. Keyed on mtime so a
    # changed file is never served stale if these are ever re-driven in-process.
    return _read_text_cached(path, path.stat().st_mtime)


def _strip_md_suffix(path: str) -> str:
    return path[:-3] if path.endswith(".md") else path


def _doc_path_for_slug(slug: str) -> str:
    return f"{slug}.md" if slug else "index.md"


def _source_edit_url(source_rel: str | None) -> str | bool:
    return f"{EDIT_URL_BASE}{source_rel}" if source_rel else False


def starlight_frontmatter(
    *,
    title: str,
    description: str | None = None,
    edit_url: str | bool | None = None,
    template: str | None = None,
) -> str:
    data: dict[str, object] = {"title": title}
    if description:
        data["description"] = description
    if edit_url is not None:
        data["editUrl"] = edit_url
    if template:
        data["template"] = template
    return "---\n" + yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ) + "---\n\n"


def write_doc(
    relative_doc_path: str,
    content: str,
    *,
    title: str,
    description: str | None = None,
    source_rel: str | None = None,
) -> GeneratedPage:
    target = CONTENT_ROOT / relative_doc_path
    target.parent.mkdir(parents=True, exist_ok=True)
    # Starlight renders the frontmatter title as the page H1; a literal leading
    # `# …` in the body would show the heading twice.
    body = re.sub(r"^#\s[^\n]*\n+", "", content.lstrip(), count=1)
    target.write_text(
        starlight_frontmatter(
            title=title,
            description=description,
            edit_url=_source_edit_url(source_rel),
        ) + body,
        encoding="utf-8",
    )
    slug = _strip_md_suffix(relative_doc_path.removesuffix("/index.md"))
    if relative_doc_path == "index.md":
        slug = ""
    return GeneratedPage(title=title, slug=slug, source_rel=source_rel)


def convert_mkdocs_admonitions(markdown: str) -> str:
    def repl(match: re.Match) -> str:
        kind = match.group(1)
        title = match.group(2)
        body = match.group(3)
        stripped = []
        for line in body.splitlines():
            if line.startswith("    "):
                stripped.append(line[4:])
            else:
                stripped.append(line)
        label = f"[{title}]" if title else ""
        return f":::{kind}{label}\n" + "\n".join(stripped).rstrip() + "\n:::\n"

    return ADMONITION_RE.sub(repl, markdown)


# github-slugger (the slugger Starlight's markdown renderer uses to assign
# heading ids) applied to this repo's heading titles: lowercase, drop every
# char that is not a word char / hyphen / space, then turn each space into a
# hyphen. It KEEPS underscores and does NOT collapse repeated separators, which
# is what github-slugger does on these ASCII titles (e.g. "tilth_write JSON
# cookbook" -> "tilth_write-json-cookbook"; "Cascade stages \u2014 branch-specific
# steps" -> "cascade-stages--branch-specific-steps"). Verified byte-for-byte
# against the installed github-slugger over every real heading title
# (tests/python/test_gen_docs.py::TestHeadingSlug pins the golden cases).
_HEADING_SLUG_STRIP_RE = re.compile(r"[^\w\- ]", re.UNICODE)


def _heading_slug(text: str) -> str:
    return _HEADING_SLUG_STRIP_RE.sub("", text.lower()).replace(" ", "-")


def _ref_title(skill_name: str, ref_stem: str) -> str:
    return _ref_title_cached(str(SKILLS_DIR), skill_name, ref_stem)


@lru_cache(maxsize=None)
def _ref_title_cached(skills_dir: str, skill_name: str, ref_stem: str) -> str:
    ref_path = Path(skills_dir) / skill_name / "references" / f"{ref_stem}.md"
    try:
        text = ref_path.read_text(encoding="utf-8")
    except OSError:
        return _heading_slug(ref_stem.replace("-", " "))
    meta, body = parse_frontmatter(text)
    title = meta.get("title") or _first_h1(body) or ref_stem.replace("-", " ").capitalize()
    return _heading_slug(title)


_ref_title.cache_clear = _ref_title_cached.cache_clear


def rewrite_skill_link(url: str, skill_name: str) -> str:
    if _is_external(url):
        return url
    path, anchor = _split_anchor(url)

    m = re.match(r"^references/(.+)\.md$", path)
    if m:
        return anchor if anchor else f"#{_ref_title(skill_name, m.group(1))}"

    m = re.match(r"^\.\./([^/]+)/SKILL\.md$", path)
    if m:
        return f"../{m.group(1)}/{anchor}"

    m = re.match(r"^\.\./([^/]+)/references/(.+)\.md$", path)
    if m:
        other_skill, stem = m.group(1), m.group(2)
        if anchor:
            return f"../{other_skill}/{anchor}"
        return f"../{other_skill}/#{_ref_title(other_skill, stem)}"

    m = re.match(r"^\.\./\.\./([A-Z_]+\.md)$", path)
    if m and m.group(1) in ROOT_DOC_MAP:
        return f"../../{ROOT_DOC_MAP[m.group(1)]}{anchor}"
    if path == "../../LICENSE":
        return LICENSE_URL

    return url


def rewrite_ref_link(url: str, skill_name: str) -> str:
    if _is_external(url):
        return url
    path, anchor = _split_anchor(url)

    m = re.match(r"^([^/]+)\.md$", path)
    if m:
        return anchor if anchor else f"#{_ref_title(skill_name, m.group(1))}"
    if path == "../SKILL.md":
        return anchor if anchor else "#"

    m = re.match(r"^\.\./\.\./([^/]+)/SKILL\.md$", path)
    if m:
        return f"../{m.group(1)}/{anchor}"

    m = re.match(r"^\.\./\.\./([^/]+)/references/(.+)\.md$", path)
    if m:
        other_skill, stem = m.group(1), m.group(2)
        if anchor:
            return f"../{other_skill}/{anchor}"
        return f"../{other_skill}/#{_ref_title(other_skill, stem)}"

    m = re.match(r"^\.\./\.\./\.\./([A-Z_]+\.md)$", path)
    if m and m.group(1) in ROOT_DOC_MAP:
        return f"../../{ROOT_DOC_MAP[m.group(1)]}{anchor}"
    if path == "../../../LICENSE":
        return LICENSE_URL

    return url


def rewrite_root_passthrough_link(url: str) -> str:
    if _is_external(url):
        return url
    path, anchor = _split_anchor(url)
    stripped = path[2:] if path.startswith("./") else path

    if stripped in ROOT_DOC_MAP:
        return f"../{ROOT_DOC_MAP[stripped]}{anchor}"
    if stripped == "LICENSE":
        return LICENSE_URL

    m = re.match(r"^skills/([^/]+)/SKILL\.md$", stripped)
    if m:
        return f"../skills/{m.group(1)}/{anchor}"

    m = re.match(r"^skills/([^/]+)/references/(.+)\.md$", stripped)
    if m:
        other_skill, stem = m.group(1), m.group(2)
        if anchor:
            return f"../skills/{other_skill}/{anchor}"
        return f"../skills/{other_skill}/#{_ref_title(other_skill, stem)}"

    return url


def apply_link_rewrite(text: str, rewriter: Callable[[str], str]) -> str:
    def image_repl(match: re.Match) -> str:
        prefix, url, suffix = match.group(1), match.group(2), match.group(3)
        return f"{prefix}{rewriter(url)}{suffix}"

    def repl(match: re.Match) -> str:
        label, url, title = match.group(1), match.group(2), match.group(3) or ""
        return f"[{label}]({rewriter(url)}{title})"

    return LINK_RE.sub(repl, NESTED_IMAGE_LINK_RE.sub(image_repl, text))


HEADING_RE = re.compile(r"^(#{1,5})(\s)", re.MULTILINE)


def _bump_headings(text: str) -> str:
    """Demote markdown headings one level, leaving fenced code blocks untouched."""
    lines = text.split("\n")
    in_fence = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines[i] = HEADING_RE.sub(lambda m: "#" + m.group(1) + m.group(2), line)
    return "\n".join(lines)


def fold_references(skill_name: str, refs_dir: Path) -> tuple[str, dict[str, str]]:
    titles: dict[str, str] = {}
    sections: list[str] = []
    if not refs_dir.is_dir():
        return "", titles

    for ref in sorted(p for p in refs_dir.iterdir() if p.is_file()):
        if ref.suffix.lower() != ".md":
            continue
        stem = ref.stem
        meta, body = parse_frontmatter(ref.read_text(encoding="utf-8"))
        body = apply_link_rewrite(body, lambda url: rewrite_ref_link(url, skill_name))
        body = convert_mkdocs_admonitions(body)
        title = meta.get("title") or _first_h1(body) or stem.replace("-", " ").capitalize()
        titles[stem] = title
        body = re.sub(r"^#\s[^\n]*\n+", "", body.lstrip(), count=1)
        body = _bump_headings(body)
        sections.append(f"## {title}\n\n{body.rstrip()}\n")

    return "\n\n".join(sections), titles


def emit_skill_page(skill_dir: Path) -> GeneratedPage | None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None

    meta, body = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    name = meta.get("name") or skill_dir.name
    description = meta.get("description", "").strip()
    license_id = meta.get("license", "MIT")

    src_rel = skill_md.relative_to(REPO_ROOT).as_posix()
    page_path = f"skills/{name}.md"

    header = (
        f":::note[Skill metadata]\n"
        f"- **License:** {license_id}\n"
        f"- **Source:** [`{src_rel}`]({REPO_URL}/blob/main/{src_rel})\n"
        f":::\n\n"
        f"**When to invoke:** {description}\n\n"
        f"---\n\n"
    )

    body = re.sub(r"^---\s*\n", "", body, count=1)
    body = re.sub(r"^#\s+/?" + re.escape(name) + r"\s*\n", "", body, count=1, flags=re.MULTILINE)
    body = apply_link_rewrite(body, lambda url: rewrite_skill_link(url, name))
    body = convert_mkdocs_admonitions(body)

    refs_dir = skill_dir / "references"
    folded, _ = fold_references(name, refs_dir)
    full_body = body.rstrip() + "\n\n" + folded if folded else body

    page = write_doc(
        page_path,
        header + full_body,
        title=f"/{name}",
        description=first_sentence(description),
        source_rel=src_rel,
    )
    return GeneratedPage(page.title, page.slug, page.source_rel)


def emit_skills_index(skills: list[GeneratedPage]) -> GeneratedPage:
    lines = [
        "Every skill in easy-cheese. Each one is independently invocable — type `/<name>` or describe what you want in plain English and Claude Code will route to the right one.",
        "",
        "| Skill | When to use |",
        "| --- | --- |",
    ]
    for skill in skills:
        meta, _ = parse_frontmatter((CONTENT_ROOT / _doc_path_for_slug(skill.slug)).read_text(encoding="utf-8"))
        summary = first_sentence(str(meta.get("description", ""))).replace("|", "\\|")
        lines.append(f"| [`{skill.title}`]({skill.slug.removeprefix('skills/')}/) | {summary} |")
    lines.append("")

    return write_doc(
        "skills/index.md",
        "\n".join(lines),
        title="Skills",
        description="Every skill in easy-cheese.",
        source_rel=None,
    )


H2_RE = re.compile(r"^## (.+?)\s*$")


def extract_h2_section(
    text: str,
    title: str,
    *,
    drop_header: bool = False,
    bump_headings: bool = False,
) -> str:
    # Stops at the next `## ` header.
    out: list[str] = []
    in_section = False
    for line in text.splitlines(keepends=True):
        m = H2_RE.match(line)
        if m:
            if in_section:
                break
            if m.group(1) == title:
                in_section = True
                if not drop_header:
                    out.append(line)
            continue
        if in_section:
            if bump_headings and re.match(r"^#{3,} ", line):
                line = line[1:]  # drop one '#' — promote h3+ by a level
            out.append(line)
    return "".join(out)


def emit_install_page() -> GeneratedPage | None:
    src = REPO_ROOT / "README.md"
    if not src.exists():
        return None
    readme = _read_text(src)

    sections = {
        "Install": extract_h2_section(readme, "Install", drop_header=True, bump_headings=True),
        "Installing MCP servers": extract_h2_section(readme, "Installing MCP servers"),
        "Optional tools": extract_h2_section(readme, "Optional tools"),
        "Installing CLI tools": extract_h2_section(readme, "Installing CLI tools"),
    }
    missing = [name for name, body in sections.items() if not body]
    if missing:
        raise RuntimeError(
            f"README.md is missing expected H2 section(s) {missing!r} — "
            "gen_docs.py:emit_install_page can't build docs/install.md without them"
        )

    body = (
        sections["Install"].rstrip() + "\n\n"
        + sections["Installing MCP servers"].rstrip() + "\n\n"
        + sections["Optional tools"].rstrip() + "\n\n"
        + sections["Installing CLI tools"].rstrip() + "\n"
    )
    body = apply_link_rewrite(body, rewrite_root_passthrough_link)
    body = convert_mkdocs_admonitions(body)

    return write_doc(
        "install.md",
        body,
        title="Install",
        description="Install easy-cheese skills, MCP servers, and CLI tools.",
        source_rel="README.md",
    )


def emit_root_passthrough(filename: str, dest_slug: str, title: str) -> GeneratedPage | None:
    src = REPO_ROOT / filename
    if not src.exists():
        return None
    text = _read_text(src)
    text = apply_link_rewrite(text, rewrite_root_passthrough_link)
    text = convert_mkdocs_admonitions(text)
    return write_doc(
        f"{dest_slug}.md",
        text,
        title=title,
        source_rel=filename,
    )


def _first_h1(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _sidebar_link(page: GeneratedPage) -> dict[str, str]:
    item = {"slug": page.slug}
    if page.title:
        item["label"] = page.title
    return item


def emit_sidebar(
    skills: list[GeneratedPage],
    project: list[GeneratedPage],
    install: GeneratedPage | None,
) -> None:
    skill_items: list[dict] = [{"label": "Skills index", "slug": "skills"}]
    for skill in skills:
        skill_items.append(_sidebar_link(skill))

    start_items = [{"label": "Home", "slug": ""}]
    if install:
        start_items.append({"label": "Install", "slug": "install"})
    sidebar = [
        {"label": "Start", "items": start_items},
        {"label": "Skills", "items": skill_items},
    ]
    if project:
        sidebar.append({"label": "Project", "items": [_sidebar_link(page) for page in project]})

    SIDEBAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    SIDEBAR_PATH.write_text(
        "// Generated by scripts/gen_docs.py; do not edit by hand.\n"
        "export const sidebar = "
        + json.dumps(sidebar, indent=2, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )


def clean_generated_docs() -> None:
    CONTENT_ROOT.mkdir(parents=True, exist_ok=True)
    for child in CONTENT_ROOT.iterdir():
        if child.name in AUTHORED_DOCS:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    if SIDEBAR_PATH.exists():
        SIDEBAR_PATH.unlink()
    _ref_title.cache_clear()

def main() -> None:
    clean_generated_docs()

    skills: list[GeneratedPage] = []
    for skill_dir in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
        page = emit_skill_page(skill_dir)
        if page is not None:
            skills.append(page)

    emit_skills_index(skills)
    install = emit_install_page()

    project: list[GeneratedPage] = []
    for filename, dest_slug, title in (
        ("README.md", "readme", "README"),
        ("CONTRIBUTING.md", "contributing", "Contributing"),
        ("SECURITY.md", "security", "Security policy"),
        ("CODE_OF_CONDUCT.md", "code-of-conduct", "Code of conduct"),
    ):
        if page := emit_root_passthrough(filename, dest_slug, title):
            project.append(page)

    emit_sidebar(skills, project, install)


if __name__ == "__main__":
    main()
