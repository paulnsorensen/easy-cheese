"""Collect review instruction sources without assigning them authority.

The helper is deliberately filesystem-local: repository instruction files are
collected only beneath the supplied repository root, and host-provided external
sources are read only when they are named by the request.  The returned records
are evidence candidates; callers must not treat this module as a precedence
resolver.

Public API::

    collect_instructions(
        repo_root, scope="diff", changed_paths=[], external_sources=[]
    )
    main([request_json_path])

The command accepts one JSON request path or JSON on stdin.  ``--text`` renders
an intentionally readable form; JSON is the default.
"""

from __future__ import annotations

# Cyclopts exposes its application result as Any at the invocation boundary.
# pyright: reportAny=false, reportUnusedCallResult=false

from cyclopts import App
import hashlib
import json
import os
import stat
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Literal, NoReturn, cast

from easy_cheese.shared.manifest_io import ManifestLoadError, read_mapping_arg_or_stdin
from easy_cheese.shared import cli
from easy_cheese_schemas.validate import require_exact_keys

RULE_FILENAMES: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md", "CLAUDE.local.md")

# The set contains only unambiguously internal trees.  Ordinary names such as
# ``build``, ``env``, ``target``, and ``coverage`` can be first-party source
# directories and are intentionally traversed.
EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".bzr",
        ".git-worktrees",
        ".worktrees",
        "vendor",
        "node_modules",
        "bower_components",
        ".venv",
        ".tox",
        ".nox",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".cache",
        ".pnpm-store",
        "site-packages",
        ".next",
        ".nuxt",
    }
)

EXCLUDED_DIRECTORY_PATHS = frozenset(
    {
        (".claude", "worktrees"),
        (".git", "worktrees"),
        (".yarn", "cache"),
        (".yarn", "unplugged"),
    }
)


def _is_excluded_directory(relative_directory: str) -> bool:
    parts = PurePosixPath(relative_directory).parts
    if any(part in EXCLUDED_DIRECTORY_NAMES for part in parts):
        return True
    return any(
        len(parts) >= len(pattern) and parts[-len(pattern) :] == pattern
        for pattern in EXCLUDED_DIRECTORY_PATHS
    )


Scope = Literal["diff", "overall"]


class InstructionCollectionError(ValueError):
    """A request or source boundary that cannot be collected safely."""


def _fail(message: str) -> NoReturn:
    raise InstructionCollectionError(message)


def _validate_scope(value: object) -> Scope:
    if value not in {"diff", "overall"}:
        _fail("scope must be 'diff' or 'overall'")
    return cast(Scope, value)


def _validate_relative_path(value: object, *, field: str) -> str:
    """Return a normalized repository-relative POSIX path.

    Backslashes and drive prefixes are rejected even on POSIX so a request has
    the same boundary semantics when it is produced on another host.  The
    helper never resolves ``..``: rejecting it is what prevents an absent path
    from making ancestor discovery escape the selected repository.
    """
    if not isinstance(value, str) or not value:
        _fail(f"{field} must be a non-empty relative path")
    path_value = value
    if "\x00" in path_value:
        _fail(f"{field} contains NUL")
    if "\\" in path_value:
        _fail(f"{field} must use '/' separators")
    if path_value.startswith("/") or (len(path_value) >= 2 and path_value[1] == ":"):
        _fail(f"{field} must be relative")
    path = PurePosixPath(path_value)

    if path.is_absolute():
        _fail(f"{field} must be relative")
    if any(part in {"", ".."} for part in path.parts):
        _fail(f"{field} must not contain '..'")
    normalized = path.as_posix()
    if not normalized:
        _fail(f"{field} must be a non-empty relative path")
    return normalized


def _validate_changed_paths(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail("changed_paths must be a list of relative paths")
    paths = [
        _validate_relative_path(item, field=f"changed_paths[{index}]")
        for index, item in enumerate(value)
    ]
    return sorted(set(paths))


def _validate_external_sources(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail("external_sources must be a list")

    sources: list[dict[str, object]] = []
    for index, raw_item in enumerate(value):
        if not isinstance(raw_item, Mapping):
            _fail(f"external_sources[{index}] must be an object")
        item = cast(Mapping[str, object], raw_item)
        path = item.get("path")
        if not isinstance(path, str) or not path:
            _fail(f"external_sources[{index}].path must be a non-empty path")
        applies_to = item.get("applies_to")
        if isinstance(applies_to, (str, bytes)) or not isinstance(applies_to, Sequence):
            _fail(f"external_sources[{index}].applies_to must be a list")
        if not applies_to:
            _fail(f"external_sources[{index}].applies_to must be non-empty")
        normalized_scopes = sorted(
            {
                _validate_relative_path(
                    scope,
                    field=f"external_sources[{index}].applies_to[{scope_index}]",
                )
                for scope_index, scope in enumerate(applies_to)
            }
        )
        record: dict[str, object] = {"path": path, "applies_to": normalized_scopes}
        provenance = item.get("provenance")
        if provenance is not None:
            if not isinstance(provenance, str) or not provenance:
                _fail(
                    f"external_sources[{index}].provenance must be a non-empty string"
                )
            record["provenance"] = provenance
        sources.append(record)
    return sources


def _resolve_root(repo_root: str | os.PathLike[str]) -> Path:
    if isinstance(repo_root, str) and not repo_root:
        _fail("repo_root must be a non-empty path")
    try:
        root = Path(repo_root).resolve(strict=True)
        info = root.stat()
    except FileNotFoundError as exc:
        raise InstructionCollectionError(
            f"repository root does not exist: {repo_root!s}"
        ) from exc
    except OSError as exc:
        raise InstructionCollectionError(
            f"cannot inspect repository root {repo_root!s}: {exc}"
        ) from exc
    if not stat.S_ISDIR(info.st_mode):
        _fail(f"repository root is not a directory: {repo_root!s}")
    return root


def _is_within(path: Path, root: Path) -> bool:
    try:
        _ = path.relative_to(root)
    except ValueError:
        return False
    return True


def _resolve_existing(path: Path, *, label: str, root: Path | None = None) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise InstructionCollectionError(f"{label} does not exist: {path}") from exc
    except RuntimeError as exc:
        raise InstructionCollectionError(
            f"{label} has a symlink cycle: {path}"
        ) from exc
    except OSError as exc:
        raise InstructionCollectionError(
            f"cannot inspect {label} {path}: {exc}"
        ) from exc
    if root is not None and not _is_within(resolved, root):
        _fail(f"{label} symlink escapes repository root: {path}")
    return resolved


def _validate_changed_path(root: Path, relative: str) -> None:
    """Check every existing component while permitting a deleted leaf."""
    current = root
    parts = PurePosixPath(relative).parts
    for index, part in enumerate(parts):
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            # A deleted leaf, or a deleted ancestor, is valid.  There is no
            # deeper directory to inspect after the first missing component.
            return
        except OSError as exc:
            raise InstructionCollectionError(
                f"cannot inspect changed path {relative!r}: {exc}"
            ) from exc
        is_last = index == len(parts) - 1
        if stat.S_ISLNK(info.st_mode):
            resolved = _resolve_existing(
                current, label=f"changed path {relative!r}", root=root
            )
            if not is_last and not resolved.is_dir():
                _fail(f"changed path {relative!r} traverses a non-directory")
            current = resolved
        elif not is_last and not stat.S_ISDIR(info.st_mode):
            _fail(f"changed path {relative!r} traverses a non-directory")


def _changed_ancestor_dirs(root: Path, relative: str) -> list[tuple[str, Path]]:
    """Return lexical directory scopes and their safe filesystem paths."""
    parts = PurePosixPath(relative).parts
    target = root.joinpath(*parts)
    try:
        target_info = target.lstat()
    except FileNotFoundError:
        directory_parts = parts[:-1]
    except OSError as exc:
        raise InstructionCollectionError(
            f"cannot inspect changed path {relative!r}: {exc}"
        ) from exc
    else:
        if stat.S_ISLNK(target_info.st_mode):
            resolved = _resolve_existing(
                target, label=f"changed path {relative!r}", root=root
            )
            directory_parts = parts if resolved.is_dir() else parts[:-1]
        elif stat.S_ISDIR(target_info.st_mode):
            directory_parts = parts
        else:
            directory_parts = parts[:-1]

    result: list[tuple[str, Path]] = [(".", root)]
    current = root
    lexical_parts: list[str] = []
    for part in directory_parts:
        next_relative = "/".join([*lexical_parts, part])
        if _is_excluded_directory(next_relative):
            break
        lexical_parts.append(part)
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            break
        except OSError as exc:
            raise InstructionCollectionError(
                f"cannot inspect changed path {relative!r}: {exc}"
            ) from exc
        if stat.S_ISLNK(info.st_mode):
            resolved = _resolve_existing(
                current, label=f"changed path {relative!r}", root=root
            )
            if not resolved.is_dir():
                _fail(f"changed path {relative!r} traverses a non-directory")
            current = resolved
        elif not stat.S_ISDIR(info.st_mode):
            _fail(f"changed path {relative!r} traverses a non-directory")
        result.append(("/".join(lexical_parts), current))
    return result


def _read_source(path: Path, *, label: str, root: Path | None) -> tuple[str, str]:
    """Read one regular UTF-8 source, refusing unsafe or partial reads."""
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise InstructionCollectionError(
            f"source disappeared while reading {label}: {path}"
        ) from exc
    except OSError as exc:
        raise InstructionCollectionError(
            f"cannot inspect source {label} {path}: {exc}"
        ) from exc

    if stat.S_ISLNK(info.st_mode):
        resolved = _resolve_existing(path, label=f"source {label}", root=root)
        try:
            info = resolved.stat()
        except OSError as exc:
            raise InstructionCollectionError(
                f"cannot inspect source {label} {path}: {exc}"
            ) from exc
        read_path = resolved
    else:
        read_path = path

    if not stat.S_ISREG(info.st_mode):
        _fail(f"source {label} is not a regular file: {path}")
    if not info.st_mode & 0o444:
        _fail(f"source {label} is unreadable: {path}")
    try:
        data = read_path.read_bytes()
    except OSError as exc:
        raise InstructionCollectionError(
            f"cannot read source {label} {path}: {exc}"
        ) from exc
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InstructionCollectionError(
            f"source {label} is not valid UTF-8: {path}"
        ) from exc
    return text, f"sha256:{hashlib.sha256(data).hexdigest()}"


def _line_numbered(text: str) -> str:
    if not text:
        return ""
    return "".join(
        f"{line_number}: {line}"
        for line_number, line in enumerate(text.splitlines(keepends=True), start=1)
    )


def _record(
    *,
    kind: str,
    path: str,
    scope: list[str],
    scope_kind: str,
    text: str,
    digest: str,
    provenance: str,
) -> dict[str, object]:
    return {
        "id": f"{kind}:{path}",
        "path": path,
        "kind": kind,
        "scope": scope,
        "scope_kind": scope_kind,
        "authority": "candidate",
        "provenance": provenance,
        "content_hash": digest,
        "content": text,
    }


def _under_scope(path: str, directory: str) -> bool:
    return directory == "." or path == directory or path.startswith(f"{directory}/")


def _collect_diff_sources(
    root: Path, changed_paths: list[str], scope: Scope
) -> list[dict[str, object]]:
    if not changed_paths:
        return []
    candidates: dict[str, tuple[str, Path]] = {}
    for changed_path in changed_paths:
        for relative_dir, actual_dir in _changed_ancestor_dirs(root, changed_path):
            # The lexical path is the identity.  A symlinked directory can
            # point at the same bytes as another scope and must not collapse it.
            for filename in RULE_FILENAMES:
                relative_source = (
                    filename if relative_dir == "." else f"{relative_dir}/{filename}"
                )
                _ = candidates.setdefault(
                    relative_source, (relative_dir, actual_dir / filename)
                )

    records: list[dict[str, object]] = []
    for relative_source, (relative_dir, source_path) in sorted(candidates.items()):
        try:
            _ = source_path.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise InstructionCollectionError(
                f"cannot inspect repository instruction source {relative_source}: {exc}"
            ) from exc
        text, digest = _read_source(
            source_path, label=f"repository instruction {relative_source}", root=root
        )
        applies_to = [
            path for path in changed_paths if _under_scope(path, relative_dir)
        ]
        records.append(
            _record(
                kind="repository",
                path=relative_source,
                scope=applies_to,
                scope_kind=scope,
                text=text,
                digest=digest,
                provenance="repository",
            )
        )
    return records


def _collect_overall_sources(root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []

    def walk(directory: Path, relative_directory: str) -> None:
        try:
            with os.scandir(directory) as entries:
                ordered = sorted(entries, key=lambda entry: entry.name)
                for entry in ordered:
                    relative_path = (
                        entry.name
                        if relative_directory == "."
                        else f"{relative_directory}/{entry.name}"
                    )
                    try:
                        info = entry.stat(follow_symlinks=False)
                    except OSError as exc:
                        raise InstructionCollectionError(
                            f"cannot inspect repository path {relative_path}: {exc}"
                        ) from exc
                    if stat.S_ISLNK(info.st_mode):
                        if entry.name not in RULE_FILENAMES:
                            # Do not follow arbitrary links.  Candidate links
                            # are handed to _read_source so escapes/cycles are
                            # loud rather than silently omitted.
                            continue
                        text, digest = _read_source(
                            Path(entry.path),
                            label=f"repository instruction {relative_path}",
                            root=root,
                        )
                        records.append(
                            _record(
                                kind="repository",
                                path=relative_path,
                                scope=[relative_directory],
                                scope_kind="overall",
                                text=text,
                                digest=digest,
                                provenance="repository",
                            )
                        )
                    elif entry.name in RULE_FILENAMES:
                        text, digest = _read_source(
                            Path(entry.path),
                            label=f"repository instruction {relative_path}",
                            root=root,
                        )
                        records.append(
                            _record(
                                kind="repository",
                                path=relative_path,
                                scope=[relative_directory],
                                scope_kind="overall",
                                text=text,
                                digest=digest,
                                provenance="repository",
                            )
                        )
                    elif stat.S_ISDIR(info.st_mode):
                        if _is_excluded_directory(relative_path):
                            continue
                        walk(Path(entry.path), relative_path)
        except OSError as exc:
            raise InstructionCollectionError(
                f"cannot scan repository instruction sources under {relative_directory}: {exc}"
            ) from exc

    walk(root, ".")
    return records


def _external_record(
    root: Path, source: Mapping[str, object], index: int
) -> dict[str, object]:
    raw_path = cast(str, source["path"])
    path = Path(raw_path)
    if not path.is_absolute():
        path = root / path
    resolved = _resolve_existing(path, label=f"external source[{index}]", root=None)
    text, digest = _read_source(
        path,
        label=f"external source[{index}]",
        root=None,
    )
    # ``resolved`` is the stable identity, while _read_source retains the
    # lexical path for diagnostics and follows a safe symlink exactly once.
    normalized_path = resolved.as_posix()
    applies_to = cast(list[str], source["applies_to"])
    record = _record(
        kind="external",
        path=normalized_path,
        scope=list(applies_to),
        scope_kind="explicit",
        text=text,
        digest=digest,
        provenance=cast(str, source.get("provenance", "explicit")),
    )
    return record


def collect_instructions(
    repo_root: str | os.PathLike[str],
    *,
    scope: Scope = "diff",
    changed_paths: Sequence[str] | None = None,
    external_sources: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Collect deterministic repository and explicitly named external sources.

    ``scope='diff'`` reads rule files at the repository root and at each
    existing ancestor directory of every changed path.  ``scope='overall'``
    recursively reads repository rule files while pruning the exclusion set.
    Missing optional rule files are ordinary absence; every other source error
    raises :class:`InstructionCollectionError`.
    """
    selected_scope = _validate_scope(scope)
    root = _resolve_root(repo_root)
    normalized_paths = _validate_changed_paths(changed_paths)
    normalized_external = _validate_external_sources(external_sources)
    for relative_path in normalized_paths:
        _validate_changed_path(root, relative_path)

    if selected_scope == "overall":
        records = _collect_overall_sources(root)
    else:
        records = _collect_diff_sources(root, normalized_paths, selected_scope)
    records.extend(
        _external_record(root, source, index)
        for index, source in enumerate(normalized_external)
    )
    records.sort(
        key=lambda item: (
            0 if item["kind"] == "repository" else 1,
            cast(str, item["path"]),
            json.dumps(item["scope"], ensure_ascii=False, separators=(",", ":")),
            cast(str, item["provenance"]),
        )
    )
    return {
        "policy_version": "age-review-instructions.v1",
        "repo_root": root.as_posix(),
        "scope": selected_scope,
        "changed_paths": normalized_paths,
        "authority": "candidate",
        "sources": records,
    }


def render_text(result: Mapping[str, object]) -> str:
    """Render a collection result without hiding source content or errors."""
    sources = result.get("sources")
    if not isinstance(sources, list):
        raise InstructionCollectionError("result.sources must be a list")
    lines = [
        f"policy_version: {result.get('policy_version', '')}",
        f"repo_root: {result.get('repo_root', '')}",
        f"scope: {result.get('scope', '')}",
        "authority: candidate",
    ]
    for raw_source in cast(list[object], sources):
        if not isinstance(raw_source, Mapping):
            raise InstructionCollectionError("result.sources contains a non-object")
        source = cast(Mapping[str, object], raw_source)
        lines.extend(
            [
                "",
                f"[{source.get('id', '')}]",
                f"path: {source.get('path', '')}",
                f"kind: {source.get('kind', '')}",
                f"provenance: {source['provenance']}",
                f"scope: {json.dumps(source.get('scope', []), ensure_ascii=False)}",
                f"content_hash: {source.get('content_hash', '')}",
                "authority: candidate",
                _line_numbered(cast(str, source["content"])),
            ]
        )
    return "\n".join(lines) + "\n"


def _request(payload: Mapping[str, object]) -> dict[str, object]:
    required = {"repo_root", "scope", "changed_paths", "external_sources"}
    require_exact_keys(payload, required, "request", error=InstructionCollectionError)
    return collect_instructions(
        cast(str | os.PathLike[str], payload["repo_root"]),
        scope=cast(Scope, payload["scope"]),
        changed_paths=cast(Sequence[str], payload["changed_paths"]),
        external_sources=cast(
            Sequence[Mapping[str, object]], payload["external_sources"]
        ),
    )


def _command(request: str | None = None, *, text: bool = False) -> int:
    """Run the JSON-in/JSON-out helper, or its readable ``--text`` mode."""
    request_args = [request] if request is not None else []
    try:
        payload = read_mapping_arg_or_stdin(request_args, "usage: review-instructions [--text] [<request.json>]")
    except (ManifestLoadError, OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    try:
        result = _request(payload)
        if text:
            _ = sys.stdout.write(render_text(result))
        else:
            json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
            _ = sys.stdout.write("\n")
    except (InstructionCollectionError, OSError, TypeError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


app = App(name="review-instructions")
_ = app.default(_command)


def main(argv: list[str] | None = None) -> int:
    return cli.run(app, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
