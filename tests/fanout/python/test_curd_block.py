"""Tests for src/fanout/curd_block.py — the spec-locked curd-block schema
(slug/contract/files/test_target/acceptance/seed + waves + decomposer).

Distinct from tests/fanout/python/test_validate_decomposition.py, which
exercises src/fanout/curd.py's run-manifest entity (id/behavior/
acceptance_criterion/status/retry_count). curd_block.py is not yet registered
in ultracook.pyz's SKILLS map, so this suite imports it directly from
src/fanout/, matching the test_baseline.py precedent.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "shared" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "src" / "fanout"))

import curd_block  # noqa: E402


def _curd(slug: str, files: list[str], est_edit_lines: int = curd_block.MIN_CURD_SURFACE) -> dict:
    return {
        "slug": slug,
        "contract": f"Implement {slug}.",
        "files": files,
        "test_target": f"pytest tests/test_{slug}.py",
        "acceptance": [f"{slug} behaves correctly"],
        "seed": [],
        "est_edit_lines": est_edit_lines,
    }


def _block(curds: list[dict], waves: list[list[str]]) -> dict:
    return {
        "curds": curds,
        "waves": waves,
        "decomposer": {"source": "cook", "model": "claude-sonnet-5", "prompt_version": "abc123"},
    }


class TestWellFormed:
    def test_accepts_well_formed_block(self) -> None:
        block = _block(
            curds=[_curd("add-widget", ["src/widget.py"]), _curd("add-gadget", ["src/gadget.py"])],
            waves=[["add-widget", "add-gadget"]],
        )
        assert curd_block.validate_curd_block(block) == []

    def test_parse_curd_block_returns_the_block(self) -> None:
        block = _block(curds=[_curd("solo", ["src/solo.py"])], waves=[["solo"]])
        assert curd_block.parse_curd_block(block) == block

    def test_parse_curd_block_accepts_yaml_string(self) -> None:
        yaml_text = """
curds:
  - slug: solo
    contract: Implement solo.
    files: [src/solo.py]
    test_target: pytest tests/test_solo.py
    acceptance: ["solo behaves correctly"]
    seed: []
    est_edit_lines: 25
waves:
  - [solo]
decomposer: {source: mold, model: claude-opus-5, prompt_version: deadbeef}
"""
        result = curd_block.parse_curd_block(yaml_text)
        assert result["curds"][0]["slug"] == "solo"


class TestDisjointness:
    def test_rejects_file_in_two_curds(self) -> None:
        block = _block(
            curds=[_curd("add-widget", ["src/shared.py"]), _curd("add-gadget", ["src/shared.py"])],
            waves=[["add-widget", "add-gadget"]],
        )
        errors = curd_block.validate_curd_block(block)
        assert any(
            "src/shared.py" in e and "add-widget" in e and "add-gadget" in e for e in errors
        ), errors

    def test_parse_curd_block_raises_on_collision(self) -> None:
        block = _block(
            curds=[_curd("add-widget", ["src/shared.py"]), _curd("add-gadget", ["src/shared.py"])],
            waves=[["add-widget", "add-gadget"]],
        )
        with pytest.raises(curd_block.CurdBlockError, match="src/shared.py"):
            curd_block.parse_curd_block(block)


class TestWaves:
    def test_rejects_wave_over_max_size(self) -> None:
        curds = [_curd(f"c{i}", [f"src/c{i}.py"]) for i in range(5)]
        block = _block(curds=curds, waves=[[c["slug"] for c in curds]])
        errors = curd_block.validate_curd_block(block)
        assert any("waves[1]" in e and "4" in e for e in errors), errors

    def test_rejects_unknown_slug_in_wave(self) -> None:
        block = _block(curds=[_curd("known", ["src/known.py"])], waves=[["known", "ghost"]])
        errors = curd_block.validate_curd_block(block)
        assert any("ghost" in e for e in errors), errors


class TestRequiredFields:
    @pytest.mark.parametrize(
        "missing", ["slug", "contract", "files", "test_target", "acceptance", "seed", "est_edit_lines"]
    )
    def test_curd_missing_required_field(self, missing: str) -> None:
        curd = _curd("solo", ["src/solo.py"])
        del curd[missing]
        block = _block(curds=[curd], waves=[["solo"]])
        errors = curd_block.validate_curd_block(block)
        assert f"curds[1].{missing} is required" in errors, errors

    def test_missing_curds_waves_decomposer_top_level(self) -> None:
        errors = curd_block.validate_curd_block({})
        assert any("curds" in e for e in errors)
        assert any("waves" in e for e in errors)
        assert any("decomposer" in e for e in errors)


class TestMalformedShapes:
    """Wrong-type inputs at each nesting level — the required-key tests above
    only ever delete a key, never swap in the wrong type. Each of these
    exercises a distinct isinstance() branch in curd_block.py that would
    otherwise raise (AttributeError/TypeError) instead of returning a
    normal validation error."""

    def test_block_not_a_mapping(self) -> None:
        assert curd_block.validate_curd_block(["not", "a", "mapping"]) == [
            "curd block must be a mapping"
        ]

    def test_curds_not_a_list(self) -> None:
        block = _block(curds=[], waves=[])
        block["curds"] = "oops"
        errors = curd_block.validate_curd_block(block)
        assert "block.curds must be a list" in errors

    def test_curd_entry_not_a_mapping(self) -> None:
        block = _block(curds=["oops"], waves=[])
        errors = curd_block.validate_curd_block(block)
        assert any("curds[1] must be a mapping" in e for e in errors), errors

    def test_waves_not_a_list(self) -> None:
        block = _block(curds=[_curd("solo", ["src/solo.py"])], waves=[["solo"]])
        block["waves"] = "oops"
        errors = curd_block.validate_curd_block(block)
        assert "block.waves must be a list" in errors

    def test_wave_entry_not_a_list(self) -> None:
        block = _block(curds=[_curd("solo", ["src/solo.py"])], waves=["oops"])
        errors = curd_block.validate_curd_block(block)
        assert any("waves[1] must be a list of slugs" in e for e in errors), errors

    def test_decomposer_not_a_mapping(self) -> None:
        block = _block(curds=[_curd("solo", ["src/solo.py"])], waves=[["solo"]])
        block["decomposer"] = "oops"
        errors = curd_block.validate_curd_block(block)
        assert any("decomposer must be a mapping" in e for e in errors), errors

    def test_decomposer_source_outside_allowed_values(self) -> None:
        block = _block(curds=[_curd("solo", ["src/solo.py"])], waves=[["solo"]])
        block["decomposer"]["source"] = "human"
        errors = curd_block.validate_curd_block(block)
        assert any("decomposer.source must be one of" in e for e in errors), errors


def _curd_py_field_keys() -> set[str]:
    import ast

    src = (REPO_ROOT / "src" / "fanout" / "curd.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    keys: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "curd"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            keys.add(node.args[0].value)
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "curd"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            keys.add(node.slice.value)
    return keys


class TestNoCollisionWithCurdPy:
    def test_locked_field_names_do_not_match_curd_py_manifest_fields(self) -> None:
        """curd.py's manifest schema uses behavior/acceptance_criterion/status/
        retry_count; the spec-locked block uses contract/acceptance/seed —
        assert the two vocabularies stay disjoint so no field silently overloads
        the other module's meaning."""
        locked_fields = {"slug", "contract", "files", "test_target", "acceptance", "seed", "est_edit_lines"}
        # "files"/"test_target" are intentionally shared key names between the
        # two modules (both validate a files list / test_target string) -- not
        # a collision. Everything else curd.py touches must stay disjoint from
        # curd_block's own vocabulary (contract/acceptance/seed/slug).
        known_shared = {"files", "test_target"}
        curd_py_only_fields = _curd_py_field_keys() - known_shared
        assert locked_fields.isdisjoint(curd_py_only_fields)


class TestSurfaceFloor:
    """est_edit_lines gates dispatch worthiness: a curd below MIN_CURD_SURFACE
    is declared too small to justify a fresh coder dispatch and must merge into
    a sibling — the regression case is the real 8-curd block whose wave 2 held
    a curd editing three lines of a dict."""

    def test_curd_at_floor_passes(self) -> None:
        block = _block(
            curds=[_curd("solo", ["src/solo.py"], est_edit_lines=curd_block.MIN_CURD_SURFACE)],
            waves=[["solo"]],
        )
        assert curd_block.validate_curd_block(block) == []

    def test_curd_below_floor_fails_as_merge_candidate(self) -> None:
        block = _block(
            curds=[_curd("tiny", ["src/tiny.py"], est_edit_lines=curd_block.MIN_CURD_SURFACE - 1)],
            waves=[["tiny"]],
        )
        errors = curd_block.validate_curd_block(block)
        assert any("tiny" in e and "MERGE CANDIDATE" in e for e in errors), errors

    def test_non_int_est_edit_lines_fails(self) -> None:
        curd = _curd("solo", ["src/solo.py"])
        curd["est_edit_lines"] = "25"
        block = _block(curds=[curd], waves=[["solo"]])
        errors = curd_block.validate_curd_block(block)
        assert any("est_edit_lines must be a positive integer" in e for e in errors), errors

    def test_negative_est_edit_lines_fails(self) -> None:
        curd = _curd("solo", ["src/solo.py"])
        curd["est_edit_lines"] = -5
        block = _block(curds=[curd], waves=[["solo"]])
        errors = curd_block.validate_curd_block(block)
        assert any("est_edit_lines must be a positive integer" in e for e in errors), errors

    def test_eight_one_line_curds_produce_eight_floor_violations(self) -> None:
        curds = [_curd(f"c{i}", [f"src/c{i}.py"], est_edit_lines=1) for i in range(8)]
        waves = [[c["slug"] for c in curds[:4]], [c["slug"] for c in curds[4:]]]
        block = _block(curds=curds, waves=waves)
        errors = curd_block.validate_curd_block(block)
        floor_errors = [e for e in errors if "MERGE CANDIDATE" in e]
        assert len(floor_errors) == 8, errors
        for curd in curds:
            assert any(curd["slug"] in e for e in floor_errors), (curd["slug"], errors)