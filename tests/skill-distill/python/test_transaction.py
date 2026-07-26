import stat

import pytest

from skill_distill.transaction import apply_family


def test_family_apply_is_atomic_and_rolls_back_every_member_on_gate_failure(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_text("old-a")
    b.write_text("old-b")
    a.chmod(0o640)
    b.chmod(0o751)
    with pytest.raises(RuntimeError, match="family gate failed"):
        apply_family("f", {a: b"new-a", b: b"new-b"}, lambda: False)
    assert a.read_text() == "old-a"
    assert b.read_text() == "old-b"
    assert stat.S_IMODE(a.stat().st_mode) == 0o640
    assert stat.S_IMODE(b.stat().st_mode) == 0o751


def test_family_apply_commits_all_members_together(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_text("old-a")
    b.write_text("old-b")
    a.chmod(0o640)
    b.chmod(0o751)
    result = apply_family("f", {b: b"new-b", a: b"new-a"}, lambda: True)
    assert result.applied_paths == (a, b)
    assert (a.read_text(), b.read_text()) == ("new-a", "new-b")
    assert stat.S_IMODE(a.stat().st_mode) == 0o640
    assert stat.S_IMODE(b.stat().st_mode) == 0o751


def test_family_apply_removes_new_members_when_gate_raises(tmp_path):
    existing = tmp_path / "existing"
    created = tmp_path / "created"
    existing.write_text("old")
    existing.chmod(0o640)

    def fail():
        raise RuntimeError("gate crashed")

    with pytest.raises(RuntimeError, match="gate crashed"):
        apply_family("f", {existing: b"new", created: b"created"}, fail)

    assert existing.read_text() == "old"
    assert stat.S_IMODE(existing.stat().st_mode) == 0o640
    assert not created.exists()
