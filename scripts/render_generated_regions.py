"""Refresh generated schema/type-block regions in skill instruction surfaces.

Projects the mold-spec document contract and the cook writer-view payload
shapes (both declared on the attrs models in
``src/easy_cheese_schemas/contracts.py``) into compact, BAML-inspired type
blocks (Python type syntax), joins the phase registry with the schema catalog and the
registered contract models into ``skills/cheese/references/schema-intertwine.md``,
and projects each Python-backed skill's static ``COMMANDS`` manifest into
``skills/<skill>/references/commands.md``.

Running with no arguments refreshes every generated region in place. Pass
``--check`` to fail (exit 1) instead of writing, for CI drift detection.
"""

from __future__ import annotations

import argparse
import importlib
import re
import sys
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, ClassVar, Protocol, TypedDict, cast

REPO_ROOT = Path(__file__).resolve().parents[1]

for _extra in (REPO_ROOT / "vendor", REPO_ROOT / "src"):
    _path = str(_extra)
    if _path not in sys.path:
        sys.path.insert(0, _path)

import attrs  # noqa: E402

from easy_cheese.shared.bundle_commands import Command, command_map  # noqa: E402
from easy_cheese_schemas import contracts  # noqa: E402
from easy_cheese_schemas import COMPILED_TRANSITION_REGISTRY  # noqa: E402
from easy_cheese_schemas import REGISTERED_CONTRACT_SCHEMA_URIS  # noqa: E402


class _DocumentContract(Protocol):
    slug: ClassVar[str]
    sections: ClassVar[tuple[contracts.Section, ...]]
    cross_field_rules: ClassVar[tuple[contracts.CrossFieldRule, ...]]


class _ContractVersion(TypedDict):
    major: int
    minor: int
    schema_uri: str


class _PhaseOutput(TypedDict):
    destination: str
    payload_schema_uri: str


class _Phase(TypedDict):
    contract_version: _ContractVersion
    input_schema_uris: list[str]
    outputs: list[_PhaseOutput]
    source: str


CURDLE_PATH = REPO_ROOT / "skills" / "mold" / "references" / "curdle.md"
WRITER_VIEWS_PATH = REPO_ROOT / "skills" / "cook" / "references" / "writer-views.md"
INTERTWINE_PATH = REPO_ROOT / "skills" / "cheese" / "references" / "schema-intertwine.md"

# Same discovery rule as ``scripts/build_pyz.SKILLS``: a skill ships a bundle
# exactly when it declares a static command manifest. Kept local so the doc
# projection does not import the bundle builder; a test pins the two equal.
MANIFEST_ROOT = REPO_ROOT / "src" / "easy_cheese" / "skills"
SKILL_SLUGS = tuple(
    sorted(path.parent.name.replace("_", "-") for path in MANIFEST_ROOT.glob("*/commands.py"))
)

MOLD_SPEC_TAG = "mold-spec-schema"
WRITER_VIEWS_TAG = "cook-writer-views"

BEGIN_PREFIX = "<!-- BEGIN GENERATED: "
END_MARKER = "<!-- END GENERATED -->"


def _region_pattern(tag: str) -> re.Pattern[str]:
    return re.compile(
        re.escape(f"{BEGIN_PREFIX}{tag} -->") + r"\n.*?" + re.escape(END_MARKER),
        re.DOTALL,
    )


def replace_region(text: str, tag: str, body: str) -> str:
    """Replace the single ``tag`` region's content between its markers."""
    if not body.endswith("\n"):
        body += "\n"
    replacement = f"{BEGIN_PREFIX}{tag} -->\n{body}{END_MARKER}"
    new_text, count = _region_pattern(tag).subn(lambda _m: replacement, text)
    if count != 1:
        raise ValueError(f"expected exactly one {tag!r} generated region, found {count}")
    return new_text


def _identifier_names(type_repr: str) -> list[str]:
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", type_repr)


if TYPE_CHECKING:
    _Fields = tuple[attrs.Attribute[object], ...]


def _collect_reachable(
    roots: list[type], module: ModuleType
) -> tuple[dict[str, _Fields], dict[str, list[Enum]]]:
    """BFS from ``roots`` over attrs classes and Enums reachable via field types."""
    classes: dict[str, _Fields] = {}
    enums: dict[str, list[Enum]] = {}
    to_visit = list(roots)
    seen: set[str] = set()
    while to_visit:
        cls = to_visit.pop(0)
        if cls.__name__ in seen:
            continue
        seen.add(cls.__name__)
        if attrs.has(cls):
            fields = cast("tuple[attrs.Attribute[object], ...]", attrs.fields(cls))
            classes[cls.__name__] = fields
            for field in fields:
                type_repr = cast(str, field.type or "")
                for name in _identifier_names(type_repr):
                    candidate = getattr(module, name, None)
                    if not isinstance(candidate, type):
                        continue
                    if attrs.has(candidate) or issubclass(candidate, Enum):
                        if candidate.__name__ not in seen:
                            to_visit.append(candidate)
                    elif candidate.__module__ == module.__name__:
                        raise ValueError(
                            f"{cls.__name__}.{field.name} references "
                            + f"non-attrs, non-Enum class {candidate.__name__!r}"
                        )
        elif issubclass(cls, Enum):
            enums[cls.__name__] = list(cls)
    return classes, enums


def render_type_blocks(roots: list[type], module: ModuleType) -> str:
    """Render compact ``type``/``enum`` blocks for every class reachable from ``roots``."""
    classes, enums = _collect_reachable(roots, module)
    lines: list[str] = []
    for name in sorted(classes):
        lines.append(f"type {name} {{")
        for field in classes[name]:
            lines.append(f"  {field.name} {field.type}")
        lines.append("}")
        lines.append("")
    for name in sorted(enums):
        values = " | ".join(f'"{cast(str, member.value)}"' for member in enums[name])
        lines.append(f"enum {name} = {values}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def render_document_contract(cls: type[_DocumentContract]) -> str:
    """Render a document contract's sections and cross-field rules as a compact block."""
    lines = [f"document {cls.slug} {{"]
    for section in cls.sections:
        optional = "?" if section.optional else ""
        if section.table is not None:
            lines.append(f'  section "{section.name}"{optional} {{')
            lines.append(f"    columns: {list(section.table.columns)}")
            if section.table.per_row:
                lines.append(f"    per_row: {list(section.table.per_row)}")
            lines.append("  }")
        else:
            lines.append(f'  section "{section.name}"{optional}')
    lines.append("}")
    lines.append("")
    for rule in cls.cross_field_rules:
        lines.append(f'rule {rule.rule_id}: "{rule.description}"')
    return "\n".join(lines).rstrip("\n") + "\n"


def render_mold_spec_region() -> str:
    mold_spec = contracts.MoldSpecDocument
    return (
        render_document_contract(cast(type[_DocumentContract], mold_spec))
        + "\n"
        + render_type_blocks([mold_spec], contracts)
    )


def render_writer_views_region() -> str:
    roots = [contracts.AgentWriterView, *contracts.writer_payload_types().values()]
    return render_type_blocks(roots, contracts)


def _slug_from_uri(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def render_schema_intertwine() -> str:
    contract_slugs = {slug: cls.__name__ for slug, cls in contracts.registered_contracts()}
    phases = cast(list[_Phase], COMPILED_TRANSITION_REGISTRY.to_data())
    catalog_slugs = sorted(
        _slug_from_uri(uri) for uri in REGISTERED_CONTRACT_SCHEMA_URIS
    )

    lines = [
        "# Schema intertwine",
        "",
        (
            "Generated by `scripts/render_generated_regions.py`; do not hand-edit. Joins"
            " the phase registry (`_compiled_phase_registry`), the schema catalog"
            " (`_schema_catalog`), and the registered contract models"
            " (`contracts.py`) into one map per phase transition."
        ),
        "",
        "## Phase transitions",
        "",
        "| Source phase | Contract version | Input schemas | Destination | Payload schema | Payload contract |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for phase in phases:
        source = phase["source"]
        version = f'{phase["contract_version"]["major"]}.{phase["contract_version"]["minor"]}'
        inputs = ", ".join(sorted(_slug_from_uri(uri) for uri in phase["input_schema_uris"]))
        outputs = sorted(phase["outputs"], key=lambda o: (o["destination"], o["payload_schema_uri"]))
        for output in outputs:
            slug = _slug_from_uri(output["payload_schema_uri"])
            contract_cls = contract_slugs.get(slug, "—")
            lines.append(
                f'| {source} | {version} | {inputs} | {output["destination"]} | {slug} | {contract_cls} |'
            )
    lines.append("")
    lines.append("## Registered schema catalog")
    lines.append("")
    lines.append("| Slug | Contract model | Input to phase | Output of phase |")
    lines.append("| --- | --- | --- | --- |")
    for slug in catalog_slugs:
        input_phases = sorted(
            phase["source"]
            for phase in phases
            if slug in (_slug_from_uri(uri) for uri in phase["input_schema_uris"])
        )
        output_phases = sorted(
            phase["source"]
            for phase in phases
            if slug in (_slug_from_uri(o["payload_schema_uri"]) for o in phase["outputs"])
        )
        contract_cls = contract_slugs.get(slug, "—")
        lines.append(
            f'| {slug} | {contract_cls} | {", ".join(input_phases) or "—"} |'
            + f' {", ".join(output_phases) or "—"} |'
        )
    lines.append("")
    return "\n".join(lines)


def commands_doc_path(slug: str) -> Path:
    return REPO_ROOT / "skills" / slug / "references" / "commands.md"


def skill_commands(slug: str) -> tuple[Command, ...]:
    """Import one skill's static manifest without resolving its command targets."""
    package = slug.replace("-", "_")
    module = importlib.import_module(f"easy_cheese.skills.{package}.commands")
    return cast("tuple[Command, ...]", module.COMMANDS)


def render_skill_commands(slug: str) -> str:
    """Render one skill's canonical command inventory from its static manifest."""
    package = slug.replace("-", "_")
    lines = [
        f"# `/{slug}` bundle commands",
        "",
        (
            "Generated by `scripts/render_generated_regions.py` from the static `COMMANDS`"
            f" manifest in `src/easy_cheese/skills/{package}/commands.py`; do not hand-edit."
            f" Every command runs as `python3 skills/{slug}/scripts/{slug}.pyz <command>"
            " [args...]` and returns an integer exit status. Pass `--help` to a command for"
            " its own arguments and output format; worked examples stay in the skill prose."
        ),
        "",
        "| Command | Purpose |",
        "| --- | --- |",
    ]
    lines.extend(
        f"| `{command.name}` | {command.summary} |"
        for command in command_map(skill_commands(slug)).values()
    )
    lines.append("")
    return "\n".join(lines)


def _refreshed_region_file(path: Path, tag: str, body: str) -> str:
    text = path.read_text(encoding="utf-8")
    return replace_region(text, tag, body)


def refresh(check: bool) -> bool:
    """Refresh (or, in check mode, diff) every generated surface.

    Returns True when every surface is already up to date.
    """
    updates = {
        CURDLE_PATH: _refreshed_region_file(CURDLE_PATH, MOLD_SPEC_TAG, render_mold_spec_region()),
        WRITER_VIEWS_PATH: _refreshed_region_file(
            WRITER_VIEWS_PATH, WRITER_VIEWS_TAG, render_writer_views_region()
        ),
        INTERTWINE_PATH: render_schema_intertwine(),
        **{commands_doc_path(slug): render_skill_commands(slug) for slug in SKILL_SLUGS},
    }

    clean = True
    for path, new_text in updates.items():
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == new_text:
            continue
        clean = False
        if check:
            print(f"DRIFT: {path.relative_to(REPO_ROOT)} is stale", file=sys.stderr)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            _ = path.write_text(new_text, encoding="utf-8")
    return clean


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if any generated surface is stale, without writing",
    )
    args = parser.parse_args(argv)
    check = cast(bool, args.check)
    clean = refresh(check=check)
    if check and not clean:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
