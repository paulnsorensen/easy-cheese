"""Focused Mold review model and transport contracts."""
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from io import StringIO
import threading
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from easy_cheese.skills.mold.review import MoldReview, ReviewRevision, state_transaction


def test_revision_is_immutable_and_digest_is_stable(tmp_path: Path) -> None:
    review = MoldReview("r", "goal")
    review.state_path = tmp_path / "review.json"
    revision = review.publish({"question": "choose"}, None)
    assert isinstance(revision, ReviewRevision)
    assert revision.number == 1
    review.publish({"question": "next"}, 1)
    assert review.revisions[0].digest == revision.digest
    with pytest.raises(ValueError, match="stale base"):
        review.publish({"question": "bad"}, 1)


def test_working_generation_and_idempotent_submit_persist(tmp_path: Path) -> None:
    path = tmp_path / "review.json"
    review = MoldReview("r", "goal", state_path=path)
    review.publish({"question": "choose"}, None)
    assert review.autosave({"answer": "yes"}, 1, 0) == 1
    with pytest.raises(ValueError, match="stale"):
        review.autosave({"answer": "no"}, 1, 0)
    first = review.submit({"answer": "yes"}, 1, "op-1")
    assert review.submit({"answer": "yes"}, 1, "op-1") == first
    with pytest.raises(ValueError, match="different"):
        review.submit({"answer": "no"}, 1, "op-1")
    restored = MoldReview.load(path)
    assert restored.submissions == [first]
    assert restored.cursor == 1


def test_poll_empty_output_is_json_null(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from easy_cheese.skills.mold.review import poll_main
    assert poll_main(["--state-dir", str(tmp_path), "--timeout", "0"]) == 0
    assert json.loads(capsys.readouterr().out) is None


def test_concurrent_saves_use_one_consistent_state_file(tmp_path: Path) -> None:
    path = tmp_path / "review.json"
    review = MoldReview("r", "goal", state_path=path)
    review.publish({"question": "choose"}, None)

    def save_once(_: int) -> None:
        review.save(path)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(save_once, range(32)))
    assert MoldReview.load(path).revisions == review.revisions


def test_publish_rejects_invalid_base_and_preserves_latest_revision(tmp_path: Path) -> None:
    review = MoldReview("r", "goal", state_path=tmp_path / "review.json")
    review.publish({"question": "choose"}, None)

    with pytest.raises(ValueError, match="stale base"):
        review.publish({"question": "changed"}, 0)

    review.publish({"question": "changed"}, None)

    assert review.revisions[-1].number == 2


def test_submit_rejects_unknown_revision_without_creating_submission(tmp_path: Path) -> None:
    review = MoldReview("r", "goal", state_path=tmp_path / "review.json")
    review.publish({"question": "choose"}, None)

    with pytest.raises(ValueError, match="revision"):
        review.submit({"answer": "yes"}, 99, "op-unknown")

    assert review.submissions == []


def test_concurrent_publish_and_autosave_preserve_both_updates(tmp_path: Path) -> None:
    path = tmp_path / "review.json"
    review = MoldReview("r", "goal", state_path=path)
    review.publish({"question": "choose"}, None)
    review.save(path)

    def autosave() -> None:
        with state_transaction(path):
            current = MoldReview.load(path)
            current.state_path = path
            current.autosave({"answer": "yes"}, 1, 0)

    def publish() -> None:
        with state_transaction(path):
            current = MoldReview.load(path)
            current.state_path = path
            current.publish({"question": "next"}, 1)
            current.save(path)

    def run_operation(operation: Callable[[], None]) -> None:
        operation()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run_operation, (autosave, publish)))

    restored = MoldReview.load(path)
    assert [item.number for item in restored.revisions] == [1, 2]
    assert restored.working[1] == {"answer": "yes"}


def test_close_cli_stops_running_review_server(tmp_path: Path) -> None:
    path = Path(__file__).resolve().parents[2] / "skills/mold/scripts/mold.pyz"
    process = subprocess.Popen(
        ["python3", str(path), "review", "serve", "--state-dir", str(tmp_path), "--port", "0"],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        launch = json.loads(process.stdout.readline())
        assert launch["url"].startswith("http://127.0.0.1:")
        result = subprocess.run(
            ["python3", str(path), "review", "close", "--state-dir", str(tmp_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        assert json.loads(result.stdout) == {"closed": True}
        assert process.wait(timeout=3) == 0
    finally:
        if process.poll() is None:
            process.kill()



def test_serve_persists_initial_review_and_returns_tokenized_url(tmp_path: Path) -> None:
    archive = Path(__file__).resolve().parents[2] / "skills/mold/scripts/mold.pyz"
    process = subprocess.Popen(
        ["python3", str(archive), "review", "serve", "--state-dir", str(tmp_path), "--port", "0"],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        launch = json.loads(process.stdout.readline())
        assert "?token=" in launch["url"]
        restored = MoldReview.load(tmp_path / "review.json")
        assert restored.review_id == launch["review_id"]
        subprocess.run(
            ["python3", str(archive), "review", "close", "--state-dir", str(tmp_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        assert process.wait(timeout=3) == 0
    finally:
        if process.poll() is None:
            process.kill()


def test_publish_creates_nested_state_directory(tmp_path: Path) -> None:
    from easy_cheese.skills.mold.review import publish_main

    input_path = tmp_path / "revision.json"
    input_path.write_text(json.dumps({"questions": []}), encoding="utf-8")
    state_dir = tmp_path / "nested" / "review-state"
    assert publish_main(["--state-dir", str(state_dir), "--input", str(input_path)]) == 0
    assert (state_dir / "review.json").is_file()

def test_poll_observes_submission_saved_after_poll_starts(tmp_path: Path) -> None:
    path = tmp_path / "review.json"
    review = MoldReview("r", "goal", state_path=path)
    review.publish({"question": "choose"}, None)
    review.save(path)
    output = StringIO()
    result: list[int] = []

    def poll() -> None:
        with redirect_stdout(output):
            from easy_cheese.skills.mold.review import poll_main
            result.append(poll_main(["--state-dir", str(tmp_path), "--timeout", "1"]))

    thread = threading.Thread(target=poll)
    thread.start()
    time.sleep(0.1)
    review.submit({"answer": "yes"}, 1, "op-late")
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert result == [0]
    assert json.loads(output.getvalue())["operation_id"] == "op-late"
