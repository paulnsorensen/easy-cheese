import json
import sys
from pathlib import Path
from typing import cast


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def test_claude_plugin_manifest_matches_top_level_skills() -> None:
    manifest_path = REPO_ROOT / ".claude-plugin" / "plugin.json"
    manifest = cast(
        dict[str, object], json.loads(manifest_path.read_text(encoding="utf-8"))
    )

    expected = sorted(
        f"./skills/{path.parent.name}"
        for path in (REPO_ROOT / "skills").glob("*/SKILL.md")
    )

    assert manifest["name"] == "easy-cheese"
    assert sorted(cast(list[str], manifest["skills"])) == expected


def test_cut_is_not_listed_in_plugin_manifest() -> None:
    manifest = cast(
        dict[str, object],
        json.loads(
            (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        ),
    )
    assert "./skills/cut" not in cast(list[str], manifest["skills"])

