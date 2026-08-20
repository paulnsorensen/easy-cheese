#!/usr/bin/env python3
# ships-as: press.pyz (module)
"""Observe assertion failures inside supported Python test runners."""

from __future__ import annotations

import builtins
import importlib.machinery
import importlib.util
import json
import os
import runpy
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import MethodType, ModuleType
from typing import Any

EVENT_KIND = "cut.assertion-origin"
EVENT_SCHEMA_VERSION = 1
MAX_EVENT_BYTES = 512
_RUNNERS = frozenset({"code", "script", "pytest", "unittest"})
_EVENT_KEYS = frozenset(
    {"assertion_origin", "complete", "event", "runner", "schema_version"}
)


@dataclass(frozen=True)
class ProbeEvent:
    """A complete assertion-origin observation from one child runner."""

    runner: str
    assertion_origin: bool

    def encode(self) -> bytes:
        payload = {
            "assertion_origin": self.assertion_origin,
            "complete": True,
            "event": EVENT_KIND,
            "runner": self.runner,
            "schema_version": EVENT_SCHEMA_VERSION,
        }
        encoded = (
            json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"
        ).encode("utf-8")
        if len(encoded) > MAX_EVENT_BYTES:
            raise ValueError("assertion probe event exceeds protocol limit")
        return encoded

    @classmethod
    def decode(cls, raw: bytes, expected_runner: str) -> ProbeEvent | None:
        """Decode exactly one complete event, returning ``None`` on any mismatch."""
        if (
            not raw
            or len(raw) > MAX_EVENT_BYTES
            or not raw.endswith(b"\n")
            or raw.count(b"\n") != 1
        ):
            return None
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or set(payload) != _EVENT_KEYS:
            return None
        if (
            type(payload["schema_version"]) is not int
            or payload["schema_version"] != EVENT_SCHEMA_VERSION
            or payload["event"] != EVENT_KIND
            or payload["runner"] != expected_runner
            or expected_runner not in _RUNNERS
            or payload["complete"] is not True
            or type(payload["assertion_origin"]) is not bool
        ):
            return None
        return cls(expected_runner, payload["assertion_origin"])


@dataclass
class _Observation:
    runner: str
    assertion_origin: bool = False

    def observe(self, exception_type: type[BaseException]) -> None:
        if issubclass(exception_type, AssertionError):
            self.assertion_origin = True

    def emit(self, descriptor: int) -> bool:
        payload = ProbeEvent(self.runner, self.assertion_origin).encode()
        try:
            written = os.write(descriptor, payload)
        except OSError as error:
            print(f"assertion probe event write failed: {error}", file=sys.stderr)
            return False
        if written != len(payload):
            print("assertion probe event write was incomplete", file=sys.stderr)
            return False
        return True


def _install_unittest_probe(
    unittest_module: ModuleType,
    observation: _Observation,
) -> Callable[..., Any]:
    def observe_result(result: Any) -> Callable[[], None]:
        missing = object()
        originals: list[tuple[str, object]] = []

        def wrap_result_method(
            method_name: str,
            error_index: int,
        ) -> None:
            original_method = getattr(result, method_name, None)
            if original_method is None:
                return
            originals.append((method_name, vars(result).get(method_name, missing)))

            def observed_method(
                _result: Any,
                *args: Any,
                **kwargs: Any,
            ) -> Any:
                error = (
                    args[error_index]
                    if len(args) > error_index
                    else kwargs.get("err")
                )
                if error is not None:
                    observation.observe(error[0])
                return original_method(*args, **kwargs)

            setattr(result, method_name, MethodType(observed_method, result))

        wrap_result_method("addFailure", 1)
        wrap_result_method("addError", 1)
        wrap_result_method("addSubTest", 2)

        def restore_result() -> None:
            for method_name, original in reversed(originals):
                if original is missing:
                    delattr(result, method_name)
                else:
                    setattr(result, method_name, original)

        return restore_result

    original_run_tests = unittest_module.TestProgram.runTests
    original_test_case_run = unittest_module.TestCase.run

    def probe_test_case_run(
        test_case: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        result = args[0] if args else kwargs.get("result")
        if result is None:
            original_factory = test_case.defaultTestResult
            missing = object()
            previous_factory = vars(test_case).get("defaultTestResult", missing)
            result_restorers: list[Callable[[], None]] = []

            def probe_default_result(_test_case: Any) -> Any:
                created = original_factory()
                result_restorers.append(observe_result(created))
                return created

            test_case.defaultTestResult = MethodType(probe_default_result, test_case)
            try:
                return original_test_case_run(test_case, *args, **kwargs)
            finally:
                for restore_result in reversed(result_restorers):
                    restore_result()
                if previous_factory is missing:
                    del test_case.defaultTestResult
                else:
                    test_case.defaultTestResult = previous_factory
        restore_result = observe_result(result)
        try:
            return original_test_case_run(test_case, *args, **kwargs)
        finally:
            restore_result()

    def probe_run_tests(program: Any) -> Any:
        unittest_module.TestCase.run = probe_test_case_run
        try:
            return original_run_tests(program)
        finally:
            unittest_module.TestCase.run = original_test_case_run

    original_init = unittest_module.TestProgram.__init__

    def probe_test_program_init(
        self: Any,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        unittest_module.TestProgram.runTests = probe_run_tests
        try:
            original_init(self, *args, **kwargs)
        finally:
            unittest_module.TestProgram.runTests = original_run_tests

    unittest_module.TestProgram.__init__ = probe_test_program_init
    return original_init


def _stdlib_unittest(module: object) -> ModuleType | None:
    if not isinstance(module, ModuleType):
        return None
    spec = getattr(module, "__spec__", None)
    origin = getattr(spec, "origin", None)
    expected = Path(os.__file__).resolve().parent / "unittest" / "__init__.py"
    if origin is None or Path(origin).resolve() != expected:
        return None
    if not all(
        getattr(module, name, None) is not None
        for name in ("TestCase", "TestProgram")
    ):
        return None
    return module


class _PytestAssertionProbe:
    def __init__(self, observation: _Observation) -> None:
        self._observation = observation

    def pytest_runtest_makereport(self, item: Any, call: Any) -> Any:
        del item
        outcome = yield
        report = outcome.get_result()
        if report.failed and call.excinfo is not None:
            self._observation.observe(call.excinfo.type)


def _set_native_path0(path: str) -> None:
    if sys.flags.safe_path:
        return
    if sys.path:
        sys.path[0] = path
    else:
        sys.path.append(path)


def _set_original_argv(original_argv0: str | None, command: list[str]) -> None:
    if original_argv0 is not None:
        sys.orig_argv = [original_argv0, *command]


def _run_code(
    source: str,
    args: list[str],
    original_argv0: str | None = None,
) -> None:
    sys.argv = ["-c", *args]
    _set_native_path0("")
    _set_original_argv(original_argv0, ["-c", source, *args])
    main_module = ModuleType("__main__")
    main_module.__builtins__ = builtins
    main_module.__spec__ = None
    main_module.__package__ = None
    main_module.__loader__ = importlib.machinery.BuiltinImporter
    missing = object()
    previous_main = sys.modules.get("__main__", missing)
    sys.modules["__main__"] = main_module
    try:
        exec(compile(source, "<string>", "exec"), main_module.__dict__)
    finally:
        if previous_main is missing:
            sys.modules.pop("__main__", None)
        else:
            sys.modules["__main__"] = previous_main


def _run_script(
    target: str,
    args: list[str],
    original_argv0: str | None = None,
) -> None:
    sys.argv = [target, *args]
    _set_native_path0(str(Path(target).resolve().parent))
    _set_original_argv(original_argv0, [target, *args])
    loader = importlib.machinery.SourceFileLoader("__main__", target)
    main_module = ModuleType("__main__")
    main_module.__file__ = target
    main_module.__loader__ = loader
    main_module.__cached__ = None
    main_module.__package__ = None
    main_module.__spec__ = None
    main_module.__builtins__ = builtins
    missing = object()
    previous_main = sys.modules.get("__main__", missing)
    sys.modules["__main__"] = main_module
    try:
        code = loader.get_code("__main__")
        if code is None:
            raise ImportError(f"could not load {target!r}")
        exec(code, main_module.__dict__)
    finally:
        if previous_main is missing:
            sys.modules.pop("__main__", None)
        else:
            sys.modules["__main__"] = previous_main


def _run_direct(
    runner: str,
    target: str,
    args: list[str],
    descriptor: int,
    original_argv0: str | None = None,
) -> int:
    observation = _Observation(runner)
    original_import = builtins.__import__
    original_test_program_inits: dict[ModuleType, Any] = {}

    def instrument(module: object) -> None:
        unittest_module = _stdlib_unittest(module)
        if unittest_module is None or unittest_module in original_test_program_inits:
            return
        original_test_program_inits[unittest_module] = _install_unittest_probe(
            unittest_module, observation
        )

    def import_with_probe(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        imported = original_import(name, globals, locals, fromlist, level)
        instrument(sys.modules.get("unittest"))
        return imported

    instrument(sys.modules.get("unittest"))

    builtins.__import__ = import_with_probe
    try:
        if runner == "code":
            _run_code(target, args, original_argv0)
        else:
            _run_script(target, args, original_argv0)
    except SystemExit:
        if not observation.emit(descriptor):
            raise SystemExit(126) from None
        raise
    except BaseException as error:
        observation.observe(type(error))
        observation.emit(descriptor)
        raise
    finally:
        builtins.__import__ = original_import
        for unittest_module, original_init in original_test_program_inits.items():
            unittest_module.TestProgram.__init__ = original_init
    return 0 if observation.emit(descriptor) else 126


def _runner_main_origin(runner: str) -> str:
    spec = importlib.util.find_spec(f"{runner}.__main__")
    if spec is None or spec.origin is None:
        raise RuntimeError(f"unable to resolve {runner}.__main__ origin")
    return spec.origin


def _pytest_console_seam(
    pytest_module: ModuleType, pytest_config: ModuleType
) -> tuple[ModuleType, str]:
    """Return (module, attr) that this interpreter's pytest.__main__ calls.

    pytest >= 9.1 routes __main__ through the private _pytest.config._console_main;
    older releases call the public pytest.console_main.
    """
    if hasattr(pytest_config, "_console_main"):
        return pytest_config, "_console_main"
    return pytest_module, "console_main"


def _run_pytest(
    args: list[str],
    descriptor: int,
    original_argv0: str | None = None,
) -> int:
    _set_native_path0(str(Path.cwd().resolve()))
    _set_original_argv(original_argv0, ["-m", "pytest", *args])
    import pytest
    import _pytest.config as pytest_config

    observation = _Observation("pytest")
    pytest.hookimpl(hookwrapper=True)(_PytestAssertionProbe.pytest_runtest_makereport)
    sys.argv = [_runner_main_origin("pytest"), *args]
    seam_module, seam_attr = _pytest_console_seam(pytest, pytest_config)
    original_console_main = getattr(seam_module, seam_attr)
    returncode = 0

    def probe_console_main() -> int:
        nonlocal returncode
        setattr(seam_module, seam_attr, original_console_main)
        main_module = sys.modules.get("__main__")
        if (
            main_module is not None
            and getattr(main_module, seam_attr, None) is probe_console_main
        ):
            setattr(main_module, seam_attr, original_console_main)
        returncode = int(
            pytest.main(args, plugins=[_PytestAssertionProbe(observation)])
        )
        return returncode

    setattr(seam_module, seam_attr, probe_console_main)
    try:
        runpy.run_module(
            "pytest.__main__",
            run_name="__main__",
            alter_sys=True,
            init_globals={"__builtins__": builtins},
        )
    except SystemExit as error:
        returncode = error.code if isinstance(error.code, int) else 1
    finally:
        setattr(seam_module, seam_attr, original_console_main)
        main_module = sys.modules.get("__main__")
        if (
            main_module is not None
            and getattr(main_module, seam_attr, None) is probe_console_main
        ):
            setattr(main_module, seam_attr, original_console_main)
    return returncode if observation.emit(descriptor) else 126


def _run_unittest(
    args: list[str],
    descriptor: int,
    original_argv0: str | None = None,
) -> int:
    _set_native_path0(str(Path.cwd().resolve()))
    _set_original_argv(original_argv0, ["-m", "unittest", *args])
    import unittest

    observation = _Observation("unittest")
    original_init = _install_unittest_probe(unittest, observation)
    runner_argv = [_runner_main_origin("unittest"), *args]
    sys.argv = runner_argv
    try:
        runpy.run_module(
            "unittest.__main__",
            run_name="__main__",
            alter_sys=True,
            init_globals={"__builtins__": builtins},
        )
    except SystemExit as error:
        returncode = error.code if isinstance(error.code, int) else 1
    else:
        returncode = 0
    finally:
        unittest.TestProgram.__init__ = original_init
    return returncode if observation.emit(descriptor) else 126


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        print(
            "usage: python -m cut_assertion_probe <fd> "
            "<code|script|pytest|unittest> <origin> [args ...]",
            file=sys.stderr,
        )
        return 2
    try:
        descriptor = int(args.pop(0))
    except ValueError:
        print("assertion probe descriptor must be an integer", file=sys.stderr)
        return 2
    runner = args.pop(0)
    if descriptor < 0 or runner not in _RUNNERS or not args:
        print("assertion probe arguments are invalid", file=sys.stderr)
        return 2
    original_argv0 = args.pop(0)
    if runner == "pytest":
        return _run_pytest(args, descriptor, original_argv0)
    if runner == "unittest":
        return _run_unittest(args, descriptor, original_argv0)
    if not args:
        print(f"assertion probe {runner} target is missing", file=sys.stderr)
        return 2
    return _run_direct(
        runner,
        args[0],
        args[1:],
        descriptor,
        original_argv0,
    )


if __name__ == "__main__":
    raise SystemExit(main())
