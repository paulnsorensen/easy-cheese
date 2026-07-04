"""Tests for skills/cheese-factory/scripts/manifest_update.py."""

from __future__ import annotations

import multiprocessing
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

import build_pyz

BUNDLE = build_pyz.cached_bundle("cheese-factory")


def _curds(n: int = 5) -> list[dict]:
    return [
        {
            "id": i + 1,
            "behavior": f"Implement feature {i + 1}",
            "acceptance_criterion": f"AC {i + 1}",
            "files": [f"src/feature_{i}.ts"],
            "test_target": f"pytest src/feature_{i}.ts",
            "status": "pending",
            "retry_count": 0,
        }
        for i in range(n)
    ]


def _manifest() -> dict:
    return {
        "slug": "feature-name",
        "spec_path": ".cheese/specs/feature-name.md",
        "created": "2026-05-14T10:00:00Z",
        "phase": "gate_approved",
        "quality_gates": ["just check"],
        "host_capabilities": {"gh": True},
        "seed": {"items": []},
        "curds": _curds(),
        "wiring": [
            {
                "id": "W1",
                "type": "barrel_export",
                "file": "src/index.ts",
                "depends_on": [],
                "status": "pending",
            }
        ],
    }


def _write_fixture(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump(_manifest(), sort_keys=False), encoding="utf-8")
    return path


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BUNDLE), "manifest_update", *args],
        capture_output=True,
        text=True,
    )


def _validate(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BUNDLE), "validate_manifest", str(path)],
        capture_output=True,
        text=True,
    )


class TestSetPhase:
    def test_happy_path_updates_phase_and_validates(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path)
        result = _run_cli("set-phase", "--manifest", str(path), "--phase", "seed_complete")
        assert result.returncode == 0, result.stderr
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["phase"] == "seed_complete"
        # The rewritten file must still pass the schema validator.
        check = _validate(path)
        assert check.returncode == 0, check.stderr

    def test_invalid_phase_exits_2(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path)
        original = path.read_bytes()
        result = _run_cli("set-phase", "--manifest", str(path), "--phase", "bogus_phase")
        assert result.returncode == 2
        assert "invalid phase" in result.stderr
        # Original file untouched on validation gate failure.
        assert path.read_bytes() == original

    def test_missing_manifest_exits_2(self, tmp_path: Path) -> None:
        path = tmp_path / "does-not-exist.yaml"
        result = _run_cli("set-phase", "--manifest", str(path), "--phase", "seed_complete")
        assert result.returncode == 2
        assert "manifest not found" in result.stderr

    def test_preserves_top_level_field_order(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path)
        expected_keys = list(_manifest().keys())
        result = _run_cli("set-phase", "--manifest", str(path), "--phase", "seed_complete")
        assert result.returncode == 0, result.stderr
        rewritten = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert list(rewritten.keys()) == expected_keys


class TestSetCurdStatus:
    def test_updates_status_and_commit_sha(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path)
        result = _run_cli(
            "set-curd-status",
            "--manifest",
            str(path),
            "--curd",
            "3",
            "--status",
            "completed",
            "--commit-sha",
            "deadbeef",
        )
        assert result.returncode == 0, result.stderr
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        curd = next(c for c in data["curds"] if c["id"] == 3)
        assert curd["status"] == "completed"
        assert curd["commit_sha"] == "deadbeef"
        assert _validate(path).returncode == 0

    def test_other_curds_untouched(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path)
        _run_cli("set-curd-status", "--manifest", str(path), "--curd", "2", "--status", "running")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        other_statuses = [c["status"] for c in data["curds"] if c["id"] != 2]
        assert all(s == "pending" for s in other_statuses)

    def test_invalid_status_exits_2(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path)
        result = _run_cli(
            "set-curd-status", "--manifest", str(path), "--curd", "1", "--status", "ok"
        )
        assert result.returncode == 2
        assert "invalid status" in result.stderr

    def test_missing_curd_id_exits_2(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path)
        result = _run_cli(
            "set-curd-status", "--manifest", str(path), "--curd", "999", "--status", "running"
        )
        assert result.returncode == 2
        assert "curd id 999 not found" in result.stderr


class TestSetWiringStatus:
    def test_updates_status_and_commit_sha(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path)
        result = _run_cli(
            "set-wiring-status",
            "--manifest",
            str(path),
            "--wiring",
            "W1",
            "--status",
            "completed",
            "--commit-sha",
            "abc1234",
        )
        assert result.returncode == 0, result.stderr
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        wiring = data["wiring"][0]
        assert wiring["status"] == "completed"
        assert wiring["commit_sha"] == "abc1234"
        assert _validate(path).returncode == 0

    def test_missing_wiring_id_exits_2(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path)
        result = _run_cli(
            "set-wiring-status", "--manifest", str(path), "--wiring", "W99", "--status", "running"
        )
        assert result.returncode == 2
        assert "wiring id 'W99' not found" in result.stderr


class TestAtomicity:
    def test_no_tmp_file_left_after_success(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path)
        result = _run_cli("set-phase", "--manifest", str(path), "--phase", "seed_complete")
        assert result.returncode == 0, result.stderr
        leftover = list(tmp_path.glob("*.tmp"))
        assert leftover == []

    def test_failed_validation_restores_original_and_leaves_no_tmp(
        self, tmp_path: Path, manifest_update: ModuleType
    ) -> None:
        # Drive failure through the in-process API so we can poison the data
        # in a way that argparse-level guards can't catch but the validator does.
        path = _write_fixture(tmp_path)
        original = path.read_bytes()
        data, original_bytes = manifest_update._load_manifest(path)
        # quality_gates must be a non-empty list — clearing it breaks schema.
        data["quality_gates"] = []
        with pytest.raises(manifest_update.cli.CliError):
            manifest_update._commit(path, data, original_bytes)
        assert path.read_bytes() == original
        assert list(tmp_path.glob("*.tmp")) == []


class TestCheckFiles:
    def test_all_present_reports_clean(self, tmp_path: Path) -> None:
        manifest = _manifest()
        for curd in manifest["curds"]:
            for f in curd["files"]:
                target = tmp_path / f
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("", encoding="utf-8")
        path = tmp_path / "manifest.yaml"
        path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        result = _run_cli("check-files", "--manifest", str(path), "--root", str(tmp_path))
        assert result.returncode == 0, result.stderr
        assert "all curd files present" in result.stdout

    def test_missing_files_reported_per_curd_without_failing(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path)
        # Fixture files are never created on disk, so every curd is "missing".
        result = _run_cli("check-files", "--manifest", str(path), "--root", str(tmp_path))
        assert result.returncode == 0, result.stderr
        assert "curd 1" in result.stdout
        assert "src/feature_0.ts" in result.stdout

    def test_json_mode_reports_missing_per_curd_id(self, tmp_path: Path) -> None:
        manifest = _manifest()
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "feature_0.ts").write_text("", encoding="utf-8")
        path = tmp_path / "manifest.yaml"
        path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        result = _run_cli("check-files", "--manifest", str(path), "--root", str(tmp_path), "--json")
        assert result.returncode == 0, result.stderr
        report = __import__("json").loads(result.stdout)
        assert "1" not in report
        assert report["2"] == ["src/feature_1.ts"]

    def test_missing_manifest_exits_2(self, tmp_path: Path) -> None:
        path = tmp_path / "does-not-exist.yaml"
        result = _run_cli("check-files", "--manifest", str(path))
        assert result.returncode == 2
        assert "manifest not found" in result.stderr


def _worker(args: tuple[str, int]) -> tuple[int, str]:
    manifest_path, curd_id = args
    result = subprocess.run(
        [
            sys.executable,
            str(BUNDLE),
            "manifest_update",
            "set-curd-status",
            "--manifest",
            manifest_path,
            "--curd",
            str(curd_id),
            "--status",
            "running",
        ],
        capture_output=True,
        text=True,
    )
    return (result.returncode, result.stderr)


class TestConcurrentWrites:
    def test_parallel_updates_never_corrupt_file(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path)
        n_curds = len(_curds())
        jobs = [(str(path), i + 1) for i in range(n_curds)]
        # Repeat the volley to widen the race window.
        for _ in range(3):
            with multiprocessing.Pool(processes=min(4, n_curds)) as pool:
                results = pool.map(_worker, jobs)
            # The advisory lock serialises all writes — no update should be lost
            # and no writer should fail due to a race condition.
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            assert isinstance(data, dict)
            assert len(data["curds"]) == n_curds
            for rc, err in results:
                assert rc == 0, f"unexpected rc={rc} stderr={err!r}"
        # Final state still passes validation.
        assert _validate(path).returncode == 0

    def test_all_distinct_updates_survive(self, tmp_path: Path) -> None:
        """With N>=8 concurrent writers each targeting a DISTINCT curd id, every
        update must appear in the final manifest (no lost writes). This is the
        behavioral proof that the advisory lock wraps the full read-modify-write."""
        n = 10
        path = tmp_path / "manifest_big.yaml"
        manifest = _manifest()
        manifest["curds"] = [
            {
                "id": i + 1,
                "behavior": f"Feature {i + 1}",
                "acceptance_criterion": f"AC {i + 1}",
                "files": [f"src/f{i}.ts"],
                "test_target": f"pytest src/f{i}.ts",
                "status": "pending",
                "retry_count": 0,
            }
            for i in range(n)
        ]
        path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

        # All jobs target distinct curd ids with the same manifest file — genuine
        # concurrent contention with no serialisation at the test level.
        jobs = [(str(path), i + 1) for i in range(n)]
        with multiprocessing.Pool(processes=n) as pool:
            results = pool.map(_worker, jobs)

        # Every writer must have succeeded.
        for rc, err in results:
            assert rc == 0, f"rc={rc} stderr={err!r}"

        # Every curd's update must be present in the final manifest.
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert _validate(path).returncode == 0
        assert len(data["curds"]) == n
        for curd in data["curds"]:
            assert curd["status"] == "running", (
                f"curd {curd['id']} status={curd['status']!r} — update was lost"
            )
