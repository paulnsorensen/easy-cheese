"""Integration-seam coherence checks for the baseline-quality-gate policy.

Each per-curd press pass hardened its own file in isolation:
- curd 2 asserted cook/SKILL.md's terse baseline-policy summary against
  itself, but never against the shared source of truth it restates
  (skills/cook/references/quality-gates.md). A future edit to one without
  the other would silently drift and no test would catch it.
- W2 (curd 6) added `_cmd_classify` unit coverage and curd 1 documented the
  `python3 skills/ultracook/scripts/ultracook.pyz baseline` example in
  ultracook/SKILL.md, but nothing ties that documented example command to
  the actual subcommand dispatch table -- the class of bug this run
  actually hit (baseline.py was undocumented in ultracook.pyz until the
  final wiring commit).
- curd 4 asserted every consumer's handoff-slug fence carries a bare
  `baseline:` line, and curd 5 asserted the JSON-schema/validator agree on
  required keys, but nothing ties quality-gates.md's own worked-example
  YAML block to that same schema -- a key renamed in the doc's example
  would drift from the schema/validator silently.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COOK_SKILL = REPO_ROOT / "skills" / "cook" / "SKILL.md"
QUALITY_GATES = REPO_ROOT / "skills" / "cook" / "references" / "quality-gates.md"
ULTRACOOK_SKILL = REPO_ROOT / "skills" / "ultracook" / "SKILL.md"
MANIFEST_SCHEMA = REPO_ROOT / "skills" / "ultracook" / "references" / "manifest-schema.json"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Cross-doc policy drift: cook/SKILL.md's summary vs quality-gates.md
# ---------------------------------------------------------------------------

# Each phrase is load-bearing policy language present, verbatim, in both
# cook/SKILL.md's terse restatement and quality-gates.md's canonical text.
# If either doc's wording changes without updating the other, one of these
# fails -- catching drift that per-file tests (which only ever read one of
# the two files) structurally cannot.
LOAD_BEARING_PHRASES = (
    "never captures its own",
    "no frame)",
    "lazily",
    "pre-change tree",
    "halt, never fix silently",
    "2 fix rounds",
    "twice",
    "rounds exhaust",
    "no-progress check trips",
    "design-shaped",
    "resume never re-asks",
)


class TestCookSkillMatchesQualityGatesDoc:
    def test_quality_gates_reference_exists(self) -> None:
        assert QUALITY_GATES.is_file(), (
            "cook/SKILL.md links to references/quality-gates.md as the shared "
            "source of truth; the file must exist for that link to resolve"
        )

    def test_load_bearing_phrases_appear_in_both_docs(self) -> None:
        cook_body = read(COOK_SKILL)
        gates_body = read(QUALITY_GATES)
        missing_from_cook = [p for p in LOAD_BEARING_PHRASES if p not in cook_body]
        missing_from_gates = [p for p in LOAD_BEARING_PHRASES if p not in gates_body]
        assert not missing_from_cook, (
            f"cook/SKILL.md is missing policy phrases present in quality-gates.md: "
            f"{missing_from_cook}"
        )
        assert not missing_from_gates, (
            f"quality-gates.md is missing policy phrases present in cook/SKILL.md: "
            f"{missing_from_gates}"
        )


# ---------------------------------------------------------------------------
# 2. Doc example <-> CLI truth: ultracook/SKILL.md's documented command must
#    actually dispatch through the built .pyz bundle.
# ---------------------------------------------------------------------------


class TestBaselineCaptureExampleDispatches:
    def test_skill_doc_names_the_documented_subcommand(self) -> None:
        body = read(ULTRACOOK_SKILL)
        assert "ultracook.pyz baseline" in body, (
            "ultracook/SKILL.md's Baseline capture example must document the "
            "`ultracook.pyz baseline` invocation this test then verifies "
            "actually dispatches"
        )

    def test_documented_baseline_subcommand_actually_dispatches(self) -> None:
        # Build the real ultracook.pyz bundle the same way tests/fanout does
        # and invoke it exactly as the doc's example prescribes: subcommand
        # `baseline`, gate failures as JSON on stdin. If a future edit
        # unregisters baseline.py from the bundle (as it was before the
        # wiring commit landed), this fails instead of the doc silently
        # documenting a dead command.
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import build_pyz  # noqa: E402  (path must be set before import)

        bundle = build_pyz.cached_bundle("ultracook")
        payload = {
            "baseline": [{"suite": "unit", "test_id": "test_a", "signature": "boom"}],
            "current": [{"suite": "unit", "test_id": "test_a", "signature": "boom"}],
        }
        result = subprocess.run(
            [sys.executable, str(bundle), "baseline"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"documented `ultracook.pyz baseline` command failed: {result.stderr}"
        )
        emitted = json.loads(result.stdout)
        assert emitted == {
            "identical": [{"suite": "unit", "test_id": "test_a", "signature": "boom"}],
            "new": [],
            "changed": [],
            "resolved": [],
        }


# ---------------------------------------------------------------------------
# 3. Slug-fence shape agreement: quality-gates.md's worked example vs the
#    manifest JSON schema's required-key set.
# ---------------------------------------------------------------------------


def _example_yaml_block(body: str) -> str:
    marker = "```yaml"
    start = body.index(marker) + len(marker)
    end = body.index("```", start)
    return body[start:end]


class TestBaselineBlockShapeAgreesWithSchema:
    def test_quality_gates_example_keys_match_manifest_schema(self) -> None:
        example = _example_yaml_block(read(QUALITY_GATES))
        schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
        baseline_schema = schema["properties"]["baseline"]
        gate_schema = baseline_schema["properties"]["gates"]["items"]
        failure_schema = gate_schema["properties"]["failures"]["items"]

        # Top-level baseline keys the doc's example shows.
        assert "captured_at:" in example
        assert "gates:" in example
        for key in baseline_schema["required"]:
            assert f"{key}:" in example, (
                f"quality-gates.md's worked example is missing required "
                f"top-level baseline key `{key}` from manifest-schema.json"
            )

        # Per-gate keys (cmd, failures).
        for key in gate_schema["required"]:
            assert key in example, (
                f"quality-gates.md's worked example is missing required "
                f"gate key `{key}` from manifest-schema.json"
            )

        # Per-failure keys (suite, test_id, signature).
        for key in failure_schema["required"]:
            assert key in example, (
                f"quality-gates.md's worked example is missing required "
                f"failure key `{key}` from manifest-schema.json"
            )
