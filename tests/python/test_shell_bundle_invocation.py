"""Run the published installed-bundle example under Bash and zsh."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[2] / "skills/age/references/installed-bundle-invocation.md"


def _function_source() -> str:
    text = DOC.read_text(encoding="utf-8")
    snippet = text.split("```bash\n", 1)[1].split("\n```", 1)[0]
    return snippet.split('\nrun_age_bundle "$HOST"', 1)[0]


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_installed_bundle_invocation_preserves_arguments(tmp_path: Path, shell: str) -> None:
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is unavailable")
    skill_dir = tmp_path / "installed skills" / "age"
    archive = skill_dir / "scripts" / "age.pyz"
    archive.parent.mkdir(parents=True)
    _ = archive.write_text("import json, sys\nprint(json.dumps(sys.argv[1:]))\n", encoding="utf-8")
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    gh = stub_dir / "gh"
    _ = gh.write_text("#!/bin/sh\nprintf '%s\\n' \"$AGE_SKILL_PATH\"\n", encoding="utf-8")
    gh.chmod(0o755)
    environment = dict(os.environ, PATH=f"{stub_dir}:{os.environ['PATH']}", AGE_SKILL_PATH=str(skill_dir))
    command = _function_source() + '\nrun_age_bundle codex severity compute --dimension security --base low --location module --fix-cost-later contained\n'
    result = subprocess.run([executable, "-fc" if shell == "zsh" else "-c", command], env=environment, cwd=tmp_path, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [
        "severity", "compute", "--dimension", "security", "--base", "low",
        "--location", "module", "--fix-cost-later", "contained",
    ]


@pytest.mark.parametrize("skill_path", ["", "/one\n/two", "/missing"])
def test_installed_bundle_invocation_rejects_bad_resolution(tmp_path: Path, skill_path: str) -> None:
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    gh = stub_dir / "gh"
    _ = gh.write_text("#!/bin/sh\nprintf '%s\\n' \"$AGE_SKILL_PATH\"\n", encoding="utf-8")
    gh.chmod(0o755)
    environment = dict(os.environ, PATH=f"{stub_dir}:{os.environ['PATH']}", AGE_SKILL_PATH=skill_path)
    result = subprocess.run(["bash", "-c", _function_source() + "\nrun_age_bundle codex severity compute"], env=environment, cwd=tmp_path, capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert result.stdout == ""
