import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_claude_plugin_manifest_matches_top_level_skills() -> None:
    manifest_path = REPO_ROOT / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    expected = sorted(
        f"./skills/{path.parent.name}"
        for path in (REPO_ROOT / "skills").glob("*/SKILL.md")
    )

    assert manifest["name"] == "easy-cheese"
    assert sorted(manifest["skills"]) == expected
