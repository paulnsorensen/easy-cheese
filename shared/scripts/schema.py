"""Reusable shape-validation helpers for cheese-factory and other skill scripts.

These helpers accumulate error strings rather than raising, so a single
validation pass can report every problem at once. The error format is
``where.key must be ...`` — the caller picks the ``where`` prefix.
"""

from __future__ import annotations

from typing import Any


def type_name(value: object) -> str:
    return type(value).__name__


def required_keys(obj: dict[str, Any], keys: tuple[str, ...], where: str) -> list[str]:
    return [f"{where}.{key} is required" for key in keys if key not in obj]


def non_empty_string(obj: dict[str, Any], key: str, where: str) -> list[str]:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        return [f"{where}.{key} must be a non-empty string"]
    return []


def string_list(value: object, where: str, *, non_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        return [f"{where} must be a list"]
    if non_empty and not value:
        return [f"{where} must be a non-empty list"]
    errors: list[str] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{where}[{index}] must be a non-empty string")
    return errors
