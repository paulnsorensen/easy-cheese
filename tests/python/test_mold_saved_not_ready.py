from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from easy_cheese.skills.mold.producer import finalize_mold
from easy_cheese_schemas.mold_cook import MoldCookMode


FIXTURE = Path(__file__).parent / "fixtures" / "spec_format" / "valid_spec.md"


def _spec(tmp_path: Path, *, do_not_implement: bool = False) -> Path:
    text = FIXTURE.read_text(encoding="utf-8")
    if do_not_implement:
        text = text.replace(
            "gates_overridden: []\n",
            "gates_overridden: []\nrequest_directive: do-not-implement\n",
            1,
        )
    path = tmp_path / "spec.md"
    _ = path.write_text(text, encoding="utf-8")
    return path


def test_incomplete_finalization_saves_a_blocked_preparation_result(
    tmp_path: Path,
) -> None:
    outcome = finalize_mold(
        _spec(tmp_path),
        artifact_root=tmp_path / "artifacts",
        operation_id="saved-1",
        request_id="saved-request-1",
        mode=MoldCookMode.LIGHT,
        approval={},
    )

    assert outcome.status == "saved-not-ready"
    assert outcome.ready is False
    assert outcome.result_path is not None
    saved = cast(
        dict[str, object],
        json.loads(outcome.result_path.read_text(encoding="utf-8")),
    )
    assert saved["status"] == "saved-not-ready"
    assert saved["saved"] is True
    preparation = cast(Mapping[str, object], saved["preparation_result"])
    assert preparation["outcome"] == "blocked"
    assert preparation["request_id"] == "saved-request-1"
    assert not (tmp_path / "artifacts" / "pointers" / "saved-1.json").exists()


def test_save_only_override_and_user_hold_never_emit_a_pointer(tmp_path: Path) -> None:
    outcome = finalize_mold(
        _spec(tmp_path, do_not_implement=True),
        artifact_root=tmp_path / "artifacts",
        operation_id="saved-2",
        request_id="saved-request-2",
        mode=MoldCookMode.LIGHT,
        approval={},
        curdle_anyway=True,
    )

    assert outcome.status == "saved-not-ready"
    assert outcome.ready is False
    hold_rows = cast(Sequence[Mapping[str, object]], outcome.payload["holds"])
    hold_ids = {str(item["hold_id"]) for item in hold_rows}
    assert {"curdle-anyway", "user-do-not-implement"} <= hold_ids
    assert "next" not in outcome.payload
    assert not (tmp_path / "artifacts" / "pointers" / "saved-2.json").exists()
