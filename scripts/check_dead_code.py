"""Owner-qualified semantic classifier over Vulture's scanner API.

Wraps Vulture 2.16's scan and accepts findings only in narrow, owner-qualified
categories; everything else is reported and fails the gate. Whitelist-free --
no checked-in symbol list (see .hallouminate/wiki/specs/vulture-dead-code-annotations.md).
"""
from __future__ import annotations

import ast
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from vulture import Vulture
from vulture.config import InputError, make_config
from vulture.core import ExitCode

REPO_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_PREFIX = "src/easy_cheese_schemas/"

# base names are matched via each file's own import map (see _import_map),
# resolved to "module.Name" and compared against these fully-qualified pairs:
_QUALIFIED_CALLBACK_OVERRIDES = {
    ("urllib.request.HTTPRedirectHandler", "redirect_request"),
    ("html.parser.HTMLParser", "handle_starttag"),
    ("html.parser.HTMLParser", "handle_data"),
    ("html.parser.HTMLParser", "handle_endtag"),
    ("urllib.request.HTTPSHandler", "https_open"),
}


@dataclass(frozen=True, slots=True)
class _Finding:
    path: Path
    first_line: int
    name: str
    typ: str
    report: str


def _findings(items) -> tuple[_Finding, ...]:
    findings = []
    for i in items:
        path = Path(i.filename)
        if path.is_absolute():
            try:
                path = path.relative_to(REPO_ROOT)
            except ValueError:
                pass
        findings.append(_Finding(path, i.first_lineno, i.name, i.typ, i.get_report()))
    return tuple(findings)


def _import_map(module: ast.Module) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in module.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                out[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return out


def _resolve_base(base: ast.expr, imports: Mapping[str, str]) -> str | None:
    if isinstance(base, ast.Name):
        return imports.get(base.id, base.id)
    if isinstance(base, ast.Attribute):
        return ast.unparse(base)
    return None


def _is_enum_base(resolved: str | None) -> bool:
    return resolved is not None and (resolved == "Enum" or resolved.endswith(".Enum"))


def _is_attrs_decorated(class_def: ast.ClassDef) -> bool:
    for dec in class_def.decorator_list:
        head = dec.func if isinstance(dec, ast.Call) else dec
        name = head.attr if isinstance(head, ast.Attribute) else getattr(head, "id", None)
        if name in {"define", "frozen", "attrs"}:
            return True
    return False


def _accepted_reason(finding: _Finding, module: ast.Module, imports: dict[str, str]) -> str | None:
    schema_owned = finding.path.as_posix().startswith(_SCHEMA_PREFIX)
    for node in ast.walk(module):
        if not isinstance(node, ast.ClassDef):
            continue
        if finding.typ == "method":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == finding.name and item.lineno == finding.first_line:
                    for base in node.bases:
                        resolved = _resolve_base(base, imports)
                        if resolved and any(
                            resolved.endswith(qualified) and method == finding.name
                            for qualified, method in _QUALIFIED_CALLBACK_OVERRIDES
                        ):
                            return "exact callback override"
        if finding.typ == "variable" and schema_owned:
            for item in node.body:
                target_line = None
                if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name) and item.targets[0].id == finding.name:
                    target_line = item.lineno
                elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and item.target.id == finding.name:
                    target_line = item.lineno
                if target_line != finding.first_line:
                    continue
                is_enum = any(_is_enum_base(_resolve_base(b, imports)) for b in node.bases)
                if is_enum or _is_attrs_decorated(node):
                    return "enum member or attrs field owned by easy_cheese_schemas"
    if finding.typ == "function":
        for node in ast.walk(module):
            if not (isinstance(node, ast.FunctionDef) and node.name == finding.name):
                continue
            start_line = node.decorator_list[0].lineno if node.decorator_list else node.lineno
            if start_line != finding.first_line:
                continue
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr == "fixture":
                    if any(kw.arg == "autouse" and isinstance(kw.value, ast.Constant) and kw.value.value is True for kw in dec.keywords):
                        return "autouse pytest fixture"
    return None


def main(argv: Sequence[str] | None = None) -> int:
    try:
        config = make_config(list(argv) if argv is not None else sys.argv[1:])
    except InputError as err:
        print(err, file=sys.stderr)
        return ExitCode.InvalidCmdlineArguments.value

    vult = Vulture(
        verbose=config["verbose"],
        ignore_names=config["ignore_names"],
        ignore_decorators=config["ignore_decorators"],
    )
    vult.scavenge(config["paths"], exclude=config["exclude"])
    if vult.exit_code == ExitCode.InvalidInput:
        return ExitCode.InvalidInput.value

    findings = _findings(
        vult.get_unused_code(
            min_confidence=config["min_confidence"], sort_by_size=config["sort_by_size"]
        )
    )
    unclassified = []
    module_cache: dict[Path, tuple[ast.Module | None, dict[str, str]]] = {}
    for finding in findings:
        if finding.path not in module_cache:
            source_path = finding.path if finding.path.is_absolute() else REPO_ROOT / finding.path
            try:
                tree = ast.parse(source_path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                module_cache[finding.path] = (None, {})
            else:
                module_cache[finding.path] = (tree, _import_map(tree))
        module, imports = module_cache[finding.path]
        if module is not None and _accepted_reason(finding, module, imports):
            continue
        unclassified.append(finding)

    for finding in unclassified:
        print(finding.report)
    return ExitCode.DeadCode.value if unclassified else ExitCode.NoDeadCode.value


if __name__ == "__main__":
    raise SystemExit(main())
