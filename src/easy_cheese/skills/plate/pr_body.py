"""Check a drafted PR body against the mechanical rules of the body contract."""

from __future__ import annotations

import re
from pathlib import Path

import fromargs

from easy_cheese.shared.publication import BoundedReadOverflow, read_bounded

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
_SHAPES = _STACK_SHAPES | {"single", "orthogonal_flat"}
_PLATED = re.compile(r"^Plated as (?P<shape>[a-z_]+): \S", re.MULTILINE)
_STACK_LINE = re.compile(r"^Stack: \d+ of \d+", re.MULTILINE)
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


def check_body(
    body: str, *, stack_layer: bool = False, template: str | None = None
) -> list[str]:
    """Return every violated mechanical rule of the body contract."""
    errors: list[str] = []
    lines = body.splitlines()
    outside, diagram = _split_first_diagram(lines)

    counted = [line for line in outside if line.strip() and not _CHECKLIST.match(line)]
    if len(counted) > MAX_LINES:
        errors.append(f"body has {len(counted)} non-blank lines; the cap is {MAX_LINES}")

    required = tuple(_headings(template)) if template is not None else DEFAULT_HEADINGS
    present = set(_headings(body))
    errors.extend(f"missing heading: {heading}" for heading in required if heading not in present)

    plated = _PLATED.search(body)
    if plated is None or plated.group("shape") not in _SHAPES:
        errors.append("missing topology line: Plated as <shape>: <reason>")
    elif stack_layer and plated.group("shape") not in _STACK_SHAPES:
        errors.append(f"stack layer needs a stacked shape, got Plated as {plated.group('shape')}")

    if stack_layer:
        if _STACK_LINE.search(body) is None:
            errors.append("stack layer needs a line: Stack: <n> of <total>")
        if not any(line.strip().startswith("flowchart") for line in diagram):
            errors.append("stack layer needs a mermaid flowchart of the stack order")

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


def check_cmd(
    body_file: str, *, stack_layer: bool = False, template_file: str | None = None
) -> dict[str, object]:
    """Check a drafted PR body against the mechanical rules of the body contract.

    Parameters
    ----------
    body_file
        Path to the drafted PR body.
    stack_layer
        Require the stack position line and the stack-order flowchart.
    template_file
        Path to the repository PR template; its `##` headings replace the defaults.
    """
    template = _read(template_file) if template_file is not None else None
    errors = check_body(_read(body_file), stack_layer=stack_layer, template=template)
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
