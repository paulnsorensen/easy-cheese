"""Focused Mold review model and transport contracts."""
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import http.client
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, redirect_stdout
from io import StringIO
import subprocess
from collections.abc import Callable, Generator, Iterator
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from easy_cheese.skills.mold.review import MoldReview, ReviewRevision, state_transaction

TAILNET_HOST = "node.tailnet.ts.net"


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


def test_close_cli_stops_running_review_server(
    tmp_path: Path, skill_archive: Callable[[str], Path]
) -> None:
    path = skill_archive("mold")
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



def test_serve_persists_initial_review_and_returns_tokenized_url(
    tmp_path: Path, skill_archive: Callable[[str], Path]
) -> None:
    archive = skill_archive("mold")
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


@contextmanager
def _running_server(
    archive: Path, state_dir: Path, *flags: str
) -> Generator[tuple[dict[str, str], int], None, None]:
    """Run ``review serve`` until the block exits, then close and reap it."""
    process = subprocess.Popen(
        ["python3", str(archive), "review", "serve", "--state-dir", str(state_dir), "--port", "0", *flags],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        launch: dict[str, str] = json.loads(process.stdout.readline())
        port = urlsplit(launch["url"]).port
        assert port is not None
        yield launch, port
    finally:
        subprocess.run(
            ["python3", str(archive), "review", "close", "--state-dir", str(state_dir)],
            capture_output=True,
        )
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


@pytest.fixture
def tailnet_server(
    tmp_path: Path, skill_archive: Callable[[str], Path]
) -> Iterator[tuple[dict[str, str], int]]:
    archive = skill_archive("mold")
    document = tmp_path / "doc.json"
    document.write_text(json.dumps({"questions": []}), encoding="utf-8")
    subprocess.run(
        ["python3", str(archive), "review", "publish", "--state-dir", str(tmp_path), "--input", str(document)],
        check=True,
        capture_output=True,
    )
    with _running_server(archive, tmp_path, "--trusted-host", TAILNET_HOST) as running:
        yield running


def _request(
    port: int, method: str, path: str, headers: dict[str, str | None], body: object | None = None
) -> tuple[int, str, bytes]:
    """Send one request; a ``None`` header value drops that header."""
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        payload = None if body is None else json.dumps(body)
        sent = {key: value for key, value in headers.items() if value is not None}
        connection.request(method, path, body=payload, headers=sent)
        response = connection.getresponse()
        return response.status, response.getheader("Set-Cookie") or "", response.read()
    finally:
        connection.close()


def _serve_proxy_headers(token: str, host: str = TAILNET_HOST) -> dict[str, str | None]:
    """Headers that ``tailscale serve`` forwards: original Host plus X-Forwarded-Proto."""
    return {"Host": host, "X-Forwarded-Proto": "https", "X-Mold-Token": token}


def test_trusted_host_accepts_tailscale_serve_requests(
    tailnet_server: tuple[dict[str, str], int],
) -> None:
    launch, port = tailnet_server
    token = launch["token"]
    assert launch["remote_url"] == f"https://{TAILNET_HOST}/?token={token}"
    assert launch["tailscale_serve"] == f"tailscale serve --bg http://127.0.0.1:{port}"
    status, cookie, _ = _request(port, "GET", f"/?token={token}", _serve_proxy_headers(""))
    assert status == 200
    assert "; Secure" in cookie
    status, _, _ = _request(
        port, "GET", "/assets/index.html", _serve_proxy_headers("") | {"Sec-Fetch-Site": "same-origin"}
    )
    assert status == 200
    generation = 0
    for host in (TAILNET_HOST, f"{TAILNET_HOST}:8443"):
        headers = _serve_proxy_headers(token, host) | {
            "Origin": f"https://{host}",
            "Content-Type": "application/json",
        }
        body: dict[str, object] = {"revision": 1, "generation": generation, "feedback": {}}
        status, _, data = _request(port, "POST", "/api/autosave", headers, body)
        assert status == 200
        generation = int(json.loads(data)["generation"])


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"Host": "evil.tail0000.ts.net", "Origin": "https://evil.tail0000.ts.net"}, id="other-host"),
        pytest.param({"Origin": f"http://{TAILNET_HOST}"}, id="http-origin"),
        pytest.param({"Origin": "https://evil.example"}, id="hostile-origin"),
        pytest.param({"X-Forwarded-Proto": "http"}, id="plain-http-proxy"),
        pytest.param({"X-Forwarded-Proto": None}, id="no-forwarded-proto"),
        pytest.param({"Host": f"{TAILNET_HOST}:", "Origin": f"https://{TAILNET_HOST}:"}, id="empty-port"),
        pytest.param({"Host": f"{TAILNET_HOST}:²", "Origin": f"https://{TAILNET_HOST}:²"}, id="non-ascii-port"),
        pytest.param({"Tailscale-Funnel-Request": "?1"}, id="funnel"),
        pytest.param({"X-Mold-Token": "wrong"}, id="bad-token"),
    ],
)
def test_trusted_host_rejects_unsafe_requests(
    tailnet_server: tuple[dict[str, str], int], overrides: dict[str, str | None]
) -> None:
    launch, port = tailnet_server
    headers = _serve_proxy_headers(launch["token"]) | {
        "Origin": f"https://{TAILNET_HOST}",
        "Content-Type": "application/json",
    } | overrides
    status, _, _ = _request(port, "POST", "/api/autosave", headers, {"revision": 1, "generation": 0, "feedback": {}})
    assert status == 403


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"Tailscale-Funnel-Request": "?1"}, id="funnel"),
        pytest.param({"Host": "evil.example"}, id="rebound-host"),
    ],
)
def test_assets_reject_funnel_and_untrusted_hosts(
    tailnet_server: tuple[dict[str, str], int], overrides: dict[str, str | None]
) -> None:
    _, port = tailnet_server
    headers = _serve_proxy_headers("") | {"Sec-Fetch-Site": "same-origin"} | overrides
    status, _, _ = _request(port, "GET", "/assets/index.html", headers)
    assert status == 403


def test_loopback_rejects_tailnet_host_without_flag(
    tmp_path: Path, skill_archive: Callable[[str], Path]
) -> None:
    with _running_server(skill_archive("mold"), tmp_path) as (launch, port):
        assert "remote_url" not in launch
        status, _, _ = _request(port, "GET", "/api/review", _serve_proxy_headers(launch["token"]))
        assert status == 403
        loopback: dict[str, str | None] = {"Host": f"127.0.0.1:{port}"}
        status, cookie, _ = _request(port, "GET", f"/?token={launch['token']}", loopback)
        assert status == 200
        assert "Secure" not in cookie
        status, _, _ = _request(port, "GET", "/assets/index.html", loopback | {"Sec-Fetch-Site": "same-origin"})
        assert status == 200


@pytest.mark.parametrize("value", ["example.com", "node.ts.net.evil.com", "ts.net", "node.tailnet.ts.net:443", "Node..ts.net", "NODE.tailnet.ts.net"])
def test_serve_rejects_non_tailnet_trusted_host(
    tmp_path: Path, skill_archive: Callable[[str], Path], value: str
) -> None:
    archive = skill_archive("mold")
    result = subprocess.run(
        ["python3", str(archive), "review", "serve", "--state-dir", str(tmp_path), "--port", "0", "--trusted-host", value],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "trusted host" in result.stderr


def test_publish_creates_nested_state_directory(tmp_path: Path) -> None:
    from easy_cheese.skills.mold.review import publish_main

    input_path = tmp_path / "revision.json"
    input_path.write_text(json.dumps({"questions": []}), encoding="utf-8")
    state_dir = tmp_path / "nested" / "review-state"
    assert publish_main(["--state-dir", str(state_dir), "--input", str(input_path)]) == 0
    assert (state_dir / "review.json").is_file()

def test_poll_observes_submission_saved_after_poll_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from easy_cheese.skills.mold import review as review_module

    path = tmp_path / "review.json"
    review = MoldReview("r", "goal", state_path=path)
    review.publish({"question": "choose"}, None)
    review.save(path)
    output = StringIO()
    sleeps: list[float] = []

    class _Clock:
        """Poll clock that moves only when poll sleeps, so disk latency cannot expire it."""

        now: float = 0.0

        def monotonic(self) -> float:
            return self.now

        def sleep(self, seconds: float) -> None:
            if not sleeps:
                review.submit({"answer": "yes"}, 1, "op-late")
            sleeps.append(seconds)
            self.now += seconds

    monkeypatch.setattr(review_module, "time", _Clock())
    with redirect_stdout(output):
        result = review_module.poll_main(
            ["--state-dir", str(tmp_path), "--timeout", "1"]
        )
    assert result == 0
    assert len(sleeps) == 1
    assert json.loads(output.getvalue())["operation_id"] == "op-late"


def _publish_outputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], *documents: dict[str, object]
) -> list[dict[str, object]]:
    """Publish each document in order through the CLI and return each JSON output."""
    from easy_cheese.skills.mold.review import publish_main

    input_path = tmp_path / "revision.json"
    outputs: list[dict[str, object]] = []
    for document in documents:
        input_path.write_text(json.dumps(document), encoding="utf-8")
        state_dir = str(tmp_path / "state")
        assert publish_main(["--state-dir", state_dir, "--input", str(input_path)]) == 0
        outputs.append(json.loads(capsys.readouterr().out))
    return outputs


def _requirement(requirement_id: str, status: str = "settled") -> dict[str, object]:
    return {"id": requirement_id, "text": f"WHEN {requirement_id} applies THE SYSTEM SHALL act.", "status": status}


def test_publish_returns_empty_warnings_for_a_clean_document(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    legacy: dict[str, object] = {"questions": [{"id": "F-0", "prompt": "Legacy fork"}]}
    first: dict[str, object] = {
        "requirements": [_requirement("R-1", "draft") | {"fork_ids": ["F-1", "F-2"]}],
        "questions": [
            {"id": "F-1", "prompt": "Choose storage", "depends_on": []},
            {"id": "F-2", "prompt": "Choose migration", "depends_on": ["F-1"]},
        ],
    }
    second: dict[str, object] = {
        "requirements": [_requirement("R-1"), _requirement("R-2", "draft")],
        "settled_fork_ids": ["F-1"],
        "questions": [{"id": "F-2", "prompt": "Choose migration", "depends_on": ["F-1"]}],
    }

    outputs = _publish_outputs(tmp_path, capsys, legacy, first, second)

    assert [output["warnings"] for output in outputs] == [[], [], []]
    assert set(outputs[-1]) == {"number", "document", "digest", "parent", "warnings"}
    assert outputs[-1]["number"] == 3


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        pytest.param(
            {"questions": [{"id": "F-1", "depends_on": "F-0"}, {"depends_on": None}]},
            [
                "question F-1: depends_on is not a list of question IDs",
                "questions[1]: depends_on is not a list of question IDs",
            ],
            id="not-a-list",
        ),
        pytest.param(
            {"questions": [{"id": "F-1"}, {"id": "F-2", "depends_on": ["F-1", "", 7]}]},
            [
                "question F-2: depends_on[1] is not a non-empty string",
                "question F-2: depends_on[2] is not a non-empty string",
            ],
            id="bad-entry",
        ),
        pytest.param(
            {"settled_fork_ids": ["F-0"], "questions": [{"id": "F-1", "depends_on": ["F-0", "F-9"]}]},
            ["question F-1: depends_on names F-9, which is not an open question or in settled_fork_ids"],
            id="missing-reference",
        ),
        pytest.param(
            {"settled_fork_ids": "F-0", "questions": [{"id": "F-1", "depends_on": ["F-0"]}]},
            ["question F-1: depends_on names F-0, which is not an open question or in settled_fork_ids"],
            id="settled-not-a-list",
        ),
        pytest.param(
            {"settled_fork_ids": ["F-1"], "questions": [{"id": "F-1"}, {"id": "F-2", "depends_on": ["F-1"]}]},
            [
                "question F-2: depends_on names F-1, which is open and also in settled_fork_ids;"
                + " the question waits until F-1 leaves questions"
            ],
            id="open-and-settled",
        ),
        pytest.param(
            {"questions": [{"id": "F-1", "depends_on": ["F-2"]}, {"id": "F-2", "depends_on": ["F-1"]}]},
            [
                "depends_on cycle among open questions: the dependency graph has cycle"
                + " F-1 -> F-2 -> F-1; these questions wait forever"
            ],
            id="cycle",
        ),
        pytest.param(
            {"questions": [{"id": "F-3", "depends_on": ["F-3"]}]},
            [
                "depends_on cycle among open questions: the dependency graph has cycle"
                + " F-3 -> F-3; these questions wait forever"
            ],
            id="self-cycle",
        ),
    ],
)
def test_publish_warns_about_fork_dependency_problems_and_still_stores_the_document(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    document: dict[str, object],
    expected: list[str],
) -> None:
    [output] = _publish_outputs(tmp_path, capsys, document)

    assert output["warnings"] == expected
    assert MoldReview.load(tmp_path / "state" / "review.json").revisions[-1].document == document


def test_publish_warns_when_requirements_from_the_previous_revision_are_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first: dict[str, object] = {
        "questions": [],
        "requirements": [_requirement("R-1"), _requirement("R-2"), _requirement("R-3")],
    }
    changed_only: dict[str, object] = {"questions": [], "requirements": [_requirement("R-2", "draft")]}

    outputs = _publish_outputs(tmp_path, capsys, first, changed_only, changed_only)

    assert [output["warnings"] for output in outputs] == [
        [],
        ["requirements from revision 1 are missing: R-1, R-3; republish the full requirement list"],
        [],
    ]


def test_publish_warnings_follow_question_then_cycle_then_requirement_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first: dict[str, object] = {"questions": [], "requirements": [_requirement("R-1")]}
    broken: dict[str, object] = {
        "questions": [
            {"id": "F-1", "depends_on": ["F-2"]},
            {"id": "F-2", "depends_on": ["F-1", "F-9"]},
            {"id": "F-3", "depends_on": "F-1"},
        ],
    }

    outputs = _publish_outputs(tmp_path, capsys, first, broken)

    assert outputs[-1]["warnings"] == [
        "question F-2: depends_on names F-9, which is not an open question or in settled_fork_ids",
        "question F-3: depends_on is not a list of question IDs",
        "depends_on cycle among open questions: the dependency graph has cycle"
        + " F-1 -> F-2 -> F-1; these questions wait forever",
        "requirements from revision 1 are missing: R-1; republish the full requirement list",
    ]
