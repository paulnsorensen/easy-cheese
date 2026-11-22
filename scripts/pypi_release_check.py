"""Decide whether a package version is new to PyPI.

Read the version from the pyproject.toml at $PYPROJECT. Look up $PROJECT on
PyPI. Write `version` and `should_publish` to $GITHUB_OUTPUT.
"""

from __future__ import annotations

import json
import os
import tomllib
import urllib.error
import urllib.request
from http.client import HTTPResponse
from pathlib import Path
from typing import cast


def released_versions(project: str) -> set[str]:
    url = f"https://pypi.org/pypi/{project}/json"
    try:
        with cast(HTTPResponse, urllib.request.urlopen(url, timeout=30)) as resp:
            payload = cast(dict[str, dict[str, object]], json.load(resp))
            return set(payload.get("releases", {}))
    except urllib.error.HTTPError as exc:
        # 404 means the project was never published: this is its first release.
        if exc.code == 404:
            return set()
        raise


def main() -> None:
    project = os.environ["PROJECT"]
    pyproject = Path(os.environ["PYPROJECT"])
    metadata = cast(dict[str, object], tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"])
    version = str(metadata["version"])
    publish = version not in released_versions(project)
    print(f"{pyproject} declares {project} {version}; already on PyPI: {not publish}")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
        _ = fh.write(f"version={version}\nshould_publish={str(publish).lower()}\n")


if __name__ == "__main__":
    main()
