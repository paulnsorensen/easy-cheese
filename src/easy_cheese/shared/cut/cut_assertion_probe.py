#!/usr/bin/env python3
"""Observe assertion failures inside supported Python test runners."""

from __future__ import annotations

import builtins
import importlib.machinery
import importlib.util
import json
import os
import runpy
import sys
from collections.abc import Callable, Generator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MethodType, ModuleType, TracebackType
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    import pytest
    from pluggy import Result
    from _pytest.reports import TestReport

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
            payload = cast(object, json.loads(raw))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        fields = cast(dict[str, object], payload)
        if set(fields) != set(_EVENT_KEYS):
            return None
        assertion_origin = fields["assertion_origin"]
        if (
            type(fields["schema_version"]) is not int
            or fields["schema_version"] != EVENT_SCHEMA_VERSION
            or fields["event"] != EVENT_KIND
            or fields["runner"] != expected_runner
            or expected_runner not in _RUNNERS
            or fields["complete"] is not True
            or type(assertion_origin) is not bool
        ):
            return None
        return cls(expected_runner, assertion_origin)


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


_ExcInfo = tuple[type[BaseException], BaseException, TracebackType]


class _TestCase(Protocol):
    defaultTestResult: Callable[[], object]

    def run(self, *args: object, **kwargs: object) -> object: ...


class _TestProgram(Protocol):
    def __init__(self, *args: object, **kwargs: object) -> None: ...
    def runTests(self) -> None: ...


class _UnittestModule(Protocol):
    @property
    def TestCase(self) -> type[_TestCase]: ...
    @property
    def TestProgram(self) -> type[_TestProgram]: ...


def _install_unittest_probe(
    unittest_module: _UnittestModule,
    observation: _Observation,
) -> Callable[..., None]:
    def observe_result(result: object) -> Callable[[], None]:
        missing = object()
        originals: list[tuple[str, object]] = []

        def wrap_result_method(
            method_name: str,
            error_index: int,
        ) -> None:
            original_method: Callable[..., object] | None = getattr(
                result, method_name, None
            )
            if original_method is None:
                return
            originals.append((method_name, vars(result).get(method_name, missing)))

            def observed_method(
                _result: object,
                *args: object,
                **kwargs: object,
            ) -> object:
                error = cast(
                    "_ExcInfo | None",
                    args[error_index]
                    if len(args) > error_index
                    else kwargs.get("err"),
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

    original_run_tests: Callable[[_TestProgram], None] = (
        unittest_module.TestProgram.runTests
    )
    original_test_case_run: Callable[..., object] = unittest_module.TestCase.run

    def probe_test_case_run(
        self: _TestCase,
        *args: object,
        **kwargs: object,
    ) -> object:
        result = args[0] if args else kwargs.get("result")
        if result is None:
            original_factory = self.defaultTestResult
            missing = object()
            previous_factory = cast(
                object, vars(self).get("defaultTestResult", missing)
            )
            result_restorers: list[Callable[[], None]] = []

            def probe_default_result(_test_case: object) -> object:
                created = original_factory()
                result_restorers.append(observe_result(created))
                return created

            self.defaultTestResult = MethodType(probe_default_result, self)
            try:
                return original_test_case_run(self, *args, **kwargs)
            finally:
                for restore_result in reversed(result_restorers):
                    restore_result()
                if previous_factory is missing:
                    del self.defaultTestResult
                else:
                    self.defaultTestResult = cast(
                        "Callable[[], object]", previous_factory
                    )
        restore_result = observe_result(result)
        try:
            return original_test_case_run(self, *args, **kwargs)
        finally:
            restore_result()

    def probe_run_tests(self: _TestProgram) -> None:
        unittest_module.TestCase.run = probe_test_case_run
        try:
            original_run_tests(self)
        finally:
            unittest_module.TestCase.run = original_test_case_run

    original_init: Callable[..., None] = unittest_module.TestProgram.__init__

    def probe_test_program_init(
        self: _TestProgram,
        *args: object,
        **kwargs: object,
    ) -> None:
        unittest_module.TestProgram.runTests = probe_run_tests
        try:
            original_init(self, *args, **kwargs)
        finally:
            unittest_module.TestProgram.runTests = original_run_tests

    unittest_module.TestProgram.__init__ = probe_test_program_init
    return original_init


# Resolved once: the stdlib location never changes within a run, and this
# check sits on the hooked-__import__ hot path.
_STDLIB_UNITTEST_INIT = Path(os.__file__).resolve().parent / "unittest" / "__init__.py"


def _stdlib_unittest(module: object) -> _UnittestModule | None:
    if not isinstance(module, ModuleType):
        return None
    spec = module.__spec__
    origin = spec.origin if spec is not None else None
    if origin is None or Path(origin).resolve() != _STDLIB_UNITTEST_INIT:
        return None
    if not all(
        getattr(module, name, None) is not None
        for name in ("TestCase", "TestProgram")
    ):
        return None
    return cast(_UnittestModule, cast(object, module))


class _PytestAssertionProbe:
    def __init__(self, observation: _Observation) -> None:
        self._observation: _Observation = observation

    def pytest_runtest_makereport(
        self, item: pytest.Item, call: pytest.CallInfo[None]
    ) -> Generator[None, Result[TestReport], None]:
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
    setattr(main_module, "__builtins__", builtins)  # noqa: V101
    main_module.__spec__ = None
    main_module.__package__ = None  # noqa: V101
    main_module.__loader__ = importlib.machinery.BuiltinImporter  # noqa: V101
    missing = object()
    previous_main = sys.modules.get("__main__", missing)
    sys.modules["__main__"] = main_module
    try:
        exec(compile(source, "<string>", "exec"), main_module.__dict__)
    finally:
        if previous_main is missing:
            _ = sys.modules.pop("__main__", None)
        else:
            sys.modules["__main__"] = cast(ModuleType, previous_main)


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
    main_module.__loader__ = loader  # noqa: V101
    setattr(main_module, "__cached__", None)  # noqa: V101
    main_module.__package__ = None  # noqa: V101
    main_module.__spec__ = None
    setattr(main_module, "__builtins__", builtins)  # noqa: V101
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
            _ = sys.modules.pop("__main__", None)
        else:
            sys.modules["__main__"] = cast(ModuleType, previous_main)


def _run_direct(
    runner: str,
    target: str,
    args: list[str],
    descriptor: int,
    original_argv0: str | None = None,
) -> int:
    observation = _Observation(runner)
    original_import: Callable[
        [
            str,
            Mapping[str, object] | None,
            Mapping[str, object] | None,
            Sequence[str] | None,
            int,
        ],
        ModuleType,
    ] = builtins.__import__
    original_test_program_inits: dict[_UnittestModule, Callable[..., None]] = {}

    def instrument(module: object) -> None:
        unittest_module = _stdlib_unittest(module)
        if unittest_module is None or unittest_module in original_test_program_inits:
            return
        original_test_program_inits[unittest_module] = _install_unittest_probe(
            unittest_module, observation
        )

    def import_with_probe(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] | None = (),
        level: int = 0,
    ) -> ModuleType:
        imported = cast(
            ModuleType, original_import(name, globals, locals, fromlist, level)
        )
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
        _ = observation.emit(descriptor)
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
    _ = pytest.hookimpl(hookwrapper=True)(_PytestAssertionProbe.pytest_runtest_makereport)
    sys.argv = [_runner_main_origin("pytest"), *args]
    seam_module, seam_attr = _pytest_console_seam(pytest, pytest_config)
    original_console_main = cast(Callable[[], int], getattr(seam_module, seam_attr))
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
        _ = runpy.run_module(
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
    unittest_module = cast(_UnittestModule, cast(object, sys.modules["unittest"]))
    original_init = _install_unittest_probe(unittest_module, observation)
    runner_argv = [_runner_main_origin("unittest"), *args]
    sys.argv = runner_argv
    try:
        _ = runpy.run_module(
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
            + "<code|script|pytest|unittest> <origin> [args ...]",
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
