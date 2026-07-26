from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from skill_distill.model_lock import snapshot_digest
from skill_distill.tokens import (
    build_tokenizer_identity,
    loaded_tokens,
    measure_load_events,
    token_savings,
)


REVISION = "a" * 40
RUNTIME = "tokenizers==1.0"


class Words:
    def __init__(self) -> None:
        self.calls = 0

    def encode(self, text, *, add_special_tokens):
        self.calls += 1
        assert add_special_tokens is False
        return text.split()


def tokenizer_snapshot(tmp_path: Path) -> tuple[Path, str]:
    snapshot = tmp_path / "tokenizer"
    snapshot.mkdir()
    (snapshot / "tokenizer.json").write_text("{}")
    return snapshot, snapshot_digest(snapshot)


def test_load_events_are_encoded_independently_and_repeated_loads_repeat_cost(
    tmp_path: Path,
):
    snapshot, digest = tokenizer_snapshot(tmp_path)
    identity = build_tokenizer_identity("example/tokenizer", REVISION, digest, RUNTIME)
    encoder = Words()
    loads = [
        ("skill", "a.md", b"one two"),
        ("reference", "r.md", b"three"),
        ("reference", "r.md", b"three"),
    ]

    profile = measure_load_events(
        identity, loads, encoder, snapshot=snapshot, runtime=RUNTIME
    )

    assert [event.token_count for event in profile.load_events] == [2, 1, 1]
    assert loaded_tokens(profile) == 4
    variant = measure_load_events(
        identity,
        [("skill", "a.md", "one")],
        encoder,
        snapshot=snapshot,
        runtime=RUNTIME,
    )
    assert token_savings(profile, variant) == 3


def test_tokenizer_identity_is_stable_and_does_not_include_load_events():
    digest = sha256(b"tokenizer").hexdigest()
    first = build_tokenizer_identity("example/tokenizer", REVISION, digest, RUNTIME)
    second = build_tokenizer_identity("example/tokenizer", REVISION, digest, RUNTIME)
    assert first.identity_digest == second.identity_digest


@pytest.mark.parametrize(
    ("revision", "digest", "runtime", "message"),
    [
        ("main", "b" * 64, RUNTIME, "full 40-character"),
        (REVISION, "not-a-digest", RUNTIME, "tokenizer_hash"),
        (REVISION, "b" * 64, "tokenizers", "exact name/version"),
    ],
)
def test_tokenizer_identity_rejects_mutable_or_incomplete_locks(
    revision: str, digest: str, runtime: str, message: str
):
    with pytest.raises(ValueError, match=message):
        build_tokenizer_identity("example/tokenizer", revision, digest, runtime)


def test_snapshot_drift_fails_before_encoder_call(tmp_path: Path):
    snapshot, digest = tokenizer_snapshot(tmp_path)
    identity = build_tokenizer_identity("example/tokenizer", REVISION, digest, RUNTIME)
    (snapshot / "tokenizer.json").write_text('{"drifted": true}')
    encoder = Words()

    with pytest.raises(ValueError, match="drifted artifacts"):
        measure_load_events(
            identity,
            [("skill", "a.md", "must not encode")],
            encoder,
            snapshot=snapshot,
            runtime=RUNTIME,
        )

    assert encoder.calls == 0


def test_runtime_drift_fails_before_encoder_call(tmp_path: Path):
    snapshot, digest = tokenizer_snapshot(tmp_path)
    identity = build_tokenizer_identity("example/tokenizer", REVISION, digest, RUNTIME)
    encoder = Words()

    with pytest.raises(ValueError, match="runtime identity drift"):
        measure_load_events(
            identity,
            [("skill", "a.md", "must not encode")],
            encoder,
            snapshot=snapshot,
            runtime="tokenizers==2.0",
        )

    assert encoder.calls == 0