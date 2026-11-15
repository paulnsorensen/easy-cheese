"""Read one work through the public `resolve` and report what it found.

The removed `lint` command used to answer "what is wrong with this store".
`resolve` now owns that check, so tests that need the findings of a single
store ask it by work id instead of reaching into a private helper.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from attrs import define

from easy_cheese.shared.wheypoint import lint_types
from easy_cheese.shared.wheypoint import resolve as resolve_mod
from easy_cheese.shared.wheypoint import storage


@define(frozen=True)
class Checked:
    resolution: resolve_mod.Resolution

    @property
    def findings(self) -> tuple[lint_types.LintFinding, ...]:
        return self.resolution.findings

    @property
    def codes(self) -> tuple[lint_types.LintCode, ...]:
        return tuple(finding.code for finding in self.findings)

    @property
    def blocking(self) -> tuple[lint_types.LintFinding, ...]:
        return tuple(f for f in self.findings if lint_types.gates_continuation(f))


def check_work(
    store: storage.WorkStore,
    *,
    project_key: str,
    git_object_exists: Callable[[str], bool] = lambda _obj: True,
    artifact_digest: Callable[[str], str | None] = lambda _path: None,
) -> Checked:
    return Checked(
        resolve_mod.resolve(
            store.work_id,
            corpus_root=Path(store.corpus_root),
            project_key=project_key,
            git_object_exists=git_object_exists,
            artifact_digest=artifact_digest,
        )
    )
