"""A bundle must be able to carry whole package trees, not just flat modules.

The published easy_cheese_schemas package and its vendored attrs/cattrs deps are
real packages: nested dirs plus .dist-info metadata that attrs reads at import
time. Flattening them would break both import and `attrs.__version__`, so these
tests pin the archive layout, the compression settings CI byte-compares against,
and -- the one that actually matters -- that a bare interpreter with no
site-packages can import the whole stack straight out of the zip.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402


@pytest.fixture(scope="module")
def ultracook_pyz(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("tree-staging")
    return build_pyz.build_bundle("ultracook", out / "ultracook.pyz")


def _run_isolated(pyz: Path, code: str) -> subprocess.CompletedProcess[str]:
    """Run `code` on an interpreter with site-packages disabled (-S) and the
    environment ignored (-I), with only the bundle on sys.path. Anything that
    imports here provably came out of the zip."""
    return subprocess.run(
        [
            sys.executable,
            "-S",
            "-I",
            "-c",
            f"import sys; sys.path.insert(0, {str(pyz)!r})\n{code}",
        ],
        capture_output=True,
        text=True,
    )


def test_package_trees_keep_their_nesting(ultracook_pyz: Path) -> None:
    """Staged dirs must land as nested archive members with posix separators;
    a flattened basename would collide across packages and break imports."""
    names = set(zipfile.ZipFile(ultracook_pyz).namelist())
    assert "easy_cheese_schemas/__init__.py" in names
    assert "easy_cheese_schemas/compat.py" in names
    assert "attr/_make.py" in names
    assert "cattrs/converters.py" in names
    assert "typing_extensions.py" in names
    assert "attrs-26.1.0.dist-info/METADATA" in names
    # Nothing was flattened into the archive root on the way in.
    assert "compat.py" not in names
    assert "_make.py" not in names
    assert not any(name.startswith("__pycache__") or "/__pycache__/" in name for name in names)


def test_schemas_stack_imports_and_round_trips_from_inside_the_zip(ultracook_pyz: Path) -> None:
    """The spec's key verification: the bundle runs on a bare interpreter with no
    site-packages. Every import must resolve inside the .pyz, and a real load()
    round-trip must work -- not just the import statement."""
    result = _run_isolated(
        ultracook_pyz,
        "import attrs, cattrs, easy_cheese_schemas as ecs\n"
        "for mod in (attrs, cattrs, ecs):\n"
        "    assert mod.__file__.startswith(sys.path[0]), (mod.__name__, mod.__file__)\n"
        "loaded = ecs.load(\n"
        "    {\n"
        "        'schema_version': 1,\n"
        "        'branch': 'claude/pypi',\n"
        "        'title': 'Ship it',\n"
        "        'base': 'main',\n"
        "        'commits': ['abc1234'],\n"
        "    },\n"
        "    ecs.PrGroup,\n"
        "    strict=True,\n"
        ")\n"
        "assert loaded.problems == (), loaded.problems\n"
        "assert loaded.provenance is ecs.Provenance.CURRENT\n"
        "assert loaded.value.branch == 'claude/pypi'\n"
        "assert loaded.value.commits == ['abc1234']\n"
        "print('ok')\n",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "ok"


def test_attrs_version_resolves_from_bundled_dist_info(ultracook_pyz: Path) -> None:
    """attrs.__version__ reads its own dist-info metadata, so dropping the
    .dist-info dirs from the staged tree would break a public attrs API."""
    result = _run_isolated(ultracook_pyz, "import attrs; print(attrs.__version__)")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "26.1.0"


def test_tree_staging_stays_byte_deterministic(tmp_path: Path) -> None:
    """CI rebuilds every committed bundle and byte-compares it, so walking a
    nested tree must not leak filesystem ordering or mtimes into the archive."""
    first = build_pyz.build_bundle("ultracook", tmp_path / "a" / "ultracook.pyz")
    second = build_pyz.build_bundle("ultracook", tmp_path / "b" / "ultracook.pyz")
    assert first.read_bytes() == second.read_bytes()


def test_every_member_carries_the_fixed_timestamp(ultracook_pyz: Path) -> None:
    """Source mtimes would make the byte-compare flap; every member is pinned."""
    with zipfile.ZipFile(ultracook_pyz) as archive:
        stamps = {info.date_time for info in archive.infolist()}
    assert stamps == {build_pyz.ZIP_TIMESTAMP}


def test_members_are_deflated(ultracook_pyz: Path) -> None:
    """ZIP_DEFLATED is what keeps the vendored deps from tripling bundle size."""
    with zipfile.ZipFile(ultracook_pyz) as archive:
        kinds = {info.compress_type for info in archive.infolist()}
    assert kinds == {zipfile.ZIP_DEFLATED}
