"""Check a drafted PR body against the mechanical rules of the body contract."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import fromargs

from easy_cheese.shared.git_utils import run_git
from easy_cheese.shared.publication import BoundedReadOverflow, read_bounded
from easy_cheese.skills.plate.diagram_trigger import FLOW_DIAGRAM, DiagramNeed, decide, parse_name_status

_MAX_BODY_BYTES = 200_000
MAX_LINES = 40
DEFAULT_HEADINGS = (
    "## Why",
    "## What changed",
    "## Non-obvious changes",
    "## How to verify",
    "## Risk",
)
_STACK_SHAPES = {"stacked_linear", "diamond_stack"}
_FLAT_SHAPE = "orthogonal_flat"
_SHAPES = _STACK_SHAPES | {"single", _FLAT_SHAPE}
_PLATED = re.compile(r"^Plated as (?P<shape>[a-z_]+): \S", re.MULTILINE)
_STACK_LINE = re.compile(r"^Stack: \d+ of \d+", re.MULTILINE)
_NO_DIAGRAM = re.compile(r"^Diagram: none, \S", re.MULTILINE)
_PR_REF = re.compile(r"(?<![\w:#])#\d+\b")
_STYLE_LINE = re.compile(r"^\s*(style|classDef|linkStyle|class)\b")
_THIS_PR = re.compile(r"\bthis PR\b", re.IGNORECASE)
_CHECKLIST = re.compile(r"^\s*[-*] \[[ xX]\]")
_FILLER = re.compile(
    r"\b(comprehensive|robust|seamless(ly)?|leverag(e|es|ed|ing)|significantly|dramatically)\b",
    re.IGNORECASE,
)


def _split_first_diagram(lines: list[str]) -> tuple[list[str], list[str]]:
    """Return (lines outside the first mermaid block, lines of that block)."""
    for start, line in enumerate(lines):
        if line.strip().startswith("```mermaid"):
            for end in range(start + 1, len(lines)):
                if lines[end].strip().startswith("```"):
                    return lines[:start] + lines[end + 1 :], lines[start : end + 1]
            return lines, []
    return lines, []


def _headings(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.startswith("## ")]


def _diagrams(lines: list[str]) -> list[list[str]]:
    """Return the content lines of every closed mermaid block."""
    blocks: list[list[str]] = []
    start: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if start is None:
            if stripped.startswith("```mermaid"):
                start = index
        elif stripped.startswith("```"):
            blocks.append(lines[start + 1 : index])
            start = None
    return blocks


def _header(block: list[str]) -> str:
    """Return the diagram type header: the first content line after any frontmatter or comment."""
    content = [line.strip() for line in block]
    if content and content[0] == "---":
        if "---" not in content[1:]:
            return ""
        content = content[content.index("---", 1) + 1 :]
    header = next((line for line in content if line and not line.startswith("%%")), "")
    return header.split(maxsplit=1)[0] if header else ""


def _draws(diagrams: list[list[str]], kind: str) -> bool:
    """Return whether any mermaid block's type header names `kind`."""
    # Mermaid reads `graph` as an alias of `flowchart`.
    kinds = (kind, "graph") if kind == "flowchart" else (kind,)
    return any(_header(block) in kinds for block in diagrams)


def _pr_refs(block: list[str]) -> set[str]:
    """Return the `#<n>` PR references in a mermaid block, outside style lines with hex colors."""
    return {hit.group(0) for line in block if not _STYLE_LINE.match(line) for hit in _PR_REF.finditer(line)}


def plated_shape(body: str) -> str | None:
    plated = _PLATED.search(body)
    return None if plated is None else plated.group("shape")


def check_body(
    body: str,
    *,
    stack_layer: bool = False,
    template: str | None = None,
    need: DiagramNeed | None = None,
) -> list[str]:
    """Return every violated mechanical rule of the body contract."""
    errors: list[str] = []
    lines = body.splitlines()
    outside, _ = _split_first_diagram(lines)
    diagrams = _diagrams(lines)

    counted = [line for line in outside if line.strip() and not _CHECKLIST.match(line)]
    if len(counted) > MAX_LINES:
        errors.append(f"body has {len(counted)} non-blank lines; the cap is {MAX_LINES}")

    required = tuple(_headings(template)) if template is not None else DEFAULT_HEADINGS
    present = set(_headings(body))
    errors.extend(f"missing heading: {heading}" for heading in required if heading not in present)

    shape = plated_shape(body)
    if shape not in _SHAPES:
        errors.append("missing topology line: Plated as <shape>: <reason>")
    elif stack_layer and shape not in _STACK_SHAPES:
        errors.append(f"stack layer needs a stacked shape, got Plated as {shape}")

    if stack_layer:
        if _STACK_LINE.search(body) is None:
            errors.append("stack layer needs a line: Stack: <n> of <total>")

    # A chart of PRs repeats the Stack line and shows no code structure.
    for block in diagrams:
        refs = _pr_refs(block)
        if len(refs) >= 2 or any(_THIS_PR.search(line) for line in block):
            named = f" ({', '.join(sorted(refs))})" if len(refs) >= 2 else ""
            errors.append(
                f"mermaid block draws PRs{named}, not code; the Stack line gives the order, so remove it"
            )

    if (
        need is not None
        and need.kind is not None
        and not _draws(diagrams, need.kind)
        and _NO_DIAGRAM.search(body) is None
    ):
        errors.append(
            f"diff needs a mermaid {need.kind} ({need.reason}); add one, or a line: Diagram: none, <reason>"
        )

    for number, line in enumerate(lines, start=1):
        hit = _FILLER.search(line)
        if hit is not None:
            errors.append(f"line {number}: filler word {hit.group(0)!r}")
    return errors


def _read(path: str) -> str:
    try:
        return read_bounded(Path(path), _MAX_BODY_BYTES).decode("utf-8")
    except (OSError, BoundedReadOverflow, UnicodeDecodeError) as error:
        raise fromargs.CliError(f"{path}: {error}", exit_code=2) from error


def _resolve_need(body: str, base: str) -> DiagramNeed | None:
    """Return the diagram need; run git only when the body does not already satisfy the rule."""
    if not base or base.startswith("-"):
        raise fromargs.CliError(f"--diagram-base must name a ref, got {base!r}", exit_code=2)
    shape = plated_shape(body)
    if shape == _FLAT_SHAPE:
        return decide([], shape=shape)
    if _NO_DIAGRAM.search(body) is not None or _draws(_diagrams(body.splitlines()), FLOW_DIAGRAM):
        return None
    return _diagram_need(base, shape)


def _diagram_need(base: str, shape: str | None) -> DiagramNeed:
    revisions = f"{base}...HEAD"
    result = run_git(["diff", "--name-status", "--find-renames", "-z", revisions])
    if result.returncode != 0:
        raise fromargs.CliError(f"git diff {revisions} failed: {result.stderr.strip()}", exit_code=2)
    try:
        changes = parse_name_status(result.stdout)
    except ValueError as error:
        raise fromargs.CliError(f"git diff {revisions}: {error}", exit_code=2) from error
    if not changes:
        # A PR always changes something, so an empty diff means the base is wrong.
        raise fromargs.CliError(f"git diff {revisions} lists no change; pass the PR base branch", exit_code=2)
    return decide(changes, shape=shape)


def check_cmd(
    body_file: str,
    *,
    stack_layer: bool = False,
    template_file: str | None = None,
    diagram_base: str | None = None,
) -> dict[str, object]:
    """Check a drafted PR body against the mechanical rules of the body contract.

    Parameters
    ----------
    body_file
        Path to the drafted PR body.
    stack_layer
        Require a stacked shape and the stack position line.
    template_file
        Path to the repository PR template; its `##` headings replace the defaults.
    diagram_base
        Base ref; require the diagram that the paths changed in `<base>...HEAD` call for.
    """
    template = _read(template_file) if template_file is not None else None
    body = _read(body_file)
    need = None if diagram_base is None else _resolve_need(body, diagram_base)
    if need is not None and need.kind is None:
        print(f"diagram not required: {need.reason}", file=sys.stderr)
    errors = check_body(body, stack_layer=stack_layer, template=template, need=need)
    if errors:
        raise fromargs.CliError("\n".join(errors), exit_code=2)
    return {"valid": True}


def build_app() -> fromargs.App:
    return fromargs.App(
        "check-pr-body",
        help="Check a drafted PR body against the mechanical body-contract rules.",
        help_formatter="plain",
        default_command=check_cmd,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
