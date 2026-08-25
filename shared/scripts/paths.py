"""Transitional delegator to the package-authoritative corpus path producer."""

from __future__ import annotations

import importlib.util
from importlib import import_module
from pathlib import Path
from types import ModuleType


def _load_canonical() -> ModuleType:
    try:
        return import_module("easy_cheese.shared.paths")
    except ModuleNotFoundError:
        # Loose repository tools may expose shared/scripts without adding src/;
        # load the same package source directly rather than recreating its rules.
        source = Path(__file__).resolve().parents[2] / "src" / "easy_cheese" / "shared" / "paths.py"
        spec = importlib.util.spec_from_file_location("_easy_cheese_canonical_paths", source)
        if spec is None or spec.loader is None:
            raise ModuleNotFoundError("canonical paths producer is unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


_canonical = _load_canonical()


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
