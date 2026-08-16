"""Contracts for the assertion probe's bounded typed event."""

from __future__ import annotations

import builtins
import json
import os
import importlib.util
import sys
import subprocess
from pathlib import Path
from types import ModuleType
import unittest

import pytest

CUT_ROOT = Path(__file__).resolve().parents[2] / "src" / "cut"


def _load_probe() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "cut_assertion_probe_under_test",
        CUT_ROOT / "cut_assertion_probe.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cut_assertion_probe = _load_probe()


_MISSING = object()


@pytest.fixture(autouse=True)
def _restore_process_globals():
    argv = sys.argv
    argv_values = list(argv)
    path = sys.path
    path_values = list(path)
    orig_argv = getattr(sys, "orig_argv", _MISSING)
    orig_argv_values = list(orig_argv) if orig_argv is not _MISSING else None
    excepthook = sys.excepthook
    unittest_main = unittest.main
    importer = builtins.__import__
    test_program_init = unittest.TestProgram.__init__
    modules = dict(sys.modules)
    yield
    argv[:] = argv_values
    sys.argv = argv
    path[:] = path_values
    sys.path = path
    if orig_argv is _MISSING:
        if hasattr(sys, "orig_argv"):
            del sys.orig_argv
    else:
        orig_argv[:] = orig_argv_values
        sys.orig_argv = orig_argv
    sys.excepthook = excepthook
    builtins.__import__ = importer
    unittest.main = unittest_main
    unittest.TestProgram.__init__ = test_program_init
    for name in list(sys.modules):
        if name not in modules:
            del sys.modules[name]
    for name, module in modules.items():
        if sys.modules.get(name) is not module:
            sys.modules[name] = module


def _event(**overrides: object) -> bytes:
    payload: dict[str, object] = {
        "assertion_origin": True,
        "complete": True,
        "event": cut_assertion_probe.EVENT_KIND,
        "runner": "pytest",
        "schema_version": cut_assertion_probe.EVENT_SCHEMA_VERSION,
    }
    payload.update(overrides)
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode()


def test_probe_event_round_trips_exact_assertion_type() -> None:
    encoded = cut_assertion_probe.ProbeEvent("pytest", True).encode()

    assert cut_assertion_probe.ProbeEvent.decode(encoded, "pytest") == (
        cut_assertion_probe.ProbeEvent("pytest", True)
    )


@pytest.mark.parametrize(
    "event",
    [
        pytest.param(b"", id="missing"),
        pytest.param(b"not-json\n", id="malformed"),
        pytest.param(_event(runner="unittest"), id="unexpected-runner"),
        pytest.param(_event(complete=False), id="incomplete"),
        pytest.param(_event() + _event(), id="multiple"),
        pytest.param(b"x" * (cut_assertion_probe.MAX_EVENT_BYTES + 1), id="oversized"),
    ],
)
def test_probe_event_rejects_invalid_transport(event: bytes) -> None:
    assert cut_assertion_probe.ProbeEvent.decode(event, "pytest") is None


@pytest.mark.parametrize("schema_version", [True, 1.0])
def test_probe_event_rejects_non_exact_schema_versions(schema_version: object) -> None:
    assert (
        cut_assertion_probe.ProbeEvent.decode(
            _event(schema_version=schema_version), "pytest"
        )
        is None
    )


def test_direct_code_mode_exposes_python_dash_c_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cut_assertion_probe.sys, "argv", ["worker"])
    monkeypatch.setattr(cut_assertion_probe.sys, "path", ["/worker", "/user"])
    safe_path = cut_assertion_probe.sys.flags.safe_path
    expected_path0 = "/worker" if safe_path else ""
    source = (
        "import sys; "
        "assert sys.argv == ['-c', 'arg']; "
        f"assert sys.path[0] == {expected_path0!r}; "
        f"assert sys.flags.safe_path is {safe_path!r}"
    )

    cut_assertion_probe._run_code(source, ["arg"], sys.executable)

    assert cut_assertion_probe.sys.orig_argv == [
        sys.executable,
        "-c",
        source,
        "arg",
    ]


def test_direct_script_mode_preserves_native_context(tmp_path: Path) -> None:
    script = tmp_path / "script.py"
    sentinel = tmp_path / "script-observation.txt"
    safe_path = cut_assertion_probe.sys.flags.safe_path
    native_path0 = (
        cut_assertion_probe.sys.path[0] if cut_assertion_probe.sys.path else None
    )
    expected_path0 = str(tmp_path.resolve()) if not safe_path else native_path0
    expected_observation = repr(
        (
            [str(script), "arg"],
            expected_path0,
            safe_path,
            [sys.executable, str(script), "arg"],
        )
    )
    script_source = (
        "import pathlib, sys; "
        f"assert sys.argv == [{str(script)!r}, 'arg']; "
        f"assert sys.path[0] == {expected_path0!r}; "
        f"assert sys.flags.safe_path is {safe_path!r}; "
        f"assert sys.orig_argv == [{sys.executable!r}, {str(script)!r}, 'arg']; "
        f"pathlib.Path({str(sentinel)!r}).write_text("
        "repr((sys.argv, sys.path[0], sys.flags.safe_path, sys.orig_argv)), "
        "encoding='utf-8')"
    )
    script.write_text(script_source, encoding="utf-8")

    cut_assertion_probe._run_script(str(script), ["arg"], sys.executable)

    assert sentinel.read_text(encoding="utf-8") == expected_observation


def test_pytest_observes_runner_native_global_argv(tmp_path: Path) -> None:
    pytest_main = importlib.util.find_spec("pytest.__main__")
    assert pytest_main is not None and pytest_main.origin is not None
    test_file = tmp_path / "test_argv.py"
    sentinel = tmp_path / "pytest-observation.txt"
    safe_path = cut_assertion_probe.sys.flags.safe_path
    expected_argv = [pytest_main.origin, str(test_file), "-q"]
    expected_orig_argv = [
        sys.executable,
        "-m",
        "pytest",
        str(test_file),
        "-q",
    ]
    expected_observation = repr(
        (
            expected_argv,
            None if safe_path else str(tmp_path),
            safe_path,
            expected_orig_argv,
        )
    )
    test_file.write_text(
        "def test_argv():\n"
        "    import pathlib, sys\n"
        f"    assert sys.argv == {expected_argv!r}\n"
        f"    assert sys.flags.safe_path is {safe_path!r}\n"
        f"    assert sys.flags.safe_path or sys.path[0] == {str(tmp_path)!r}\n"
        f"    assert sys.orig_argv == {expected_orig_argv!r}\n"
        f"    pathlib.Path({str(sentinel)!r}).write_text("
        "repr((sys.argv, None if sys.flags.safe_path else sys.path[0], "
        "sys.flags.safe_path, sys.orig_argv)), encoding='utf-8')\n",
        encoding="utf-8",
    )
    read_fd, write_fd = os.pipe()
    try:
        returncode = cut_assertion_probe._run_pytest(
            [str(test_file), "-q"],
            write_fd,
            sys.executable,
        )
    finally:
        os.close(write_fd)
    try:
        event = json.loads(os.read(read_fd, cut_assertion_probe.MAX_EVENT_BYTES + 1))
    finally:
        os.close(read_fd)

    assert returncode == 0
    assert event["assertion_origin"] is False
    assert sentinel.read_text(encoding="utf-8") == expected_observation


def test_pytest_ignores_expected_xfail_and_observes_real_failure(
    tmp_path: Path,
) -> None:
    test_file = tmp_path / "test_mixed.py"
    test_file.write_text(
        "import pytest\n\n"
        "@pytest.mark.xfail(reason='expected')\n"
        "def test_expected_assertion():\n"
        "    raise AssertionError('expected xfail')\n\n"
        "def test_real_failure():\n"
        "    raise RuntimeError('AssertionError: witness failure')\n",
        encoding="utf-8",
    )
    read_fd, write_fd = os.pipe()
    try:
        returncode = cut_assertion_probe._run_pytest([str(test_file), "-q"], write_fd)
    finally:
        os.close(write_fd)
    try:
        event = json.loads(os.read(read_fd, cut_assertion_probe.MAX_EVENT_BYTES + 1))
    finally:
        os.close(read_fd)

    assert returncode == 1
    assert event["assertion_origin"] is False


def test_unittest_observes_runner_native_global_argv(tmp_path: Path) -> None:
    unittest_main = importlib.util.find_spec("unittest.__main__")
    assert unittest_main is not None and unittest_main.origin is not None
    (tmp_path / "__init__.py").write_text("", encoding="utf-8")
    test_file = tmp_path / "test_unittest_argv.py"
    sentinel = tmp_path / "unittest-observation.txt"
    safe_path = cut_assertion_probe.sys.flags.safe_path
    expected_argv0 = f"{Path(sys.executable).name} -m unittest"
    expected_argv = [
        expected_argv0,
        "discover",
        "-s",
        str(tmp_path),
        "-p",
        "test_*.py",
    ]
    expected_orig_argv = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(tmp_path),
        "-p",
        "test_*.py",
    ]
    expected_observation = repr(
        (
            expected_argv,
            None if safe_path else str(tmp_path),
            safe_path,
            expected_orig_argv,
        )
    )
    test_file.write_text(
        "import pathlib\n"
        "import sys\n"
        "import unittest\n\n"
        "class ArgvTest(unittest.TestCase):\n"
        "    def test_argv(self):\n"
        f"        self.assertEqual(sys.argv, {expected_argv!r})\n"
        f"        self.assertIs(sys.flags.safe_path, {safe_path!r})\n"
        f"        self.assertTrue(sys.flags.safe_path or sys.path[0] == {str(tmp_path)!r})\n"
        f"        self.assertEqual(sys.orig_argv, {expected_orig_argv!r})\n"
        f"        pathlib.Path({str(sentinel)!r}).write_text("
        "repr((sys.argv, None if sys.flags.safe_path else sys.path[0], "
        "sys.flags.safe_path, sys.orig_argv)), encoding='utf-8')\n",
        encoding="utf-8",
    )
    args = ["discover", "-s", str(tmp_path), "-p", "test_*.py"]
    read_fd, write_fd = os.pipe()
    try:
        returncode = cut_assertion_probe._run_unittest(
            args,
            write_fd,
            sys.executable,
        )
    finally:
        os.close(write_fd)
    try:
        event = json.loads(os.read(read_fd, cut_assertion_probe.MAX_EVENT_BYTES + 1))
    finally:
        os.close(read_fd)

    assert returncode == 0
    assert event["assertion_origin"] is False
    assert sentinel.read_text(encoding="utf-8") == expected_observation


def test_unittest_preserves_stdlib_zero_test_exit_code(tmp_path: Path) -> None:
    (tmp_path / "__init__.py").write_text("", encoding="utf-8")
    args = ["discover", "-s", str(tmp_path), "-p", "test_*.py"]
    expected = subprocess.run(
        [sys.executable, "-m", "unittest", *args],
        cwd=tmp_path.parent,
        capture_output=True,
        text=True,
        timeout=30,
    )
    read_fd, write_fd = os.pipe()
    try:
        returncode = cut_assertion_probe._run_unittest(args, write_fd)
    finally:
        os.close(write_fd)
    try:
        event = json.loads(os.read(read_fd, cut_assertion_probe.MAX_EVENT_BYTES + 1))
    finally:
        os.close(read_fd)

    assert returncode == expected.returncode
    assert event["assertion_origin"] is False
