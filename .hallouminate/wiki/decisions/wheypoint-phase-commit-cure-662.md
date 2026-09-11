# Wheypoint phase-commit cure decisions (PR #662)

Recorded by the `/affinage` → `/cure` chain on PR #662 (`feat/wheypoint-phase-rehydration`). These are the review findings that changed the design, plus one open decision.

## Decisions

- **One repository-root source.** `paths.resolve_repo_root(root)` (git toplevel, else cwd, resolved) is the only way the kernel derives "the repository root". `lint.lint_work`, `resolve.resolve()`, `commit._digest_root`, and `phase_commit.commit_phase_revision` all call it. Before this, the reader anchored to bare cwd while the writer digested against the explicit artifact root, so `wheypoint-resolve` from a subdirectory produced a gating `stale-artifact-link`.
- **One grounded-entry grammar.** `shared/wheypoint/grounded.py` owns `parse_grounded_entry`, `validate_grounded`, `GroundedEntryError`, `MAX_GROUNDED_ENTRIES`. `phase_commit` re-exports them; `lint._grounded_path_findings` parses with the same function. The module deliberately imports nothing from the kernel so it can sit under both `lint` and `phase_commit` without the `lint → phase_commit → commit → lint` cycle basedpyright rejects.
- **`error` is a real resolve outcome.** `wheypoint-resolve` prints the full payload with `outcome: "error"`, `ok: false`, `dispatchable: false`, plus `findings`/`searched`/`source`, and exits `EXIT_REFUSED`. The bare `{ok, command, error}` envelope is reserved for usage and internal errors. `shared/wheypoint/resolve_cli.py` is the single owner of the payload projection (`resolve_payload`, `Refusal`, `BadUsage`, `Parser`, `EXIT_*`); `skills/wheypoint/wheypoint.py::_run_resolve` calls it and keeps only `--legacy`.
- **Read-only git guard covers `run_git`.** `tests/wheypoint/python/test_projection.py` scans both literal `["git", ...]` argv and `run_git([...])` / `_run_git_ok([...])` calls. Kernel git calls go through `easy_cheese.shared.git_utils.run_git`; add new invocations to `READ_ONLY_GIT` there.
- **Chain-phase write boundary.** `write-handoff-artifact` accepts `--corpus-root`, opens one `WorkStore` for the pre-read and the commit, rejects `--grounded` on non-chain phases, and reports wheypoint failures as `wheypoint: <TypeName>: <message>` with a traceback on stderr. A commit failure after the artifact landed says so explicitly and names the `stale-artifact-link` consequence.
- **Retry is observable.** `commit_phase_revision` returns `CommitOutcome(result, retried)` and writes one stderr line naming the refreshed parent revision before the single retry.
- **Lineage checks read receipts only.** `WorkStore.receipt_revisions()` parses revision JSON without reading or hashing projections; `commit._check_lineage` uses it, so a commit no longer rescans every projection in the store.

## Open decision

- **Artifact-before-commit ordering.** `write_artifact` still `os.replace`s the phase artifact before `commit_phase_revision`; `test_commit_failure_keeps_written_artifact` locks that. A deterministic commit failure therefore leaves an artifact whose digest no longer matches the last revision's link, and the next resolve gates on `stale-artifact-link`. Options: commit first against the staged tmp digest, restore the prior bytes on failure, or make that link non-gating when the artifact is newer than the revision. Not changed in #662; author's call.

## Follow-up

- Every skill bundle carries the whole `easy_cheese.shared` tree, so the kernel move added ~190 KB to each of 13 `.pyz` files. Splitting the kernel into its own wheel for the chain skills only is a sprawling change left for a later PR.
