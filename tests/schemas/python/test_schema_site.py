"""The deployed schemas.easy-cheese.dev tree is the catalogue, byte for byte.

`REGISTERED_CONTRACT_SCHEMA_URIS` is baked into published PyPI releases, so a
served document that drifts from `schema_bytes()` silently breaks every
consumer that dereferences the URI. These tests pin the deploy to the same
goldens the runtime is pinned to, and pin the served path of each URI to the
path the URI itself claims.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_schema_site  # noqa: E402

from easy_cheese_schemas import (  # noqa: E402
    REGISTERED_CONTRACT_SCHEMA_URIS,
    SCHEMA_ROOT,
    __version__,
)
from easy_cheese_schemas.schema_runtime import schema_bytes  # noqa: E402

GOLDENS = Path(__file__).with_name("goldens")


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_schema_site.build(tmp_path_factory.mktemp("schema-site") / "dist")


def _headers(site: Path) -> dict[str, dict[str, str]]:
    rules: dict[str, dict[str, str]] = {}
    current = ""
    for line in (site / "_headers").read_text(encoding="utf-8").splitlines():
        if line.startswith("/"):
            current = line
            rules[current] = {}
        else:
            name, _, value = line.strip().partition(": ")
            rules[current][name] = value
    return rules


def test_served_path_of_every_uri_is_the_path_the_uri_claims() -> None:
    for uri, slug in build_schema_site.schema_paths().items():
        assert uri == f"{SCHEMA_ROOT}/{slug}"


def test_site_holds_exactly_the_catalogue_plus_index_and_headers(site: Path) -> None:
    slugs = set(build_schema_site.schema_paths().values())

    assert {path.name for path in site.iterdir()} == slugs | {"_headers", "index.html"}


@pytest.mark.parametrize("schema_uri", sorted(REGISTERED_CONTRACT_SCHEMA_URIS))
def test_served_document_is_the_golden_schema(site: Path, schema_uri: str) -> None:
    slug = schema_uri.rsplit("/", 1)[-1]
    served = (site / slug).read_bytes()

    assert served == schema_bytes(schema_uri)
    assert served == (GOLDENS / f"{slug}.json").read_bytes()


def test_headers_type_every_schema_path_as_schema_json(site: Path) -> None:
    slugs = sorted(build_schema_site.schema_paths().values())

    assert _headers(site) == {
        f"/{slug}": {
            "Content-Type": "application/schema+json; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
        }
        for slug in slugs
    }


def test_index_page_lists_every_uri_and_the_package_version(site: Path) -> None:
    index = (site / "index.html").read_text(encoding="utf-8")

    assert f"<code>{__version__}</code>" in index
    for uri, slug in build_schema_site.schema_paths().items():
        assert f'<a href="/{slug}"><code>{uri}</code></a>' in index


def test_rebuilding_over_an_existing_deploy_is_byte_identical(site: Path) -> None:
    before = {path.name: path.read_bytes() for path in site.iterdir()}

    _ = build_schema_site.build(site)

    assert {path.name: path.read_bytes() for path in site.iterdir()} == before
