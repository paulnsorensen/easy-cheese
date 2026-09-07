"""The shared strict validators (#612).

One home for the rules that used to be re-typed privately per module: the
bool-excluding integer check, the exact key-set check that names missing and
unknown keys separately, and the repository-relative path rule. Every
rejection is a ``ValueError`` naming the field.
"""

from __future__ import annotations

import pytest

from easy_cheese_schemas.validate import (
    is_int,
    is_relative_path,
    require_exact_keys,
    require_int,
    require_list,
    require_mapping,
    require_relative_path,
    require_str,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, True), (-3, True), (True, False), (False, False), (1.0, False), ("1", False), (None, False)],
)
def test_is_int_excludes_bool_and_non_integers(value: object, expected: bool) -> None:
    assert is_int(value) is expected


def test_require_int_returns_the_integer() -> None:
    assert require_int(3, "attempt") == 3


def test_require_int_names_the_field() -> None:
    with pytest.raises(ValueError, match="^attempt must be an integer$"):
        _ = require_int(True, "attempt")


def test_require_str_returns_the_value_unstripped() -> None:
    assert require_str("  ok ", "slug") == "  ok "


@pytest.mark.parametrize("value", ["", "   ", "\n", 7, None, b"x"])
def test_require_str_rejects_blank_and_non_strings(value: object) -> None:
    with pytest.raises(ValueError, match="^slug must be a non-empty string$"):
        _ = require_str(value, "slug")


def test_require_list_returns_the_same_object() -> None:
    items: list[object] = [1]
    assert require_list(items, "tool_errors") is items


@pytest.mark.parametrize("value", [(1,), "abc", {"a": 1}, None])
def test_require_list_rejects_non_lists(value: object) -> None:
    with pytest.raises(ValueError, match="^tool_errors must be a list$"):
        _ = require_list(value, "tool_errors")


def test_require_mapping_returns_the_same_object() -> None:
    entry: dict[str, object] = {"role": "reviewer"}
    assert require_mapping(entry, "each delegations entry") is entry


@pytest.mark.parametrize("value", [["role"], "role", None])
def test_require_mapping_rejects_non_mappings(value: object) -> None:
    with pytest.raises(ValueError, match="^each delegations entry must be a mapping$"):
        _ = require_mapping(value, "each delegations entry")


def test_require_exact_keys_accepts_the_exact_set_in_any_order() -> None:
    require_exact_keys({"b": 1, "a": 2}, ("a", "b"), "request")


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"a": 1}, "request keys mismatch: missing ['b']"),
        ({"a": 1, "b": 2, "z": 0, "c": 0}, "request keys mismatch: unknown ['c', 'z']"),
        ({"c": 0}, "request keys mismatch: missing ['a', 'b'], unknown ['c']"),
        ({}, "request keys mismatch: missing ['a', 'b']"),
    ],
)
def test_require_exact_keys_names_missing_then_unknown_sorted(
    values: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError) as caught:
        require_exact_keys(values, ("b", "a"), "request")
    assert str(caught.value) == message
    assert type(caught.value) is ValueError


def test_require_exact_keys_raises_the_callers_error_type() -> None:
    class Rejected(ValueError):
        pass

    with pytest.raises(Rejected, match=r"^curd_ids keys mismatch: missing \['api'\]$"):
        require_exact_keys({}, ("api",), "curd_ids", error=Rejected)


@pytest.mark.parametrize("path", ["src/a.py", ".", "tests/", "./a", "a/b:c", "a b/c.d"])
def test_require_relative_path_returns_accepted_paths_unchanged(path: str) -> None:
    assert is_relative_path(path) is True
    assert require_relative_path(path, "cwd") == path


@pytest.mark.parametrize(
    "path",
    [
        "/etc/passwd",
        "..",
        "../x",
        "a/../b",
        "a/..",
        "C:/x",
        "c:x",
        "a\\b",
        "\\\\server\\share",
        "a\x00b",
    ],
)
def test_require_relative_path_rejects_escapes(path: str) -> None:
    assert is_relative_path(path) is False
    with pytest.raises(ValueError, match="^cwd must be a repository-relative path$"):
        _ = require_relative_path(path, "cwd")


@pytest.mark.parametrize("value", ["", "  ", 3, None])
def test_require_relative_path_requires_a_non_empty_string_first(value: object) -> None:
    assert is_relative_path(value) is False
    with pytest.raises(ValueError, match="^cwd must be a non-empty string$"):
        _ = require_relative_path(value, "cwd")
