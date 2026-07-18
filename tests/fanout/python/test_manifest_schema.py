"""Manifest schema sanity checks.

The schema is JSON-Schema-shaped but the easy-cheese repo pins itself to
pyyaml + pytest as the only third-party deps. So we don't bring jsonschema
in — instead we verify the schema parses, has the right top-level fields,
and that an example manifest matches the required field set.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def schema(manifest_schema_path: Path) -> dict:
    return json.loads(manifest_schema_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pr_plan_schema(pr_plan_schema_path: Path) -> dict:
    return json.loads(pr_plan_schema_path.read_text(encoding="utf-8"))


@pytest.fixture
def example_manifest() -> dict:
    """An example manifest that should match the schema."""
    return {
        "slug": "feature-name",
        "spec_path": ".cheese/specs/feature-name.md",
        "created": "2026-05-14T10:00:00Z",
        "phase": "gate_approved",
        "quality_gates": ["just check"],
        "host_capabilities": {
            "pr_stack": True,
            "melt": True,
            "commit": True,
            "gh": True,
        },
        "agent_resolution": {
            "request": {
                "work": "test",
                "preferred_types": ["planner"],
                "required_tools": ["read"],
                "permissions": "read-only",
                "isolation": "fresh-context",
                "minimum_power": "powerful",
                "effort": "high",
            },
            "attempts": [{"type": "planner", "model": "test", "power": "powerful", "result": "accepted", "reason": "exact"}],
            "resolved": {"type": "planner", "model": "test", "power": "powerful", "effort": "high", "topology": "sequential"},
            "fallback_reason": None,
            "degraded": False,
            "permission_enforcement": "tool-restricted",
        },
        "seed": {
            "items": [
                {
                    "description": "Add shared OrderId type",
                    "files": ["src/common/types.ts"],
                    "commit_sha": "abc123",
                    "status": "completed",
                }
            ]
        },
        "curds": [
            {
                "id": 1,
                "behavior": "Implement order entity",
                "acceptance_criterion": "Spec §3.1",
                "files": ["src/orders/order.ts", "src/orders/order.test.ts"],
                "test_target": "vitest run src/orders/order.test.ts",
                "status": "completed",
                "worktree_path": "/path",
                "branch": "ultracook/slug/curd-1",
                "commit_sha": "def456",
                "retry_count": 0,
                "error": None,
                "review_context": {
                    "base_commit": "a" * 40,
                    "reviewed_tree_oid": "b" * 40,
                    "diff_hash": "sha256:" + "c" * 64,
                    "scope": ["src/orders/order.ts", "src/orders/order.test.ts"],
                },
            }
        ],
        "wiring": [
            {
                "id": "W1",
                "type": "barrel_export",
                "file": "src/orders/index.ts",
                "depends_on": [],
                "status": "completed",
                "commit_sha": "ghi789",
            }
        ],
        "post_review": {
            "press_slug": ".cheese/press/feature-name.md",
            "age_slug": ".cheese/age/feature-name.md",
            "cure_slug": ".cheese/cure/feature-name.md",
            "findings_applied": 3,
            "findings_deferred": 0,
            "review_context": {
                "base_commit": "a" * 40,
                "reviewed_tree_oid": "d" * 40,
                "diff_hash": "sha256:" + "e" * 64,
                "scope": ["src/orders"],
            },
        },
        "pr_plan": {
            "shape": "diamond_stack",
            "groups": [
                {
                    "branch": "ultracook/slug/pr-1-seed",
                    "title": "feat(orders): shared types",
                    "body": "Adds shared types.",
                    "base": "main",
                    "commits": ["abc123"],
                    "depends_on": [],
                    "pr_number": 101,
                    "pr_url": "https://github.com/owner/repo/pull/101",
                }
            ],
        },
        "phase_summary": "Seed complete; curds next.",
        "carry_forward": ["slug", "spec_summary", "manifest_path", "quality_gates"],
    }


class TestSchemaShape:
    def test_schema_parses(self, schema: dict) -> None:
        assert isinstance(schema, dict)
        assert schema.get("type") == "object"

    def test_required_top_level_keys(self, schema: dict) -> None:
        # These keys MUST be required so resume / phase routing work.
        required = set(schema.get("required", []))
        for key in (
            "slug",
            "spec_path",
            "created",
            "phase",
            "quality_gates",
            "host_capabilities",
            "agent_resolution",
            "seed",
            "curds",
            "wiring",
        ):
            assert key in required, f"top-level required key missing: {key}"

    def test_phase_enum_covers_eight_phases(self, schema: dict) -> None:
        phases = schema["properties"]["phase"]["enum"]
        # Phase 0..7 each get a terminal "complete" marker, except the first
        # is "gate_approved" because the user gate is what marks Phase 0 done.
        expected = {
            "gate_approved",
            "seed_complete",
            "curds_complete",
            "merge_complete",
            "wiring_complete",
            "final_merge_complete",
            "post_review_complete",
            "pr_publish_complete",
        }
        assert set(phases) == expected

    def test_pr_plan_is_external_ref(self, schema: dict) -> None:
        # The pr_plan shape is defined in its own schema file so editors and
        # other consumers can target it directly. Manifest just $refs it.
        assert schema["properties"]["pr_plan"] == {"$ref": "pr-plan-schema.json"}

    def test_pr_plan_shape_enum_covers_four(self, pr_plan_schema: dict) -> None:
        shapes = pr_plan_schema["properties"]["shape"]["enum"]
        assert set(shapes) == {
            "single",
            "orthogonal_flat",
            "stacked_linear",
            "diamond_stack",
        }

    def test_review_context_records_reproducible_identity(self, schema: dict) -> None:
        review = schema["$defs"]["review_context"]
        assert set(review["required"]) == {
            "base_commit",
            "reviewed_tree_oid",
            "diff_hash",
            "scope",
        }
        assert "tree object" in review["properties"]["reviewed_tree_oid"]["description"].lower()
        assert "commit sha" not in review["properties"]["reviewed_tree_oid"]["description"].lower()
        assert schema["properties"]["current_review"] == {"$ref": "#/$defs/review_context"}
        assert schema["properties"]["curds"]["items"]["properties"]["review_context"] == {
            "$ref": "#/$defs/review_context"
        }

        for field in ("base_commit", "reviewed_tree_oid"):
            pattern = review["properties"][field]["pattern"]
            assert "A-F" in pattern
            oid_pattern = re.compile(pattern)
            assert oid_pattern.fullmatch("a" * 40)
            assert oid_pattern.fullmatch("B" * 64)
            assert oid_pattern.fullmatch("c" * 41) is None
        resolution = schema["$defs"]["agent_resolution"]
        assert resolution["properties"]["request"]["properties"]["required_tools"]["minItems"] == 1
        assert set(resolution["properties"]["attempts"]["items"]["required"]) == {
            "type", "model", "power", "result", "reason"
        }
        assert "allOf" in schema
        assert "allOf" in schema["properties"]["curds"]["items"]


class TestExampleManifestMatchesSchema:
    """Validate the example shape against the schema's required field lists.

    We don't bring in jsonschema (would expand the dep surface beyond
    pyyaml + pytest per python.instructions.md). Instead, walk each required
    field on each shape and assert it's present in the example.
    """

    def test_top_level_required_present(self, schema: dict, example_manifest: dict) -> None:
        for key in schema.get("required", []):
            assert key in example_manifest, f"example missing top-level required key: {key}"

    def test_curd_required_fields_present(self, schema: dict, example_manifest: dict) -> None:
        curd_required = schema["properties"]["curds"]["items"]["required"]
        for curd in example_manifest["curds"]:
            for key in curd_required:
                assert key in curd, f"curd missing required field: {key}"

    def test_wiring_required_fields_present(self, schema: dict, example_manifest: dict) -> None:
        wiring_required = schema["properties"]["wiring"]["items"]["required"]
        for wiring in example_manifest["wiring"]:
            for key in wiring_required:
                assert key in wiring, f"wiring missing required field: {key}"

    def test_seed_item_required_fields_present(self, schema: dict, example_manifest: dict) -> None:
        seed_required = schema["properties"]["seed"]["properties"]["items"]["items"]["required"]
        for item in example_manifest["seed"]["items"]:
            for key in seed_required:
                assert key in item, f"seed item missing required field: {key}"

    def test_phase_value_in_enum(self, schema: dict, example_manifest: dict) -> None:
        phases = schema["properties"]["phase"]["enum"]
        assert example_manifest["phase"] in phases

    def test_pr_plan_shape_value_in_enum(self, pr_plan_schema: dict, example_manifest: dict) -> None:
        shapes = pr_plan_schema["properties"]["shape"]["enum"]
        assert example_manifest["pr_plan"]["shape"] in shapes
