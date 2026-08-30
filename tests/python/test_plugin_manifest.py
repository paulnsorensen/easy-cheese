import json
import os
import re
import shlex
import subprocess
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


def test_cut_is_not_listed_in_plugin_manifest() -> None:
    manifest = json.loads(
        (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert "./skills/cut" not in manifest["skills"]


def test_installer_fallback_installs_press_from_unrelated_cwd(tmp_path: Path) -> None:
    log = tmp_path / "gh.log"
    gh = tmp_path / "gh"
    gh.write_text(
        '#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$STUB_LOG"\n',
        encoding="utf-8",
    )
    gh.chmod(0o755)

    env = os.environ.copy()
    env.update({"EC_GH": str(gh), "STUB_LOG": str(log)})
    result = subprocess.run(
        [
            "bash",
            "-c",
            f"source {shlex.quote(str(REPO_ROOT / 'scripts' / 'install.sh'))}; ec_install_skills claude-code",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    installs = [
        line
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.startswith("skill install ")
    ]
    assert any(" press " in f" {line} " and "--force" in line for line in installs)
