"""Contract tests for the /age benchmark's seeded-defect case corpus.

Spec: age-fanout-mechanics-benchmark.md, AC-9, curd/2.
"""

import shutil
import subprocess
import tempfile
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import cast


REPO_ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = REPO_ROOT / "benchmark" / "age" / "cases"
AGE_BENCH_SRC = REPO_ROOT / "src" / "easy_cheese" / "skills" / "age_bench"


def _case_dirs() -> list[Path]:
    if not CASES_DIR.is_dir():
        return []
    return sorted(p for p in CASES_DIR.iterdir() if p.is_dir())


def _load_manifest(case_dir: Path) -> Mapping[str, object]:
    manifest_path = case_dir / "case.toml"
    with manifest_path.open("rb") as fh:
        return cast(Mapping[str, object], tomllib.load(fh))


def test_corpus_holds_five_to_fifteen_fully_described_cases():
    case_dirs = _case_dirs()
    assert 5 <= len(case_dirs) <= 15, (
        f"expected 5..15 cases, found {len(case_dirs)}: {[p.name for p in case_dirs]}"
    )

    for case_dir in case_dirs:
        manifest = _load_manifest(case_dir)

        overlap_area = manifest.get("overlap_area")
        assert isinstance(overlap_area, str) and overlap_area, (
            f"{case_dir.name}: overlap_area must be a non-empty string"
        )

        defect = manifest.get("defect")
        assert isinstance(defect, dict), f"{case_dir.name}: missing [defect] table"
        defect = cast(Mapping[str, object], defect)
        defect_file = defect.get("file")
        assert isinstance(defect_file, str) and defect_file, (
            f"{case_dir.name}: defect.file must be a non-empty string"
        )
        defect_line = defect.get("line")
        assert isinstance(defect_line, int) and defect_line > 0, (
            f"{case_dir.name}: defect.line must be a positive int"
        )
        assert (case_dir / "base" / defect_file).is_file(), (
            f"{case_dir.name}: defect.file {defect_file!r} not found under base/"
        )

        description = manifest.get("description")
        assert isinstance(description, str) and description, (
            f"{case_dir.name}: description must be a non-empty string"
        )
        assert "\n" not in description, f"{case_dir.name}: description must be one line"


def test_every_seed_patch_applies_to_its_base():
    case_dirs = _case_dirs()
    assert case_dirs, "no cases found under benchmark/age/cases"

    for case_dir in case_dirs:
        manifest = _load_manifest(case_dir)
        defect = cast(Mapping[str, object], manifest["defect"])
        defect_file = defect["file"]
        patch_path = case_dir / "seed.patch"
        patch_text = patch_path.read_text()

        touched = {
            line.split("\t")[0].strip()
            for line in patch_text.splitlines()
            if line.startswith("+++ b/")
        }
        touched = {t[len("+++ b/"):] for t in touched}
        assert defect_file in touched, (
            f"{case_dir.name}: seed.patch does not touch declared defect.file {defect_file!r}"
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _ = shutil.copytree(case_dir / "base", tmp_path, dirs_exist_ok=True)
            result = subprocess.run(
                ["git", "apply", "--check", str(patch_path.resolve())],
                cwd=tmp_path,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, (
                f"{case_dir.name}: seed.patch failed to apply to base/: {result.stderr}"
            )


def test_each_overlap_area_appears_at_most_once():
    case_dirs = _case_dirs()
    assert case_dirs, "no cases found under benchmark/age/cases"

    areas = [_load_manifest(case_dir)["overlap_area"] for case_dir in case_dirs]
    duplicates = {area for area in areas if areas.count(area) > 1}
    assert not duplicates, f"overlap area(s) claimed by more than one case: {duplicates}"


def test_every_manifest_parses_with_tomllib():
    case_dirs = _case_dirs()
    assert case_dirs, "no cases found under benchmark/age/cases"

    for case_dir in case_dirs:
        manifest = _load_manifest(case_dir)
        assert isinstance(manifest, dict)

    if AGE_BENCH_SRC.is_dir():
        offenders = [
            path
            for path in AGE_BENCH_SRC.rglob("*.py")
            if any(
                line.strip().startswith("import yaml")
                or line.strip().startswith("from yaml")
                for line in path.read_text().splitlines()
            )
        ]
        assert not offenders, f"yaml import found under age_bench: {offenders}"
