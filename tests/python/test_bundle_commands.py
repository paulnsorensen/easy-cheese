"""Behavioral contract for easy_cheese.shared.bundle_commands.

Covers the declarative command registry in isolation: registration and its
validation, sorted introspection, reference-checked compilation, dispatch exit
codes and argument forwarding, and generated-guidance rendering plus drift
detection. The registry is module-global mutable state, so every test runs
against a snapshot restored on teardown and registers handlers under an
explicit module key.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from easy_cheese.shared import bundle_commands as bc

MODULE = "test_module"


@pytest.fixture(autouse=True)
def _isolate_registry() -> Iterator[None]:
    snapshot = {key: dict(value) for key, value in bc._REGISTRY.items()}
    try:
        yield
    finally:
        bc._REGISTRY.clear()
        bc._REGISTRY.update(snapshot)


def register(name: str, *, module: str = MODULE, ret: int | str = 0, doc: str | None = None):
    calls: list[list[str]] = []

    def handler(argv: list[str]):
        calls.append(argv)
        return ret

    handler.__module__ = module
    handler.__name__ = f"{name}_impl"
    handler.__doc__ = doc
    handler.calls = calls  # type: ignore[attr-defined]
    return bc.bundle_command(name)(handler)


def test_decorator_registers_and_marks_function() -> None:
    handler = register("go")
    assert handler.__bundle_command__ == "go"  # type: ignore[attr-defined]
    assert [c.name for c in bc.registered_commands(MODULE)] == ["go"]


@pytest.mark.parametrize("name", ["Bad", "", "-x", "_x", "a b", "camelCase"])
def test_invalid_command_name_rejected(name: str) -> None:
    with pytest.raises(ValueError, match="invalid command name"):
        bc.bundle_command(name)


def test_duplicate_command_rejected() -> None:
    register("go")
    with pytest.raises(ValueError, match="duplicate bundle command"):
        register("go")


def test_registered_commands_sorted_by_name() -> None:
    register("beta")
    register("alpha")
    assert [c.name for c in bc.registered_commands(MODULE)] == ["alpha", "beta"]


def test_compile_requires_registered_commands() -> None:
    with pytest.raises(ValueError, match="no bundle commands registered"):
        bc.compile_bundle_commands("no-such-module")


def test_compile_maps_name_to_function_name() -> None:
    register("a")
    register("b")
    assert bc.compile_bundle_commands(MODULE) == {"a": "a_impl", "b": "b_impl"}


def test_compile_flags_unreferenced_and_missing() -> None:
    register("a")
    register("b")
    with pytest.raises(ValueError, match=r"unreferenced=\['b'\], missing=\['c'\]"):
        bc.compile_bundle_commands(MODULE, referenced={"a", "c"})


def test_compile_accepts_exact_reference_set() -> None:
    register("a")
    register("b")
    assert bc.compile_bundle_commands(MODULE, referenced={"a", "b"}) == {
        "a": "a_impl",
        "b": "b_impl",
    }


def test_dispatch_invokes_handler_and_forwards_args() -> None:
    handler = register("go", ret=7)
    assert bc.dispatch(MODULE, ["go", "x", "y"]) == 7
    assert handler.calls == [["x", "y"]]  # type: ignore[attr-defined]


def test_dispatch_empty_argv_prints_usage_and_returns_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    register("go")
    assert bc.dispatch(MODULE, []) == 2
    assert "usage: <pyz> {go}" in capsys.readouterr().out


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_dispatch_help_returns_0(flag: str, capsys: pytest.CaptureFixture[str]) -> None:
    register("go")
    assert bc.dispatch(MODULE, [flag]) == 0
    assert "usage:" in capsys.readouterr().out


def test_dispatch_unknown_command_returns_2_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    register("go")
    assert bc.dispatch(MODULE, ["nope"]) == 2
    assert "usage:" in capsys.readouterr().err


def test_dispatch_detects_stale_expected_map() -> None:
    register("go")
    with pytest.raises(RuntimeError, match="stale"):
        bc.dispatch(MODULE, ["go"], expected={"go": "wrong_impl"})


def test_dispatch_accepts_matching_expected_map() -> None:
    register("go", ret=0)
    assert bc.dispatch(MODULE, ["go"], expected={"go": "go_impl"}) == 0


def test_dispatch_rejects_non_integer_status() -> None:
    register("go", ret="oops")
    with pytest.raises(TypeError, match="did not return an integer status"):
        bc.dispatch(MODULE, ["go"])


def test_guidance_source_renders_first_docline_sorted() -> None:
    register("beta", doc="Second command.\nignored detail.")
    register("alpha", doc="First command.")
    assert bc.guidance_source(MODULE) == (
        "<!-- GENERATED BUNDLE COMMANDS:START -->\n"
        "- `alpha` — First command.\n"
        "- `beta` — Second command.\n"
        "<!-- GENERATED BUNDLE COMMANDS:END -->"
    )


def test_validate_generated_region_accepts_current_block() -> None:
    register("go", doc="Do the thing.")
    text = f"prefix\n{bc.guidance_source(MODULE)}\nsuffix"
    bc.validate_generated_region(text, MODULE)


def test_validate_generated_region_flags_drift() -> None:
    register("go", doc="Do the thing.")
    stale = (
        "<!-- GENERATED BUNDLE COMMANDS:START -->\n"
        "- `go` — Stale description.\n"
        "<!-- GENERATED BUNDLE COMMANDS:END -->"
    )
    with pytest.raises(ValueError, match="generated command guidance drift"):
        bc.validate_generated_region(stale, MODULE)


def test_validate_generated_region_flags_missing_block() -> None:
    register("go", doc="Do the thing.")
    with pytest.raises(ValueError, match="generated command guidance drift"):
        bc.validate_generated_region("no markers here", MODULE)
