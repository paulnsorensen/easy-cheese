from __future__ import annotations

import pytest

from easy_cheese.shared.bundle_commands import (
    bundle_command,
    compile_bundle_commands,
    guidance_source,
    validate_generated_region,
)
from easy_cheese.skills.cook import commands as cook_commands
from easy_cheese.skills.mold import commands as mold_commands
from scripts import build_pyz


def test_duplicate_or_unreferenced_commands_reject():
    with pytest.raises(ValueError, match="unreferenced"):
        compile_bundle_commands(mold_commands.__name__, referenced={"contract"})

    @bundle_command("one")
    def one():
        return None

    with pytest.raises(ValueError, match="duplicate"):
        bundle_command("one")(lambda: None)


def test_compiled_command_maps_are_complete():
    assert set(build_pyz._compile_layout_commands("mold")) == {
        "artifact-path",
        "contract",
        "curd-count",
        "gate-graph",
        "render_html",
        "taste-test",
        "validate-spec",
    }
    assert set(build_pyz._compile_layout_commands("cook")) == {
        "artifact-path",
        "contract",
        "findings_cli",
        "gates_cli",
        "handoff_cli",
        "normalize",
        "paths_cli",
        "read_handoff_slug",
        "render_html",
        "slugify",
        "validate",
        "worktree",
        "write_handoff_artifact",
    }


def test_generated_region_drift_rejects():
    guidance = guidance_source(mold_commands.__name__)
    validate_generated_region(guidance, mold_commands.__name__)
    with pytest.raises(ValueError, match="drift"):
        validate_generated_region(guidance.replace("contract", "missing", 1), mold_commands.__name__)


def test_own_archive_dispatch_runtime_and_ast_compilers_agree():
    assert build_pyz._compile_layout_commands("cook") == compile_bundle_commands(
        cook_commands.__name__
    )
