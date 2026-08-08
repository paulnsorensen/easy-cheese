from __future__ import annotations

import json
from importlib import resources

_FIXTURE_NAMES = ("contract-cases.json", "normalization-cases.json")


def list_conformance_fixtures() -> tuple[str, ...]:
    return _FIXTURE_NAMES


def _fixture_resource(name: str):
    if type(name) is not str or name not in _FIXTURE_NAMES:
        raise ValueError(f"unknown conformance fixture {name!r}")
    return resources.files("easy_cheese_schemas").joinpath(
        "conformance", "v1", name
    )


def read_conformance_fixture(name: str) -> bytes:
    return _fixture_resource(name).read_bytes()


def load_conformance_fixture(name: str) -> dict[str, object]:
    try:
        value = json.loads(read_conformance_fixture(name))
    except json.JSONDecodeError as error:
        raise ValueError(f"conformance fixture {name!r} is not valid JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"conformance fixture {name!r} must contain an object")
    return value


__all__ = [
    "list_conformance_fixtures",
    "load_conformance_fixture",
    "read_conformance_fixture",
]
