"""Canonical JSON bytes and the SHA-256 digests taken over them.

Every integrity claim in the Wheypoint runtime -- a record digest, a receipt
digest, a request fingerprint -- is a hash of *these* bytes, so the encoding
has to be a function of the value and nothing else:

* keys sorted, no insertion-order or dict-rehash dependence;
* the tightest separators, so whitespace cannot drift between writers;
* UTF-8 rather than escaped ASCII, so the file reads as the text it holds;
* non-finite floats refused, because `NaN` and `Infinity` are not JSON and a
  reader that accepts them agrees to a value that never equals itself.

A value that cannot be encoded is refused with the path that broke it, since a
digest over a silently coerced payload is worse than no digest at all.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import cast

DIGEST_PREFIX = "sha256:"


class CanonicalJsonError(ValueError):
    """Raised when a value has no canonical JSON encoding."""


def _check(value: object, path: str) -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalJsonError(f"{path} must be a finite number, not {value!r}")
        return
    if isinstance(value, dict):
        mapping = cast("dict[object, object]", value)
        for key, item in mapping.items():
            if not isinstance(key, str):
                raise CanonicalJsonError(
                    f"{path} keys must be strings, not {type(key).__name__}"
                )
            _check(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        sequence = cast("list[object] | tuple[object, ...]", value)
        for index, item in enumerate(sequence):
            _check(item, f"{path}[{index}]")
        return
    raise CanonicalJsonError(f"{path} is not JSON data: {type(value).__name__}")


def canonical_bytes(value: object) -> bytes:
    """The one encoding of `value` every digest in the runtime is taken over."""
    _check(value, "value")
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def digest_bytes(payload: bytes) -> str:
    """`sha256:<hex>` over raw bytes -- file contents as well as encoded values."""
    return f"{DIGEST_PREFIX}{hashlib.sha256(payload).hexdigest()}"


def digest_text(text: str) -> str:
    return digest_bytes(text.encode("utf-8"))


def digest_value(value: object) -> str:
    return digest_bytes(canonical_bytes(value))