"""The documented mini-spec template must satisfy the canonical Mold contract.

`skills/mold/references/mini-spec-mode.md` is the only source a tier-1 mint
reads. A template that omits required frontmatter or the Grounding table makes
the validator invent probe outcomes that nobody recorded.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "src" / "easy_cheese" / "skills" / "mold" / "validate_spec.py"
TEMPLATE = REPO_ROOT / "skills" / "mold" / "references" / "mini-spec-mode.md"

FILLED_MINI_SPEC = """---
slug: sample-mini-spec
status: draft
source: agent-mini-spec
created: 2026-09-05
confidence: medium
intent: Clarify the Mold documentation.
blast_radius: low
inputs: Existing Mold documentation.
outputs: Updated Mold documentation.
agent_resolution: []
gate_applicability:
  disposition: not-applicable
  work_class: docs-only
  ui_surface: not-applicable
  reason: Documentation-only change.
verification: Run the documentation build.
---

## Contract
Clarify existing documentation without changing runtime behavior.

## Grounding

| Probe | Outcome | Evidence |
| --- | --- | --- |
| wiki | miss | the repository wiki has no entry for this topic |
| explorer | hit | .cheese/notes/explorer.md names the module |

## Acceptance
- AC-1: WHEN the documentation build runs THE SYSTEM SHALL complete successfully.

## Non-goals
- Runtime behavior changes.
"""


def _template() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "field", ["status: draft", "created:", "confidence:", "agent_resolution:"]
)
def test_template_declares_each_required_frontmatter_field(field: str) -> None:
    """The validator must read a real value, not a default it invented."""
    assert field in _template()


@pytest.mark.parametrize("probe", ["| wiki |", "| explorer |"])
def test_template_declares_each_grounding_probe(probe: str) -> None:
    """Each probe carries one recorded row, so no row is synthesized."""
    body = _template()
    assert "## Grounding" in body
    assert probe in body


def test_template_never_says_to_invent_a_row() -> None:
    assert "Never invent a row." in _template()


def test_filled_template_passes_strict_validation(tmp_path: Path) -> None:
    """A mini-spec written from the template mints cleanly under --strict."""
    spec = tmp_path / "mini-spec.md"
    _ = spec.write_text(FILLED_MINI_SPEC, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "--strict", str(spec)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_strict_validation_rejects_a_malformed_grounding_row(tmp_path: Path) -> None:
    """A recorded probe with blank evidence is a rejection, not a default."""
    spec = tmp_path / "mini-spec.md"
    _ = spec.write_text(
        FILLED_MINI_SPEC.replace(
            "| wiki | miss | the repository wiki has no entry for this topic |",
            "| wiki | miss |  |",
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "--strict", str(spec)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "ERROR:" in result.stdout + result.stderr
