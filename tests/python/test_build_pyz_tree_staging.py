"""A bundle must be able to carry whole package trees, not just flat modules.

The published easy_cheese_schemas package and its attrs/cattrs dependencies are
real packages: nested dirs plus .dist-info metadata that attrs reads at import
time. Shiv stores those wheels under site-packages/ and extracts them before
dispatch, so these tests pin the packaged layout, deterministic metadata, and
the importable runtime members.
"""

from __future__ import annotations

import re
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402

pytestmark = pytest.mark.skipif(  # noqa: V107
    importlib.util.find_spec("build") is None
    or importlib.util.find_spec("pip") is None
    or (shutil.which("shiv") is None and importlib.util.find_spec("shiv") is None),
    reason="bundle integration requires requirements-build.txt",
)


@pytest.fixture(scope="module")
def ultracook_pyz(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("tree-staging")
    return build_pyz.build_bundle("cook", out / "cook.pyz")

@pytest.fixture(scope="module")
def press_pyz(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("tree-staging-press")
    return build_pyz.build_bundle("press", out / "press.pyz")


def _bundle_members(pyz: Path) -> set[str]:
    with zipfile.ZipFile(pyz) as archive:
        return {
            name.removeprefix("site-packages/")
            for name in archive.namelist()
            if not name.startswith("site-packages/bin/")
        }


def test_press_tree_staging_keeps_schema_and_helpers_nested(press_pyz: Path) -> None:
    names = _bundle_members(press_pyz)
    assert "easy_cheese/shared/fanout/press_route.py" in names
    assert "easy_cheese/shared/fanout/press_route_cli.py" in names
    assert "easy_cheese/skills/press/commands.py" in names
    assert "easy_cheese_schemas/gates.py" in names
    assert "easy_cheese_schemas/compat.py" in names
    assert "attrs-26.1.0.dist-info/METADATA" in names
    assert "cattrs/converters.py" in names
    assert "gates.py" not in names


def test_press_cli_runs_from_isolated_bundle(press_pyz: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-S", "-I", str(press_pyz), "nope"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    usage = result.stdout + result.stderr
    assert "press-route" in usage


def test_press_bundle_is_byte_deterministic(tmp_path: Path) -> None:
    first = build_pyz.build_bundle("press", tmp_path / "a" / "press.pyz")
    second = build_pyz.build_bundle("press", tmp_path / "b" / "press.pyz")
    assert first.read_bytes() == second.read_bytes()


def _run_isolated(pyz: Path, code: str) -> subprocess.CompletedProcess[str]:
    """Extract Shiv's site-packages payload and run only against those members."""
    with tempfile.TemporaryDirectory(prefix="easy-cheese-site-packages-") as root:
        package_root = Path(root)
        with zipfile.ZipFile(pyz) as archive:
            for name in archive.namelist():
                if not name.startswith("site-packages/"):
                    continue
                relative = Path(name.removeprefix("site-packages/"))
                target = package_root / relative
                if name.endswith("/"):
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(name))
        return subprocess.run(
            [
                sys.executable,
                "-S",
                "-I",
                "-c",
                f"import sys; sys.path.insert(0, {str(package_root)!r})\n{code}",
            ],
            capture_output=True,
            text=True,
        )


def test_package_trees_keep_their_nesting(ultracook_pyz: Path) -> None:
    """Staged dirs must land as nested archive members with posix separators;
    a flattened basename would collide across packages and break imports."""
    names = _bundle_members(ultracook_pyz)
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


@pytest.fixture(scope="module")
def wheypoint_pyz(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("tree-staging-wheypoint")
    return build_pyz.build_bundle("wheypoint", out / "wheypoint.pyz")


def test_the_wheypoint_bundle_carries_its_whole_runtime(wheypoint_pyz: Path) -> None:
    """The app and shared distributions retain their package namespaces."""
    names = _bundle_members(wheypoint_pyz)
    for module in (
        "canonical.py",
        "commit.py",
        "legacy.py",
        "lint.py",
        "projection.py",
        "records.py",
        "resolve.py",
        "storage.py",
        "wheypoint.py",
    ):
        assert f"easy_cheese/skills/wheypoint/{module}" in names, module
    # The shared library it reuses rather than reimplements.
    assert "easy_cheese/shared/paths.py" in names
    # Schemas and locked deps ride along, nested, exactly as for ultracook.
    assert "easy_cheese_schemas/wheypoint.py" in names
    assert "attr/_make.py" in names
    assert "cattrs/converters.py" in names
    assert "attrs-26.1.0.dist-info/METADATA" in names
    assert not any(name.startswith("__pycache__") or "/__pycache__/" in name for name in names)


def test_the_wheypoint_runtime_imports_from_inside_the_zip(wheypoint_pyz: Path) -> None:
    """Acceptance: the bundle runs under -S with no ambient site packages. Every
    module must resolve out of the archive, not the developer's checkout."""
    result = _run_isolated(
        wheypoint_pyz,
        "from easy_cheese.skills.wheypoint import "
        "commit, resolve, lint, storage, projection, records, canonical\n"
        "import easy_cheese_schemas as ecs\n"
        "for mod in (commit, resolve, lint, storage, ecs):\n"
        "    assert mod.__file__.startswith(sys.path[0]), (mod.__name__, mod.__file__)\n"
        "assert commit.GENESIS_PARENT == 'genesis'\n"
        "assert ecs.WheypointRecord is not None\n"
        "print('ok')\n",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "ok"


def test_the_wheypoint_bundle_is_deterministic(tmp_path) -> None:
    """Byte-equality against the committed artifact is CI's job (check_bundles.py
    compares canonical member content, because ZIP metadata differs). What is verifiable
    anywhere is that two builds of one source tree agree."""
    first = build_pyz.build_bundle("wheypoint", tmp_path / "a.pyz")
    second = build_pyz.build_bundle("wheypoint", tmp_path / "b.pyz")
    assert first.read_bytes() == second.read_bytes()


def test_tree_staging_stays_byte_deterministic(tmp_path: Path) -> None:
    """CI rebuilds every committed bundle and byte-compares it, so walking a
    nested tree must not leak filesystem ordering or mtimes into the archive."""
    first = build_pyz.build_bundle("cook", tmp_path / "a" / "cook.pyz")
    second = build_pyz.build_bundle("cook", tmp_path / "b" / "cook.pyz")
    assert first.read_bytes() == second.read_bytes()


def test_internal_wheel_normalization_ignores_compressor_and_member_order(
    tmp_path: Path,
) -> None:
    members = {
        "demo.py": b"VALUE = 1\n",
        "demo-1.0.0.dist-info/METADATA": (
            b"Metadata-Version: 2.1\nName: demo\nVersion: 1.0.0\n"
        ),
        "demo-1.0.0.dist-info/WHEEL": (
            b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
        ),
        "demo-1.0.0.dist-info/RECORD": b"",
    }
    wheels = []
    for name, compression, entries in (
        ("a", zipfile.ZIP_DEFLATED, members.items()),
        ("b", zipfile.ZIP_STORED, reversed(members.items())),
    ):
        wheel = tmp_path / name / "demo-1.0.0-py3-none-any.whl"
        wheel.parent.mkdir()
        with zipfile.ZipFile(wheel, "w", compression=compression) as archive:
            for member, content in entries:
                archive.writestr(member, content)
        wheels.append(build_pyz._normalize_internal_wheel(wheel))

    assert wheels[0].read_bytes() == wheels[1].read_bytes()
    with zipfile.ZipFile(wheels[0]) as archive:
        assert archive.read("demo.py") == members["demo.py"]
        assert {item.compress_type for item in archive.infolist()} == {
            zipfile.ZIP_STORED
        }


def test_builder_does_not_expose_a_custom_wheel_writer() -> None:
    assert not hasattr(build_pyz, "_wheel")
    assert not hasattr(build_pyz, "WHEEL_TIMESTAMP")


def test_members_are_stored(ultracook_pyz: Path) -> None:
    """Shiv's --uncompressed mode stores all members for deterministic startup."""
    with zipfile.ZipFile(ultracook_pyz) as archive:
        kinds = {info.compress_type for info in archive.infolist()}
    assert kinds == {zipfile.ZIP_STORED}



def test_shiv_command_uses_a_local_hash_locked_wheelhouse(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    wheelhouse = tmp_path / "wheelhouse"
    command = build_pyz._shiv_command(
        "cook", requirements, tmp_path / "cook.pyz", wheelhouse
    )
    for flag in (
        "--reproducible",
        "--uncompressed",
        "--no-index",
        "--only-binary=:all:",
        "--require-hashes",
    ):
        assert flag in command
    assert command[command.index("--python") + 1] == "/usr/bin/env python3"
    assert command[command.index("--find-links") + 1] == str(wheelhouse)
    assert command[command.index("--requirement") + 1] == str(requirements)


def test_build_cli_preserves_resolver_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    failure = subprocess.CalledProcessError(
        1,
        ["pip", "install"],
        output="resolver stdout",
        stderr="resolver stderr",
    )

    def fail(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise failure

    monkeypatch.setattr(build_pyz, "build_bundles", fail)

    assert build_pyz.main(["build_pyz.py", "--out-dir", str(tmp_path), "cook"]) == 1
    diagnostics = capsys.readouterr().err
    assert "cook" in diagnostics
    assert "subprocess stdout" in diagnostics
    assert "subprocess stderr" in diagnostics


def test_runtime_lock_contains_only_external_pure_wheels() -> None:
    lines = (REPO_ROOT / "requirements" / "runtime.txt").read_text().splitlines()
    locked = [line for line in lines if line and not line.startswith("#")]
    assert all(re.fullmatch(r"[^=]+==[^ ]+ --hash=sha256:[0-9a-f]{64}", line) for line in locked)
    assert not any(line.startswith("easy-cheese-") for line in locked)


def _test_wheel(
    path: Path, *, pure: bool = True, native_suffix: str | None = None
) -> Path:
    dist_info = "demo-1.0.0.dist-info"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"{dist_info}/METADATA",
            "Metadata-Version: 2.1\nName: demo\nVersion: 1.0.0\n",
        )
        archive.writestr(
            f"{dist_info}/WHEEL",
            f"Wheel-Version: 1.0\nRoot-Is-Purelib: {'true' if pure else 'false'}\n"
            "Tag: py3-none-any\n",
        )
        archive.writestr(f"demo{native_suffix}" if native_suffix else "demo.py", b"")
    return path


@pytest.mark.parametrize("suffix", [".so", ".pyd", ".dylib"])
def test_validate_pure_wheel_rejects_native_suffixes(
    tmp_path: Path, suffix: str
) -> None:
    native = _test_wheel(
        tmp_path / "demo-1.0.0-py3-none-any.whl",
        native_suffix=suffix,
    )
    with pytest.raises(ValueError, match="native members"):
        build_pyz.validate_pure_wheel(native)


def test_validate_pure_wheel_rejects_false_root_is_purelib(tmp_path: Path) -> None:
    wheel = _test_wheel(tmp_path / "demo-1.0.0-py3-none-any.whl", pure=False)
    with pytest.raises(ValueError, match="Root-Is-Purelib: true"):
        build_pyz.validate_pure_wheel(wheel)


def test_validate_pure_wheel_rejects_non_universal_tag(tmp_path: Path) -> None:
    renamed = _test_wheel(
        tmp_path / "demo-1.0.0-cp314-cp314-macosx_14_0_arm64.whl"
    )
    with pytest.raises(ValueError, match="not py3-none-any"):
        build_pyz.validate_pure_wheel(renamed)


def test_shiv_bundle_has_no_loose_source_or_vendor_roots(ultracook_pyz: Path) -> None:
    with zipfile.ZipFile(ultracook_pyz) as archive:
        names = archive.namelist()
    assert "site-packages" in {name.split("/", 1)[0] for name in names}
    assert not any(
        name.startswith(("src/", "shared/", "vendor/", "common.pyz"))
        for name in names
    )
