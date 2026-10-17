"""Guard the contributor guide against drift from the real command surface."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRIBUTING = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
JUSTFILE = (REPO_ROOT / "justfile").read_text(encoding="utf-8")


def test_documents_the_decorator_command_contract() -> None:
    for token in ("@bundle_command", "derive_command", "validate_command_surface"):
        assert token in CONTRIBUTING, f"CONTRIBUTING.md must document {token}"


def test_does_not_teach_the_rejected_command_pattern() -> None:
    assert 'Command(name, "module:callable")' not in CONTRIBUTING
    assert "Do not add a decorator-based registry." not in CONTRIBUTING


def test_names_every_toolchain_the_full_gate_requires() -> None:
    assert "node --test" in JUSTFILE
    assert "cargo test" in JUSTFILE
    assert "corepack pnpm" in JUSTFILE
    for prerequisite in ("Corepack", "Cargo", "bats-core", "ShellCheck", "uv"):
        assert prerequisite in CONTRIBUTING, f"CONTRIBUTING.md must name {prerequisite}"


def test_uses_the_canonical_verification_commands() -> None:
    assert "just test" in CONTRIBUTING
    assert "Run `just check` before you open a pull request." in CONTRIBUTING
    assert "python3 -m pytest tests/python -q" not in CONTRIBUTING
