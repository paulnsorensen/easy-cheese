import json
import re
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


def test_install_sh_fallback_matches_top_level_skills() -> None:
    install_sh = (REPO_ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
    match = re.search(r'^EC_FALLBACK_SKILLS="([^"]+)"', install_sh, re.MULTILINE)
    assert match, "EC_FALLBACK_SKILLS assignment not found in scripts/install.sh"

    expected = sorted(
        f"./skills/{path.parent.name}"
        for path in (REPO_ROOT / "skills").glob("*/SKILL.md")
    )
    fallback = sorted(f"./skills/{name}" for name in match.group(1).split())

    assert fallback == expected
