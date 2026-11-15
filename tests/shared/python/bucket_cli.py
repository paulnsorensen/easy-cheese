"""Shared bucket-command app for CLI adversarial and repair tests."""

from __future__ import annotations

import fromargs


def bucket(*, files: int, modules: int = 1, title: str = "") -> list[object]:
    return [files, modules, title]


def bucket_app() -> fromargs.App:
    app = fromargs.App("bucket-test", help_formatter="plain")
    _ = app.command(bucket)
    return app