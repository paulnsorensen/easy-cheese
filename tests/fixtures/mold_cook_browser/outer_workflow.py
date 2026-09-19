"""Execute the accepted Cook handoff and produce the browser feature."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

from easy_cheese_schemas.contracts import (
    Criterion,
    CriterionDisposition,
    CriterionResultWriterView,
    CurdResultWriterView,
    ReviewDisposition,
    ReviewResultWriterView,
)
from easy_cheese.skills.cook.preparation import execute_accepted_handoff


def _write_feature(
    repository: Path, context: dict[str, object]
) -> CurdResultWriterView:
    criteria = cast(tuple[Criterion, ...], context["criteria"])
    document = """<!doctype html>
<html><body>
<h1>Mold to Cook fixture</h1>
<p data-testid="feature-state">ready</p>
<button type="button" id="run">Run feature</button>
<p data-testid="feature-result">Waiting</p>
<script>
  document.querySelector('#run').addEventListener('click', () => {
    document.querySelector('[data-testid="feature-result"]').textContent = 'Feature executed';
  });
</script>
</body></html>
"""
    _ = (repository / "index.html").write_text(document, encoding="utf-8")
    return CurdResultWriterView(
        criterion_results=tuple(
            CriterionResultWriterView(
                criterion_id=criterion.criterion_id,
                disposition=CriterionDisposition.PASSED,
            )
            for criterion in criteria
        )
    )


def _clean_review(_request: object) -> ReviewResultWriterView:
    return ReviewResultWriterView(disposition=ReviewDisposition.CLEAN, findings=())


def _unexpected_diagnosis(_request: object) -> object:
    raise AssertionError("clean feature must not dispatch diagnosis")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        raise SystemExit("usage: outer_workflow.py POINTER REPOSITORY ARTIFACT_ROOT")
    pointer, repository, artifact_root = (Path(value) for value in argv)
    results = execute_accepted_handoff(
        pointer,
        artifact_root=artifact_root,
        repository_root=repository,
        dispatch_writer=lambda context: _write_feature(
            repository, cast(dict[str, object], context)
        ),
        dispatch_review=_clean_review,
        dispatch_diagnosis=_unexpected_diagnosis,
    )
    print(
        json.dumps(
            {
                "feature": "index.html",
                "results": len(results.execution_results[1]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
