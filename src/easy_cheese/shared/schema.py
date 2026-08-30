"""Reusable shape-validation helpers for the fan-out engine and other skill scripts.

These helpers accumulate error strings rather than raising, so a single
validation pass can report every problem at once. The error format is
``where.key must be ...`` — the caller picks the ``where`` prefix.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast


def type_name(value: object) -> str:
    return type(value).__name__


def required_keys(obj: dict[str, object], keys: tuple[str, ...], where: str) -> list[str]:
    return [f"{where}.{key} is required" for key in keys if key not in obj]


def non_empty_string(obj: dict[str, object], key: str, where: str) -> list[str]:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        return [f"{where}.{key} must be a non-empty string"]
    return []


def string_list(value: object, where: str, *, non_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        return [f"{where} must be a list"]
    if non_empty and not value:
        return [f"{where} must be a non-empty list"]
    items = cast("list[object]", value)
    errors: list[str] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{where}[{index}] must be a non-empty string")
    return errors


def disjoint_errors(
    curds: list[object],
    *,
    id_key: str,
    message: Callable[[str, object, object], str],
    strict: bool = False,
) -> list[str]:
    """Cross-curd file collision, generalized over curd.py's run-manifest
    contract (strict=True: flags non-dict curds, missing/empty files, and
    non-string file entries) and curd_block.py's decomposition-artifact
    contract (strict=False: caller has already dict-filtered; silently skips
    non-list files / non-string entries)."""
    errors: list[str] = []
    file_to_id: dict[str, object] = {}
    for curd in curds:
        if strict and not isinstance(curd, dict):
            continue
        curd_dict = cast("dict[str, object]", curd)
        cid = curd_dict.get(id_key, "?")
        files = curd_dict.get("files")
        if strict:
            if not isinstance(files, list) or not files:
                errors.append(f"curd {cid}: missing or empty 'files'")
                continue
        elif not isinstance(files, list):
            continue
        file_items = cast("list[object]", files)
        for f in file_items:
            if not isinstance(f, str):
                if strict:
                    errors.append(f"curd {cid}: non-string file entry: {f!r}")
                continue
            if f in file_to_id:
                errors.append(message(f, file_to_id[f], cid))
            else:
                file_to_id[f] = cid
    return errors
