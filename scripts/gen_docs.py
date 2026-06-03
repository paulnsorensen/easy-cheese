"""Generate MkDocs pages from skill sources at build time.

Invoked by mkdocs-gen-files. For each skills/<name>/SKILL.md:
  - Emit docs/skills/<name>.md mirroring the SKILL.md body, with title from
    frontmatter and an "edit this page" link back to the source.
  - Mirror references/* (Markdown + asset files like JSON schemas) under
    docs/skills/<name>/references/*. Only Markdown refs land in the nav.
  - Rewrite internal Markdown links to match the flattened docs layout.

Also emits:
  - docs/skills/index.md — table listing every skill + its one-line description.
  - docs/SUMMARY.md — literate-nav for the whole site.
  - docs/install.md — sliced out of README.md's Install / Installing MCP servers
    / Installing CLI tools sections so install instructions stay single-sourced.
  - docs/shared/*.md — cross-skill contracts (e.g. handoff-gate.md) mirrored
    from the repo's top-level shared/ directory so skills can link to them.
  - docs/contributing.md, docs/security.md, docs/code-of-conduct.md — slurped
    from the repo root so they stay single-sourced.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import mkdocs_gen_files
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
SHARED_DIR = REPO_ROOT / "shared"
REPO_URL = "https://github.com/paulnsorensen/easy-cheese"
LICENSE_URL = f"{REPO_URL}/blob/main/LICENSE"

LINK_RE = re.compile(r"(?<!\!)\[([^\]]+)\]\(([^)\s]+)(\s+\"[^\"]*\")?\)")
NESTED_IMAGE_LINK_RE = re.compile(r"(\[!\[[^\]]*\]\([^)]+\)\]\()([^)\s]+)(\))")

ROOT_DOC_MAP = {
    "README.md": "readme.md",
    "CONTRIBUTING.md": "contributing.md",
    "SECURITY.md": "security.md",
    "CODE_OF_CONDUCT.md": "code-of-conduct.md",
}


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
    return meta, body


def first_sentence(desc: str) -> str:
    desc = desc.replace("\n", " ").strip()
    match = re.search(r"^(.*?[.!?])(\s|$)", desc)
    return (match.group(1) if match else desc)[:240]


def _split_anchor(path: str) -> tuple[str, str]:
    if "#" in path:
        body, anchor = path.split("#", 1)
        return body, "#" + anchor
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


def rewrite_skill_link(url: str, skill_name: str) -> str:
    if _is_external(url):
        return url
    path, anchor = _split_anchor(url)

    if path.startswith("references/"):
        return f"{skill_name}/{path}{anchor}"

    m = re.match(r"^\.\./([^/]+)/SKILL\.md$", path)
    if m:
        return f"{m.group(1)}.md{anchor}"

    m = re.match(r"^\.\./([^/]+)/references/(.+)$", path)
    if m:
        return f"{m.group(1)}/references/{m.group(2)}{anchor}"

    m = re.match(r"^\.\./\.\./([A-Z_]+\.md)$", path)
    if m and m.group(1) in ROOT_DOC_MAP:
        return f"../{ROOT_DOC_MAP[m.group(1)]}{anchor}"

    # Cross-cutting contracts in top-level shared/ (e.g. ../../shared/handoff-gate.md).
    # The source path climbs through repo_root; after flattening SKILL.md to
    # docs/skills/<name>.md it only needs one `..` to reach docs/shared/.
    m = re.match(r"^\.\./\.\./shared/(.+\.md)$", path)
    if m:
        return f"../shared/{m.group(1)}{anchor}"

    if path == "../../LICENSE":
        return LICENSE_URL

    return url


def rewrite_ref_link(url: str, skill_name: str) -> str:
    if _is_external(url):
        return url
    path, anchor = _split_anchor(url)

    if path == "../SKILL.md":
        return f"../../{skill_name}.md{anchor}"

    m = re.match(r"^\.\./\.\./([^/]+)/SKILL\.md$", path)
    if m:
        return f"../../{m.group(1)}.md{anchor}"

    m = re.match(r"^\.\./\.\./([^/]+)/references/(.+)$", path)
    if m:
        return f"../../{m.group(1)}/references/{m.group(2)}{anchor}"

    m = re.match(r"^\.\./\.\./\.\./([A-Z_]+\.md)$", path)
    if m and m.group(1) in ROOT_DOC_MAP:
        return f"../../../{ROOT_DOC_MAP[m.group(1)]}{anchor}"

    if path == "../../../LICENSE":
        return LICENSE_URL

    return url


def rewrite_root_passthrough_link(url: str) -> str:
    if _is_external(url):
        return url
    path, anchor = _split_anchor(url)
    stripped = path[2:] if path.startswith("./") else path

    if stripped in ROOT_DOC_MAP:
        return f"./{ROOT_DOC_MAP[stripped]}{anchor}"
    if stripped == "LICENSE":
        return LICENSE_URL
    return url


def apply_link_rewrite(text: str, rewriter) -> str:
    def image_repl(match: re.Match) -> str:
        prefix, url, suffix = match.group(1), match.group(2), match.group(3)
        return f"{prefix}{rewriter(url)}{suffix}"

    def repl(match: re.Match) -> str:
        label, url, title = match.group(1), match.group(2), match.group(3) or ""
        return f"[{label}]({rewriter(url)}{title})"

    return LINK_RE.sub(repl, NESTED_IMAGE_LINK_RE.sub(image_repl, text))


def emit_skill_page(skill_dir: Path) -> dict | None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None

    meta, body = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    name = meta.get("name") or skill_dir.name
    description = meta.get("description", "").strip()
    license_id = meta.get("license", "MIT")

    src_rel = skill_md.relative_to(REPO_ROOT).as_posix()
    page_path = f"skills/{name}.md"

    front = "---\n" + yaml.safe_dump(
        {"title": f"/{name}", "description": first_sentence(description)},
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ) + "---\n\n"

    header = (
        f"# `/{name}`\n\n"
        f"!!! info \"Skill metadata\"\n"
        f"    - **License:** {license_id}\n"
        f"    - **Source:** [`{src_rel}`]({REPO_URL}/blob/main/{src_rel})\n\n"
        f"**When to invoke:** {description}\n\n"
        f"---\n\n"
    )

    body = re.sub(r"^---\s*\n", "", body, count=1)
    body = re.sub(r"^#\s+/?" + re.escape(name) + r"\s*\n", "", body, count=1, flags=re.MULTILINE)
    body = apply_link_rewrite(body, lambda url: rewrite_skill_link(url, name))

    with mkdocs_gen_files.open(page_path, "w") as fh:
        fh.write(front + header + body.lstrip())
    mkdocs_gen_files.set_edit_path(page_path, src_rel)

    refs_dir = skill_dir / "references"
    refs: list[tuple[str, str]] = []
    if refs_dir.is_dir():
        for ref in sorted(p for p in refs_dir.iterdir() if p.is_file()):
            ref_rel = ref.relative_to(REPO_ROOT).as_posix()
            out = f"skills/{name}/references/{ref.name}"
            if ref.suffix.lower() == ".md":
                content = apply_link_rewrite(
                    ref.read_text(encoding="utf-8"),
                    lambda url: rewrite_ref_link(url, name),
                )
                with mkdocs_gen_files.open(out, "w") as fh:
                    fh.write(content)
                mkdocs_gen_files.set_edit_path(out, ref_rel)
                refs.append((ref.stem, out))
            else:
                # Non-Markdown reference (e.g. JSON schema) — copy as a static
                # asset. set_edit_path() only applies to rendered pages.
                with mkdocs_gen_files.open(out, "wb") as fh:
                    fh.write(ref.read_bytes())

    return {"name": name, "description": description, "page": page_path, "refs": refs}


def emit_skills_index(skills: list[dict]) -> None:
    lines = [
        "# Skills",
        "",
        "Every skill in easy-cheese. Each one is independently invocable — type `/<name>` or describe what you want in plain English and Claude Code will route to the right one.",
        "",
        "| Skill | When to use |",
        "| --- | --- |",
    ]
    for s in skills:
        summary = first_sentence(s["description"]).replace("|", "\\|")
        lines.append(f"| [`/{s['name']}`]({s['name']}.md) | {summary} |")
    lines.append("")

    with mkdocs_gen_files.open("skills/index.md", "w") as fh:
        fh.write("\n".join(lines))


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


def emit_install_page() -> bool:
    src = REPO_ROOT / "README.md"
    if not src.exists():
        return False
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

    front = "---\n" + yaml.safe_dump(
        {"title": "Install", "description": "Install easy-cheese skills, MCP servers, and CLI tools."},
        sort_keys=False, allow_unicode=True, default_flow_style=False,
    ) + "---\n\n# Install\n\n"

    with mkdocs_gen_files.open("install.md", "w") as fh:
        fh.write(front + body.lstrip())
    mkdocs_gen_files.set_edit_path("install.md", "README.md")
    return True


def emit_root_passthrough(filename: str, dest: str, title: str) -> bool:
    src = REPO_ROOT / filename
    if not src.exists():
        return False
    text = _read_text(src)
    text = re.sub(r"^#\s+.*\n", "", text, count=1)
    text = apply_link_rewrite(text, rewrite_root_passthrough_link)
    front = "---\n" + yaml.safe_dump(
        {"title": title},
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ) + f"---\n\n# {title}\n\n"
    with mkdocs_gen_files.open(dest, "w") as fh:
        fh.write(front + text.lstrip())
    mkdocs_gen_files.set_edit_path(dest, filename)
    return True


def emit_shared_pages() -> list[tuple[str, str]]:
    # mkdocs --strict requires shared files to exist in the docs tree and the nav.
    if not SHARED_DIR.is_dir():
        return []

    entries: list[tuple[str, str]] = []
    for src in sorted(p for p in SHARED_DIR.iterdir() if p.is_file() and p.suffix == ".md"):
        src_rel = src.relative_to(REPO_ROOT).as_posix()
        out = f"shared/{src.name}"
        text = src.read_text(encoding="utf-8")
        with mkdocs_gen_files.open(out, "w") as fh:
            fh.write(text)
        mkdocs_gen_files.set_edit_path(out, src_rel)

        title = _first_h1(text) or src.stem.replace("-", " ").capitalize()
        entries.append((title, out))
    return entries


def _first_h1(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def emit_nav(
    skills: list[dict],
    shared: list[tuple[str, str]],
    extras: list[tuple[str, str]],
) -> None:
    lines = [
        "* [Home](index.md)",
        "* [Install](install.md)",
        "* Skills",
        "    * [Overview](skills/index.md)",
    ]
    for s in skills:
        lines.append(f"    * [/{s['name']}](skills/{s['name']}.md)")
        for ref_name, ref_path in s["refs"]:
            lines.append(f"        * [{ref_name}]({ref_path})")
    if shared:
        lines.append("* Shared contracts")
        for title, path in shared:
            lines.append(f"    * [{title}]({path})")
    if extras:
        lines.append("* Project")
        for title, path in extras:
            lines.append(f"    * [{title}]({path})")
    with mkdocs_gen_files.open("SUMMARY.md", "w") as fh:
        fh.write("\n".join(lines) + "\n")


def main() -> None:
    skills: list[dict] = []
    for skill_dir in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
        page = emit_skill_page(skill_dir)
        if page is not None:
            skills.append(page)

    emit_skills_index(skills)
    emit_install_page()
    shared = emit_shared_pages()

    extras: list[tuple[str, str]] = []
    if emit_root_passthrough("README.md", "readme.md", "README"):
        extras.append(("README", "readme.md"))
    if emit_root_passthrough("CONTRIBUTING.md", "contributing.md", "Contributing"):
        extras.append(("Contributing", "contributing.md"))
    if emit_root_passthrough("SECURITY.md", "security.md", "Security policy"):
        extras.append(("Security", "security.md"))
    if emit_root_passthrough("CODE_OF_CONDUCT.md", "code-of-conduct.md", "Code of conduct"):
        extras.append(("Code of conduct", "code-of-conduct.md"))

    emit_nav(skills, shared, extras)


main()
