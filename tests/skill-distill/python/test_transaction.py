import stat

import pytest

import skill_distill.transaction as transaction
from skill_distill.transaction import apply_family


def test_family_apply_is_atomic_and_rolls_back_every_member_on_write_failure(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_text("old-a")
    b.write_text("old-b")
    a.chmod(0o640)
    b.chmod(0o751)
    original_replace = transaction._replace

    def fake_replace(path, content, mode=None):
        if path == b and content == b"new-b":
            raise OSError("disk full")
        original_replace(path, content, mode)

    monkeypatch.setattr(transaction, "_replace", fake_replace)
    with pytest.raises(OSError, match="disk full"):
        apply_family("f", {a: b"new-a", b: b"new-b"})
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
    result = apply_family("f", {b: b"new-b", a: b"new-a"})
    assert result.applied_paths == (a, b)
    assert (a.read_text(), b.read_text()) == ("new-a", "new-b")
    assert stat.S_IMODE(a.stat().st_mode) == 0o640
    assert stat.S_IMODE(b.stat().st_mode) == 0o751


def test_family_apply_removes_new_members_when_write_raises(tmp_path, monkeypatch):
    existing = tmp_path / "existing"
    created = tmp_path / "created"
    existing.write_text("old")
    existing.chmod(0o640)
    original_replace = transaction._replace

    def fake_replace(path, content, mode=None):
        if path == existing:
            raise RuntimeError("write crashed")
        original_replace(path, content, mode)

    monkeypatch.setattr(transaction, "_replace", fake_replace)
    with pytest.raises(RuntimeError, match="write crashed"):
        apply_family("f", {existing: b"new", created: b"created"})

    assert existing.read_text() == "old"
    assert stat.S_IMODE(existing.stat().st_mode) == 0o640
    assert not created.exists()


def test_family_apply_continues_restoring_remaining_members_when_one_restore_raises(tmp_path, monkeypatch):
    a, b, c = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    a.write_text("old-a")
    b.write_text("old-b")
    c.write_text("old-c")
    original_replace = transaction._replace

    def fake_replace(path, content, mode=None):
        if path == b and content == b"new-b":
            raise OSError("disk full")
        if path == a and content == b"old-a":
            raise OSError("restore failed for a")
        original_replace(path, content, mode)

    monkeypatch.setattr(transaction, "_replace", fake_replace)
    with pytest.raises(OSError, match="disk full") as error:
        apply_family("f", {a: b"new-a", b: b"new-b", c: b"new-c"})

    assert "restore failed for a" not in str(error.value)
    assert str(a) in "".join(error.value.__notes__)
    # a's restore raised, so it keeps the applied write; b and c were still restored.
    assert a.read_text() == "new-a"
    assert b.read_text() == "old-b"
    assert c.read_text() == "old-c"
