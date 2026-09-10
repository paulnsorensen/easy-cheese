"""End-to-end coverage for cook.pyz's `accept` contract command.

Each test publishes a real HandoffPointer through mold.pyz's `publish`, then
feeds that pointer (optionally tampered) into an isolated cook.pyz `accept`
subprocess, proving Cook executes only from a validated canonical pointer.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402

pytestmark = pytest.mark.skipif(  # noqa: V107
    importlib.util.find_spec("build") is None
    or importlib.util.find_spec("pip") is None
    or (shutil.which("shiv") is None and importlib.util.find_spec("shiv") is None),
    reason="bundle integration requires requirements-build.txt",
)

DOC_PAYLOAD: dict[str, object] = {
    "objective": "Ship the approved behavior",
    "curds": [
        {
            "key": "runtime",
            "outcome": "Implement strict validation",
            "scope": {"paths": ["src/runtime.py"]},
            "outputs": ["Validated contract"],
            "criteria": [
                {
                    "description": "Unknown fields reject",
                    "check": "uv run pytest tests/test_runtime.py",
                }
            ],
        }
    ],
}

DOC = {"kind": "curd_plan", "payload": DOC_PAYLOAD}

TWO_CURD_DOC_PAYLOAD: dict[str, object] = {
    "objective": "Ship the approved behavior",
    "curds": [
        {
            "key": "c1",
            "outcome": "Implement the first curd",
            "scope": {"paths": ["src/c1.py"]},
            "outputs": ["c1 landed"],
            "dependencies": ["c2"],
            "criteria": [
                {
                    "description": "c1 behaves",
                    "check": "uv run pytest tests/test_c1.py",
                }
            ],
        },
        {
            "key": "c2",
            "outcome": "Implement the second curd",
            "scope": {"paths": ["src/c2.py"]},
            "outputs": ["c2 landed"],
            "criteria": [
                {
                    "description": "c2 behaves",
                    "check": "uv run pytest tests/test_c2.py",
                }
            ],
        },
    ],
}

TWO_CURD_DOC = {"kind": "curd_plan", "payload": TWO_CURD_DOC_PAYLOAD}

MINI_SPEC_FIXTURE = (
    REPO_ROOT / "tests/python/fixtures/spec_format/valid_red_required_mini_spec.md"
)


def _spec_with_landing(tmp_path: Path, landing_block: str) -> Path:
    text = MINI_SPEC_FIXTURE.read_text(encoding="utf-8")
    text = text.replace(
        "gate_applicability:",
        f"{landing_block}\ngate_applicability:",
    )
    spec_path = tmp_path / "spec.md"
    _ = spec_path.write_text(text, encoding="utf-8")
    return spec_path


CURD_PLAN_SCHEMA_URI = "https://schemas.easy-cheese.dev/curd-plan"

INVOCATION = {
    "plan_id": "curdplan-cook-accept-1",
    "contract_version": {
        "schema_uri": CURD_PLAN_SCHEMA_URI,
        "major": "1",
        "minor": "0",
    },
}


def _run(pyz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # Run from the bundle's own dir with PYTHONPATH stripped, so the only way
    # an import can resolve is from inside the .pyz itself.
    env = dict(os.environ)
    _ = env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, str(pyz), *args],
        cwd=str(pyz.parent),
        capture_output=True,
        text=True,
        env=env,
    )


def _publish(
    tmp_path: Path,
    operation_id: str,
    *,
    doc: object = DOC,
    raw_text: str | None = None,
) -> tuple[Path, dict[str, object]]:
    mold_pyz = build_pyz.cached_bundle("mold")
    document = tmp_path / f"{operation_id}-document.json"
    _ = document.write_text(
        raw_text if raw_text is not None else json.dumps(doc), encoding="utf-8"
    )
    invocation = tmp_path / f"{operation_id}-invocation.json"
    _ = invocation.write_text(json.dumps(INVOCATION), encoding="utf-8")
    artifact_root = tmp_path / "artifacts"
    result = _run(
        mold_pyz,
        "publish",
        str(document),
        "--invocation",
        str(invocation),
        "--operation-id",
        operation_id,
        "--artifact-root",
        str(artifact_root),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    pointer_path = artifact_root / "pointers" / f"{operation_id}.json"
    pointer = cast(dict[str, object], json.loads(pointer_path.read_text(encoding="utf-8")))
    return pointer_path, pointer


def _accept(pointer_path: Path) -> subprocess.CompletedProcess[str]:
    cook_pyz = build_pyz.cached_bundle("cook")
    return _run(cook_pyz, "accept", str(pointer_path))


def _accept_with_spec(pointer_path: Path, spec_path: Path) -> subprocess.CompletedProcess[str]:
    cook_pyz = build_pyz.cached_bundle("cook")
    return _run(cook_pyz, "accept", str(pointer_path), "--spec", str(spec_path))


def _assert_canonical_wrapper(stdout: str) -> dict[str, object]:
    """Assert the complete accepted wrapper, not just one field.

    A partial assertion passes after Cook drops the objective, the curds, the
    derived identifiers, or the digest, so every field is checked here.
    """
    wrapper = cast(dict[str, object], json.loads(stdout))
    assert sorted(wrapper) == ["digest", "normalization_receipt", "value"]
    value = cast(dict[str, object], wrapper["value"])
    assert value["plan_id"] == INVOCATION["plan_id"]
    assert value["objective"] == DOC_PAYLOAD["objective"]
    assert value["revision"] == 1
    assert value["contract_version"] == INVOCATION["contract_version"]
    curds = cast(list[dict[str, object]], value["curds"])
    assert [curd["curd_id"] for curd in curds] == ["curdplan-cook-accept-1/curd/1"]
    assert curds[0]["outcome"] == "Implement strict validation"
    criteria = cast(list[dict[str, object]], curds[0]["criteria"])
    assert [criterion["criterion_id"] for criterion in criteria] == [
        "curdplan-cook-accept-1/curd/1/criterion/1"
    ]
    digest = cast(str, wrapper["digest"])
    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64
    assert digest != value["digest"]
    return wrapper


def test_cook_pyz_accepts_a_real_mold_pointer(tmp_path: Path) -> None:
    pointer_path, pointer = _publish(tmp_path, "op-happy")
    result = _accept(pointer_path)
    assert result.returncode == 0, result.stdout + result.stderr
    wrapper = _assert_canonical_wrapper(result.stdout)
    assert wrapper["normalization_receipt"] is None
    assert pointer["destination_phase"] == "cook"


def test_cook_pyz_accepts_a_receipt_bearing_pointer(tmp_path: Path) -> None:
    raw_text = json.dumps(DOC)[:-1] + ",}"
    pointer_path, pointer = _publish(tmp_path, "op-receipt", raw_text=raw_text)
    assert pointer["normalization_receipt"] is not None
    result = _accept(pointer_path)
    assert result.returncode == 0, result.stdout + result.stderr
    wrapper = _assert_canonical_wrapper(result.stdout)
    receipt = cast(dict[str, object], wrapper["normalization_receipt"])
    assert receipt["uri"] == cast(dict[str, object], pointer["normalization_receipt"])["uri"]


def test_cook_pyz_rejects_tampered_payload(tmp_path: Path) -> None:
    """A same-size edit must still fail on the digest, not on the size."""
    pointer_path, pointer = _publish(tmp_path, "op-tampered-payload")
    payload = cast(dict[str, object], pointer["payload"])
    payload_path = Path(cast(str, payload["uri"]).removeprefix("file://"))
    original = payload_path.read_bytes()
    tampered = original.replace(b"Ship the approved", b"Sank the approved")
    assert len(tampered) == len(original)
    assert tampered != original
    _ = payload_path.write_bytes(tampered)
    result = _accept(pointer_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "digest mismatch" in result.stderr
    assert "size mismatch" not in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_rejects_wrong_route(tmp_path: Path) -> None:
    pointer_path, pointer = _publish(tmp_path, "op-wrong-route")
    pointer["source_phase"] = "press"
    _ = pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    result = _accept(pointer_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "press -> cook is not declared" in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_rejects_missing_receipt_file(tmp_path: Path) -> None:
    raw_text = json.dumps(DOC)[:-1] + ",}"
    pointer_path, pointer = _publish(tmp_path, "op-missing-receipt", raw_text=raw_text)
    receipt = cast(dict[str, object], pointer["normalization_receipt"])
    receipt_path = Path(cast(str, receipt["uri"]).removeprefix("file://"))
    receipt_path.unlink()
    result = _accept(pointer_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "artifact is not readable" in result.stderr
    assert str(receipt_path) in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_rejects_receipt_digest_mismatch(tmp_path: Path) -> None:
    raw_text = json.dumps(DOC)[:-1] + ",}"
    pointer_path, pointer = _publish(tmp_path, "op-receipt-mismatch", raw_text=raw_text)
    receipt = cast(dict[str, object], pointer["normalization_receipt"])
    receipt["digest"] = f"sha256:{'0' * 64}"
    _ = pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    result = _accept(pointer_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "digest mismatch" in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_rejects_receipt_canonical_digest_mismatch(tmp_path: Path) -> None:
    raw_text = json.dumps(DOC)[:-1] + ",}"
    pointer_path, pointer = _publish(
        tmp_path, "op-receipt-canonical-mismatch", raw_text=raw_text
    )
    receipt_ref = cast(dict[str, object], pointer["normalization_receipt"])
    receipt_path = Path(cast(str, receipt_ref["uri"]).removeprefix("file://"))
    receipt_body = cast(
        dict[str, object], json.loads(receipt_path.read_text(encoding="utf-8"))
    )
    receipt_body["canonical_digest"] = f"sha256:{'0' * 64}"
    tampered_bytes = json.dumps(receipt_body).encode("utf-8")
    _ = receipt_path.write_text(json.dumps(receipt_body), encoding="utf-8")
    receipt_ref["digest"] = f"sha256:{hashlib.sha256(tampered_bytes).hexdigest()}"
    receipt_ref["size_bytes"] = len(tampered_bytes)
    _ = pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    result = _accept(pointer_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "does not match the canonical payload" in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_rejects_bare_payload(tmp_path: Path) -> None:
    cook_pyz = build_pyz.cached_bundle("cook")
    bare_payload = tmp_path / "bare-payload.json"
    _ = bare_payload.write_text(json.dumps(DOC), encoding="utf-8")
    result = _run(cook_pyz, "accept", str(bare_payload))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "$.contract_version is required" in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_rejects_missing_payload_file(tmp_path: Path) -> None:
    pointer_path, pointer = _publish(tmp_path, "op-missing-payload")
    payload = cast(dict[str, object], pointer["payload"])
    payload_path = Path(cast(str, payload["uri"]).removeprefix("file://"))
    payload_path.unlink()
    result = _accept(pointer_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "artifact is not readable" in result.stderr
    assert str(payload_path) in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_rejects_unsafe_artifact_uri(tmp_path: Path) -> None:
    pointer_path, pointer = _publish(tmp_path, "op-unsafe-uri")
    payload = cast(dict[str, object], pointer["payload"])
    payload["uri"] = "https://example.com/payload.json"
    _ = pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    result = _accept(pointer_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr.startswith("ERROR:")
    assert "is not a file:// uri" in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_rejects_missing_pointer_file(tmp_path: Path) -> None:
    missing_pointer = tmp_path / "does-not-exist.json"
    result = _accept(missing_pointer)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "pointer not found at" in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_accepts_bare_relative_pointer_from_pointers_dir(
    tmp_path: Path,
) -> None:
    pointer_path, pointer = _publish(tmp_path, "op-relative")
    cook_pyz = build_pyz.cached_bundle("cook")
    env = dict(os.environ)
    _ = env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, str(cook_pyz), "accept", pointer_path.name],
        cwd=str(pointer_path.parent),
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wrapper = cast(dict[str, object], json.loads(result.stdout))
    value = cast(dict[str, object], wrapper["value"])
    assert value["plan_id"] == INVOCATION["plan_id"]
    assert pointer["destination_phase"] == "cook"


def test_cook_pyz_refuses_a_plan_that_crosses_landing_layers(tmp_path: Path) -> None:
    pointer_path, _pointer = _publish(tmp_path, "op-landing-refused", doc=TWO_CURD_DOC)
    spec_path = _spec_with_landing(
        tmp_path,
        "landing:\n  shape: stacked_linear\n"
        + '  layers: [["curdplan-cook-accept-1/curd/1"], ["curdplan-cook-accept-1/curd/2"]]',
    )
    result = _accept_with_spec(pointer_path, spec_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (
        "landing-layer-order curd 'curdplan-cook-accept-1/curd/1' in layer 1 "
        "depends on 'curdplan-cook-accept-1/curd/2' in layer 2"
    ) in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""


def test_cook_pyz_accepts_a_plan_that_matches_landing_layers(tmp_path: Path) -> None:
    pointer_path, _pointer = _publish(tmp_path, "op-landing-matches", doc=TWO_CURD_DOC)
    spec_path = _spec_with_landing(
        tmp_path,
        "landing:\n  shape: stacked_linear\n"
        + '  layers: [["curdplan-cook-accept-1/curd/2"], ["curdplan-cook-accept-1/curd/1"]]',
    )
    result = _accept_with_spec(pointer_path, spec_path)
    assert result.returncode == 0, result.stdout + result.stderr
    wrapper = cast(dict[str, object], json.loads(result.stdout))
    assert sorted(wrapper) == ["digest", "normalization_receipt", "value"]


def test_cook_pyz_accepts_a_plan_when_spec_has_no_landing_block(tmp_path: Path) -> None:
    pointer_path, _pointer = _publish(tmp_path, "op-landing-absent", doc=TWO_CURD_DOC)
    result = _accept_with_spec(pointer_path, MINI_SPEC_FIXTURE)
    assert result.returncode == 0, result.stdout + result.stderr
    wrapper = cast(dict[str, object], json.loads(result.stdout))
    assert sorted(wrapper) == ["digest", "normalization_receipt", "value"]


def test_cook_pyz_rejects_a_missing_spec_file(tmp_path: Path) -> None:
    pointer_path, _pointer = _publish(tmp_path, "op-missing-spec")
    missing_spec = tmp_path / "does-not-exist.md"
    result = _accept_with_spec(pointer_path, missing_spec)
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr.startswith("ERROR:")
    assert "Traceback" not in result.stderr
    assert result.stdout == ""


def test_cook_pyz_rejects_a_malformed_landing_block(tmp_path: Path) -> None:
    pointer_path, _pointer = _publish(tmp_path, "op-malformed-landing")
    spec_path = _spec_with_landing(tmp_path, "landing:\n  shape: sideways")
    result = _accept_with_spec(pointer_path, spec_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "landing-closed-class" in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""


def test_cook_pyz_refuses_a_plan_missing_a_curd_from_layers(tmp_path: Path) -> None:
    pointer_path, _pointer = _publish(tmp_path, "op-missing-curd", doc=TWO_CURD_DOC)
    spec_path = _spec_with_landing(
        tmp_path,
        "landing:\n  shape: stacked_linear\n"
        + '  layers: [["curdplan-cook-accept-1/curd/1"]]',
    )
    result = _accept_with_spec(pointer_path, spec_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (
        "landing-layer-missing-curd curd 'curdplan-cook-accept-1/curd/2' is missing from "
        + "landing.layers"
    ) in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_refuses_a_plan_naming_an_unknown_curd_in_layers(tmp_path: Path) -> None:
    pointer_path, _pointer = _publish(tmp_path, "op-unknown-curd", doc=TWO_CURD_DOC)
    spec_path = _spec_with_landing(
        tmp_path,
        "landing:\n  shape: stacked_linear\n"
        + '  layers: [["curdplan-cook-accept-1/curd/1"], '
        + '["curdplan-cook-accept-1/curd/2"], ["curdplan-cook-accept-1/curd/9"]]',
    )
    result = _accept_with_spec(pointer_path, spec_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "landing-layer-unknown-curd landing.layers names unknown curd" in result.stderr
    assert "curdplan-cook-accept-1/curd/9" in result.stderr


def test_cook_pyz_accepts_same_layer_dependency(tmp_path: Path) -> None:
    pointer_path, _pointer = _publish(tmp_path, "op-same-layer", doc=TWO_CURD_DOC)
    spec_path = _spec_with_landing(
        tmp_path,
        "landing:\n  shape: stacked_linear\n"
        + '  layers: [["curdplan-cook-accept-1/curd/1", "curdplan-cook-accept-1/curd/2"]]',
    )
    result = _accept_with_spec(pointer_path, spec_path)
    assert result.returncode == 0, result.stdout + result.stderr
    wrapper = cast(dict[str, object], json.loads(result.stdout))
    assert sorted(wrapper) == ["digest", "normalization_receipt", "value"]


def test_cook_pyz_accepts_single_shape_with_empty_layers_for_two_curd_plan(
    tmp_path: Path,
) -> None:
    pointer_path, _pointer = _publish(tmp_path, "op-single-empty-layers", doc=TWO_CURD_DOC)
    spec_path = _spec_with_landing(tmp_path, "landing:\n  shape: single\n  layers: []")
    result = _accept_with_spec(pointer_path, spec_path)
    assert result.returncode == 0, result.stdout + result.stderr
    wrapper = cast(dict[str, object], json.loads(result.stdout))
    assert sorted(wrapper) == ["digest", "normalization_receipt", "value"]


def test_cook_pyz_says_on_stderr_whether_landing_layers_were_checked(tmp_path: Path) -> None:
    pointer_path, _pointer = _publish(tmp_path, "op-landing-note", doc=TWO_CURD_DOC)
    unchecked = _accept(pointer_path)
    assert unchecked.returncode == 0, unchecked.stdout + unchecked.stderr
    assert "NOTE: landing layers not checked (no --spec)" in unchecked.stderr
    checked = _accept_with_spec(pointer_path, MINI_SPEC_FIXTURE)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert (
        f"NOTE: landing layers not checked ({str(MINI_SPEC_FIXTURE)!r} declares no layers)"
        in checked.stderr
    )
    assert "ERROR:" not in checked.stderr
    layered = _accept_with_spec(
        pointer_path,
        _spec_with_landing(
            tmp_path,
            "landing:\n  shape: stacked_linear\n"
            + '  layers: [["curdplan-cook-accept-1/curd/2"], ["curdplan-cook-accept-1/curd/1"]]',
        ),
    )
    assert layered.returncode == 0, layered.stdout + layered.stderr
    assert "NOTE: landing layers checked against " in layered.stderr


def test_cook_pyz_rejects_a_non_utf8_spec_without_a_traceback(tmp_path: Path) -> None:
    pointer_path, _pointer = _publish(tmp_path, "op-binary-spec", doc=TWO_CURD_DOC)
    spec_path = tmp_path / "binary.md"
    _ = spec_path.write_bytes(b"---\nlanding:\n  shape: single\n---\n\xff\xfe")
    result = _accept_with_spec(pointer_path, spec_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"ERROR: cannot read spec {str(spec_path)!r}" in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""


def test_cook_pyz_rejects_a_spec_that_is_not_a_regular_file(tmp_path: Path) -> None:
    pointer_path, _pointer = _publish(tmp_path, "op-dir-spec", doc=TWO_CURD_DOC)
    result = _accept_with_spec(pointer_path, tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"ERROR: cannot read spec {str(tmp_path)!r}: not a regular file" in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_rejects_a_spec_larger_than_the_byte_cap(tmp_path: Path) -> None:
    pointer_path, _pointer = _publish(tmp_path, "op-huge-spec", doc=TWO_CURD_DOC)
    spec_path = tmp_path / "huge.md"
    _ = spec_path.write_bytes(b"---\nlanding:\n  shape: single\n---\n" + b"x" * 1_000_001)
    result = _accept_with_spec(pointer_path, spec_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (
        f"ERROR: cannot read spec {str(spec_path)!r}: larger than 1000000 bytes"
        in result.stderr
    )
    assert "Traceback" not in result.stderr
    assert result.stdout == ""


def test_cook_pyz_escapes_a_spec_path_that_could_forge_a_stderr_line(tmp_path: Path) -> None:
    pointer_path, _pointer = _publish(tmp_path, "op-evil-path", doc=TWO_CURD_DOC)
    spec_path = tmp_path / "evil\nERROR: forged.md"
    _ = spec_path.write_text(MINI_SPEC_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    result = _accept_with_spec(pointer_path, spec_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "\nERROR:" not in result.stderr
    assert "evil\\nERROR: forged.md" in result.stderr