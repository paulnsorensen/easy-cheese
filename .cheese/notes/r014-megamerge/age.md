# Age Area Reconciliation

## Summary

The age area now enforces one review-only boundary.

The review lock hashes tracked changes and untracked file content.
The handoff command derives `next` from the review findings.
The command manifest remains the only bundle command source.

The reconciliation audits all age Markdown prose for ASD-STE100 compliance.
`just bundle` rebuilds all 13 skill bundles.
`just check` passes after the rebuild.

## Commits

- `7ce9519` ingests the PR #592 age slice.
- `b3ddbeb` ingests the PR #581 age slice.
- `a2457cf` ingests the PR #586 age slice.
- `c580604` reconciles the age area and rebuilds the bundles.

## Source PRs

- PR #581 adds manifest-driven command documentation and required command summaries.
- PR #586 adds the review lock and the guarded handoff writer.
- PR #592 adds enforceable skill boundaries and bundle command doctrine.

## Disagreements

- `skills/age/SKILL.md` always passed `--next cure`, but its output contract also required `next: done` for clean reviews. The reconciliation keeps the outcome-derived state because it matches the report contract.
- `skills/age/references/handoff-detail.md` repeated the bundled command as its own fallback. The reconciliation removes the duplicate because both instructions ran the same command.
- `src/easy_cheese/skills/age/review_lock.py` promised an unchanged production tree, but it hashed only untracked paths. The reconciliation also hashes untracked content because an inline edit must invalidate the lock.

## Outward dependencies

- this -> shared: `commands.py` uses `bundle_commands`, `artifact_path`, fan-out commands, severity, path, handoff, and HTML commands.
- this -> shared: `review_lock.py` uses `cli`, `git_utils`, and `write_handoff_artifact`.
- this -> shared: `age_html_report.py` uses `cli` and `html_report`.
- this -> schemas: the age report emits the canonical handback fields through the shared handoff writer.
- press -> this: age reads `.cheese/press/<slug>.md` through `read-handoff-slug`.
- cook -> this: the cook fan pathway dispatches age and consumes its `next` state.
- affinage -> this: affinage uses the age review flow and its fan-out contract.
- this -> cure: age emits `.cheese/age/<slug>.md` and dispatches `/cure` for selected findings.
- build -> this: `scripts/build_pyz.py` packages `commands.py` and `review_lock.py` into `skills/age/scripts/age.pyz`.
- build -> this: `scripts/render_generated_regions.py` generates `skills/age/references/commands.md` from `COMMANDS`.

## STE100 status

compliant

## Follow-ups

none
