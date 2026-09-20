"""Private, submit-driven local review canvas for Mold."""
# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false, reportUnannotatedClassAttribute=false, reportDeprecated=false

from __future__ import annotations

import argparse
from collections.abc import Generator
from contextlib import contextmanager, nullcontext
import hashlib
import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Union, cast
from typing_extensions import TypeAlias, override
from urllib.parse import parse_qs, quote, urlparse

from easy_cheese.shared.advisory_lock import advisory_lock
from easy_cheese.shared.publication import atomic_write

JSONValue: TypeAlias = Union[
    str, int, float, bool, None, list["JSONValue"], dict[str, "JSONValue"]
]
JSONObject = dict[str, JSONValue]

MAX_BODY = 1_048_576
ASSET_ROOT = Path(__file__).with_name("assets")
ASSET_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css",
    ".js": "text/javascript",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


@contextmanager
def state_transaction(path: Path) -> Generator[None, None, None]:
    lock_path = path.with_name(f".{path.name}.lock")
    with advisory_lock(lock_path):
        yield


def _state_signature(path: Path) -> tuple[int, int] | None:
    try:
        metadata = path.stat()
    except FileNotFoundError:
        return None
    return metadata.st_mtime_ns, metadata.st_size


@dataclass(frozen=True)
class ReviewRevision:
    number: int
    document: JSONObject
    digest: str
    parent: int | None = None


@dataclass
class MoldReview:
    review_id: str
    goal: str
    revisions: list[ReviewRevision] = field(default_factory=list)
    working: dict[int, JSONObject] = field(default_factory=dict)
    generation: dict[int, int] = field(default_factory=dict)
    submissions: list[JSONObject] = field(default_factory=list)
    operations: dict[str, str] = field(default_factory=dict)
    cursor: int = 0
    closed: bool = False
    state_path: Path | None = None
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    @classmethod
    def load(cls, path: Path) -> MoldReview:
        if not path.exists():
            return cls(secrets.token_urlsafe(12), "")
        raw = json.loads(path.read_text(encoding="utf-8"))
        revisions = [ReviewRevision(**item) for item in raw.get("revisions", [])]
        working = {int(key): value for key, value in raw.get("working", {}).items()}
        generation = {int(key): value for key, value in raw.get("generation", {}).items()}
        return cls(
            raw["review_id"],
            raw.get("goal", ""),
            revisions,
            working,
            generation,
            raw.get("submissions", []),
            raw.get("operations", {}),
            raw.get("cursor", 0),
            raw.get("closed", False),
        )

    def _payload(self) -> JSONObject:
        return cast(JSONObject, {
            "review_id": self.review_id,
            "goal": self.goal,
            "revisions": [revision.__dict__ for revision in self.revisions],
            "working": {str(key): value for key, value in self.working.items()},
            "generation": {str(key): value for key, value in self.generation.items()},
            "submissions": self.submissions,
            "operations": self.operations,
            "cursor": self.cursor,
            "closed": self.closed,
        })

    def save(self, path: Path) -> None:
        with self._lock:
            atomic_write(
                path,
                json.dumps(self._payload(), sort_keys=True).encode("utf-8"),
            )

    def publish(self, document: JSONObject, base: int | None) -> ReviewRevision:
        with self._lock:
            current = self.revisions[-1].number if self.revisions else 0
            if base is not None and base != current:
                raise ValueError("stale base revision")
            blob = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
            revision = ReviewRevision(
                current + 1,
                document,
                hashlib.sha256(blob).hexdigest(),
                current or None,
            )
            self.revisions.append(revision)
            self.generation.setdefault(revision.number, 0)
            return revision


    def autosave(self, payload: JSONObject, revision: int, generation: int) -> int:
        with self._lock:
            known_revision = any(item.number == revision for item in self.revisions)
            if not known_revision or generation != self.generation.get(revision, 0):
                raise ValueError("stale working copy")
            self.working[revision] = payload
            self.generation[revision] = generation + 1
            self.save_state()
            return generation + 1

    def submit(self, payload: JSONObject, revision: int, operation_id: str) -> JSONObject:
        with self._lock:
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            prior = self.operations.get(operation_id)
            if prior is not None:
                if prior != encoded:
                    raise ValueError("operation ID reused with different content")
                return next(
                    item for item in self.submissions if item["operation_id"] == operation_id
                )
            if not self.revisions or revision != self.revisions[-1].number:
                raise ValueError("stale source revision")
            self.cursor += 1
            result = cast(JSONObject, {
                "submission_id": secrets.token_urlsafe(12),
                "operation_id": operation_id,
                "revision": revision,
                "feedback": payload,
                "cursor": len(self.submissions) + 1,
            })
            self.operations[operation_id] = encoded
            self.submissions.append(result)
            self.working.pop(revision, None)
            self.save_state()
            return result

    def save_state(self) -> None:
        if self.state_path is not None:
            self.save(self.state_path)


class _ReviewServer(ThreadingHTTPServer):
    review: MoldReview = cast(MoldReview, object())
    token: str = ""
    state_signature: tuple[int, int] | None = None

    def __init__(self, address: tuple[str, int], handler: type[BaseHTTPRequestHandler]) -> None:
        super().__init__(address, handler)
        self.state_lock: threading.RLock = threading.RLock()

class _Handler(BaseHTTPRequestHandler):
    @override
    def log_message(self, format: str, *args: object) -> None:
        """Do not log request paths because launch tokens can appear in URLs."""
        return

    def _review(self) -> MoldReview:
        server = cast(_ReviewServer, self.server)
        with server.state_lock:
            review = server.review
            if (
                review.state_path is not None
                and _state_signature(review.state_path) != server.state_signature
            ):
                with state_transaction(review.state_path):
                    refreshed = MoldReview.load(review.state_path)
                refreshed.state_path = review.state_path
                server.review = refreshed
                server.state_signature = _state_signature(review.state_path)
            return server.review

    def _send(
        self,
        status: int,
        body: object,
        content_type: str = "application/json",
        cookie: str | None = None,
    ) -> None:
        data = body if isinstance(body, bytes) else json.dumps(body, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self, require_origin: bool = False) -> bool:
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        token = self.headers.get("X-Mold-Token")
        request = urlparse(self.path)
        if not token and request.path in ("/", "/index.html"):
            token = parse_qs(request.query).get("token", [""])[0]
        if not token:
            token = next(
                (
                    part[11:]
                    for part in self.headers.get("Cookie", "").split("; ")
                    if part.startswith("mold_token=")
                ),
                "",
            )
        server = cast(_ReviewServer, self.server)
        loopback = host == f"127.0.0.1:{server.server_port}"
        same_origin = origin == f"http://{host}" if require_origin else origin in (None, "null", f"http://{host}")
        return loopback and same_origin and secrets.compare_digest(token, server.token)

    def _asset_is_authorized(self, path: str) -> bool:
        if not path.startswith("/assets/"):
            return False
        if self.headers.get("Sec-Fetch-Site") == "same-origin":
            return True
        query_token = parse_qs(urlparse(self.path).query).get("token", [""])[0]
        referer_token = parse_qs(
            urlparse(self.headers.get("Referer", "")).query
        ).get("token", [""])[0]
        return secrets.compare_digest(
            query_token or referer_token, cast(_ReviewServer, self.server).token
        )

    @override
    def do_GET(self) -> None:  # pyright: ignore[reportGeneralTypeIssues]
        path = urlparse(self.path).path
        authorized = self._authorized() or self._asset_is_authorized(path)
        if not authorized:
            self._send(403, {"error": "forbidden"})
            return
        if path in ("/", "/index.html"):
            self._serve_index()
            return
        if path == "/api/review":
            self._serve_review()
            return
        if path.startswith("/assets/"):
            self._serve_asset(path)
            return
        self._send(404, {"error": "not found"})

    def _serve_index(self) -> None:
        index = ASSET_ROOT / "index.html"
        if not index.is_file():
            self._send(404, {"error": "review asset missing"})
            return
        token = cast(_ReviewServer, self.server).token
        self._send(
            200,
            index.read_bytes(),
            "text/html; charset=utf-8",
            f"mold_token={token}; Path=/; HttpOnly; SameSite=Strict",
        )

    def _serve_review(self) -> None:
        review = self._review()
        revision = review.revisions[-1].__dict__ if review.revisions else None
        self._send(
            200,
            {
                "review_id": review.review_id,
                "goal": review.goal,
                "revision": revision,
                "working": review.working,
                "generation": review.generation,
                "closed": review.closed,
            },
        )

    def _serve_asset(self, path: str) -> None:
        relative = path.removeprefix("/assets/")
        asset = (ASSET_ROOT / relative).resolve()
        if not asset.is_relative_to(ASSET_ROOT.resolve()) or not asset.is_file():
            self._send(404, {"error": "asset not found"})
            return
        content_type = ASSET_TYPES.get(asset.suffix)
        if content_type is None:
            self._send(415, {"error": "asset type not allowed"})
            return
        self._send(200, asset.read_bytes(), content_type)

    def _read_payload(self) -> JSONObject | None:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            self._send(400, {"error": "missing Content-Length"})
            return None
        try:
            length = int(raw_length)
        except ValueError:
            self._send(400, {"error": "invalid Content-Length"})
            return None
        if length < 0:
            self._send(400, {"error": "invalid Content-Length"})
            return None
        if length > MAX_BODY:
            _ = self.rfile.read(length)
            self._send(413, {"error": "body too large"})
            return None
        try:
            payload = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._send(400, {"error": "invalid JSON"})
            return None
        if not isinstance(payload, dict):
            self._send(400, {"error": "JSON body must be an object"})
            return None
        return cast(JSONObject, payload)

    @override
    def do_POST(self) -> None:  # pyright: ignore[reportGeneralTypeIssues]
        if not self._authorized(require_origin=True):
            self._send(403, {"error": "forbidden"})
            return
        if self.headers.get("Content-Type") != "application/json":
            self._send(415, {"error": "Content-Type must be application/json"})
            return
        payload = self._read_payload()
        if payload is None:
            return
        server = cast(_ReviewServer, self.server)
        with server.state_lock:
            state_path = server.review.state_path
            transaction = state_transaction(state_path) if state_path else nullcontext()
            with transaction:
                review = MoldReview.load(state_path) if state_path else server.review
                review.state_path = state_path
                server.review = review
                request_path = urlparse(self.path).path
                try:
                    if request_path == "/api/autosave":
                        result = self._autosave(review, payload)
                    elif request_path == "/api/submit":
                        result = self._submit(review, payload)
                    elif request_path == "/api/close":
                        result = self._close(review)
                    else:
                        self._send(404, {"error": "not found"})
                        return
                except (KeyError, TypeError, ValueError) as exc:
                    self._send(409, {"error": str(exc)})
                    return
                if request_path == "/api/close":
                    review.save_state()
                server.state_signature = _state_signature(state_path) if state_path else None
                self._send(200, result)

    @staticmethod
    def _autosave(review: MoldReview, payload: JSONObject) -> dict[str, int]:
        feedback = payload["feedback"]
        revision = int(cast(int, payload["revision"]))
        generation = int(cast(int, payload["generation"]))
        if not isinstance(feedback, dict):
            raise TypeError("feedback must be an object")
        return {"generation": review.autosave(cast(JSONObject, feedback), revision, generation)}

    @staticmethod
    def _submit(review: MoldReview, payload: JSONObject) -> JSONObject:
        feedback = payload["feedback"]
        if not isinstance(feedback, dict):
            raise TypeError("feedback must be an object")
        return review.submit(
            cast(JSONObject, feedback),
            int(cast(int, payload["revision"])),
            str(cast(str, payload["operation_id"])),
        )

    def _close(self, review: MoldReview) -> dict[str, bool]:
        review.closed = True
        return {"closed": True}


def serve_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="review serve")
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args(argv)
    state = args.state_dir
    state.mkdir(parents=True, exist_ok=True)
    path = state / "review.json"
    with state_transaction(path):
        review = MoldReview.load(path)
        review.state_path = path
        if not path.exists() or review.closed:
            review.closed = False
            review.save(path)
    token = secrets.token_urlsafe(32)
    server = _ReviewServer(("127.0.0.1", args.port), _Handler)
    server.review = review
    server.token = token
    server.state_signature = _state_signature(path)
    print(
        json.dumps(
            {
                "url": f"http://127.0.0.1:{server.server_port}/?token={quote(token, safe='')}",
                "token": token,
                "review_id": review.review_id,
            }
        ),
        flush=True,
    )
    server.timeout = 0.2
    try:
        while True:
            server.handle_request()
            with server.state_lock:
                if server.review.closed:
                    break
                signature = _state_signature(path)
                if signature != server.state_signature:
                    with state_transaction(path):
                        refreshed = MoldReview.load(path)
                    refreshed.state_path = path
                    server.review = refreshed
                    server.state_signature = _state_signature(path)
                if server.review.closed:
                    break
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


def _args(argv: list[str], command: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=f"review {command}")
    parser.add_argument("--state-dir", type=Path, required=True)
    return parser.parse_args(argv)


def publish_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--base-revision", type=int, default=None)
    args = parser.parse_args(argv)
    args.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = args.state_dir / "review.json"
    try:
        with state_transaction(path):
            review = MoldReview.load(path)
            document = json.loads(args.input.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                raise TypeError("input JSON must be an object")
            revision = review.publish(cast(JSONObject, document), args.base_revision)
            review.save(path)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    print(json.dumps(revision.__dict__, sort_keys=True))
    return 0


def poll_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--after", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=0)
    args = parser.parse_args(argv)
    path = args.state_dir / "review.json"
    deadline = time.monotonic() + args.timeout
    while True:
        with state_transaction(path):
            review = MoldReview.load(path)
        if len(review.submissions) > args.after:
            print(json.dumps(review.submissions[args.after], sort_keys=True))
            return 0
        if time.monotonic() >= deadline:
            print("null")
            return 0
        time.sleep(0.05)


def close_main(argv: list[str]) -> int:
    args = _args(argv, "close")
    path = args.state_dir / "review.json"
    with state_transaction(path):
        review = MoldReview.load(path)
        review.closed = True
        review.save(path)
    print(json.dumps({"closed": True}))
    return 0