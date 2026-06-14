import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_plugin_json_skills_match_skills_directories() -> None:
    """plugin.json skills list must match the skills/ directory listing exactly.

    This catches two failure modes:
    - a skills/ dir that was added without a plugin.json entry (invisible to the harness)
    - a plugin.json entry whose skills/ dir was removed (broken reference)
    """
    manifest_path = REPO_ROOT / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    dirs_on_disk = sorted(
        f"./skills/{path.parent.name}"
        for path in (REPO_ROOT / "skills").glob("*/SKILL.md")
    )

    assert sorted(manifest["skills"]) == dirs_on_disk, (
        f"plugin.json skills entries do not match skills/ directories.\n"
        f"  In plugin.json but not on disk: {sorted(set(manifest['skills']) - set(dirs_on_disk))}\n"
        f"  On disk but not in plugin.json: {sorted(set(dirs_on_disk) - set(manifest['skills']))}"
    )
