# R014 Megamerge Re-review

The review covers `origin/main...HEAD`.
It verifies all 30 findings from `.cheese/notes/r014-megamerge/holistic-review.md`.
Current state: 24 applied, six partly applied, and none open.

## Verification table

| Finding | Severity | State | Evidence |
| --- | --- | --- | --- |
| The Age lock can certify a different reviewed tree. | Blocker | applied | `tree_digest` hashes `HEAD`, streams tracked changes, and includes `.cheese` inputs. Tests cover clean commits and spec changes (`src/easy_cheese/skills/age/review_lock.py:134-183`; `tests/python/test_age_review_lock.py:54-113`). |
| Publication uses a second, weaker artifact resolver. | Blocker | applied | Publication calls `resolve_artifact` inside the declared root. The resolver verifies URI policy, size, digest, media type, and schema (`src/easy_cheese/shared/publication.py:414-436`; `src/easy_cheese_schemas/artifacts.py:65-126`). |
| Corrupt payload repair can delete a valid concurrent write. | Blocker | partly applied | POSIX repairs lock per digest. Non-POSIX repairs skip locking and keep the `stat()`-to-`unlink()` race (`src/easy_cheese/shared/publication.py:26-29,353-398`; `pyproject.toml:15-22`). |
| Wheypoint reports failure after it advances canonical state. | Blocker | applied | The pending ledger records request and revision identity. Retry resumes the same committed revision (`src/easy_cheese/skills/wheypoint/wheypoint.py:264-309`; `tests/wheypoint/python/test_checkpoint.py:461-506`). |
| Plate never detects a normal `gh stack` installation. | Blocker | applied | Plate reads the repository from the second extension column. The fixture uses actual CLI output (`src/easy_cheese/skills/plate/stack_tools.py:104-114`; `tests/python/test_plate_runtime.py:129-160`). |
| Briesearch persists credential-bearing URLs in durable state. | Blocker | partly applied | Prose requires redaction, but `load_ledger` accepts raw query values and redacts only after reading persisted JSON (`skills/briesearch/references/context-isolation.md:61`; `src/easy_cheese/skills/briesearch/ledger.py:230-258,344-354`). |
| Briesearch emits URL secrets on failure paths. | Blocker | applied | `budget` and `ground_check` use `render_url`, which removes user information and query values (`src/easy_cheese/skills/briesearch/ledger.py:83-94`; `src/easy_cheese/skills/briesearch/budget.py:135-147`; `src/easy_cheese/skills/briesearch/ground_check.py:263-291`). |
| Mold names the wrong hard-cheese boundary. | Blocker | partly applied | Skill prose names Plate as the caller. One stale test still calls Cure the gate-firing skill (`skills/mold/SKILL.md:121-125`; `skills/cure/SKILL.md:227-234`; `tests/python/test_hard_cheese.py:156-158`). |
| URL identity discards authorization context. | High | applied | Ledger ingestion and citation checks reject user information before correlation (`src/easy_cheese/skills/briesearch/ledger.py:163-185,239-245`; `src/easy_cheese/skills/briesearch/ground_check.py:269-281`). |
| URL identity merges distinct trailing-slash resources. | High | applied | `canonical_url` preserves non-root trailing slashes. Its test treats `/a` and `/a/` as different resources (`src/easy_cheese/skills/briesearch/ledger.py:163-185`; `tests/python/test_briesearch_ledger.py:59-71`). |
| Citation parsing truncates valid parenthesized URLs. | High | applied | `_remote_urls` balances delimiters. The focused test preserves `/wiki/Foo_(bar)` (`src/easy_cheese/skills/briesearch/ground_check.py:240-260`; `tests/python/test_briesearch_ledger.py:243-252`). |
| The standalone Mold validator has a dependency-order failure. | High | applied | The validator falls back after any package import failure. The isolated test removes only `cattrs` (`src/easy_cheese/skills/mold/validate_spec.py:100-136`; `tests/python/test_validate_spec.py:82-121`). |
| The release decision file contradicts the integrated implementation. | High | partly applied | Resolved sections record the new choices, but earlier text still states unconditional legacy failure as verified behavior (`.cheese/plans/release-0-14-decisions.md:12-45,246-251`; `tests/python/test_validate_spec.py:562-592`). |
| Publication replay accepts a corrupt receipt. | High | applied | Replay uses `_resolve_pointer`, which verifies the receipt and binds its digest to the payload (`src/easy_cheese/shared/publication.py:450-486,559-561`; `tests/python/test_publication_gateway.py:362-371`). |
| Built-in migration behavior depends on import order. | High | applied | `compat` registers the built-in adapter at package import. An isolated test proves lookup before `shared.migrate` import (`src/easy_cheese_schemas/compat.py:487-550`; `tests/python/test_schemas_compat.py:367-417`). |
| Wheypoint uses two incompatible ancestry validators. | High | applied | Commit and lint call the same lineage walker. Tests cover missing parents, cycles, and digest changes (`src/easy_cheese/skills/wheypoint/lineage.py:58-125`; `src/easy_cheese/skills/wheypoint/commit.py:356-405`; `src/easy_cheese/skills/wheypoint/lint.py:353-397`). |
| Mold document invariants have two owners. | High | partly applied | `validate_spec` constructs `MoldSpecDocument`. `taste_test` still parses frontmatter, contracts, and applicability independently (`src/easy_cheese/skills/mold/validate_spec.py:595-634`; `src/easy_cheese/shared/taste_test.py:443-490,586-638,659-758`). |
| Replay identity lacks a direct test. | High | applied | A direct parameterized test changes each route and schema field and requires a new digest (`tests/python/test_publication_gateway.py:76-94`). |
| Legacy receipt tests miss half-populated source metadata. | High | applied | Both validation-layer tests remove each source field separately (`tests/schemas/python/test_contracts.py:1029-1074`). |
| The manifest adjacency test can pass without loading a manifest. | High | partly applied | A mismatched manifest must fail, but the positive test still checks only exit status (`tests/python/test_briesearch_ledger.py:227-233,288-298`). |
| The active Mold graph advertises a forbidden legacy path. | Medium | applied | The active graph and DOT output use `Typed planner stage` (`src/easy_cheese/skills/mold/gate_graph.py:107-134`; `skills/mold/scripts/mold.dot:27,50,52`). |
| The bundle gate repeats archive and Git work. | Medium | applied | One `_ArchiveAnalysis` caches member bytes and syntax trees. One Git batch reads all baseline bundles (`scripts/check_bundles.py:530-633,719-755,846-890`; `tests/python/test_check_bundles.py:68-126`). |
| Ground checking rescans the ledger for every report row. | Medium | applied | `check_report` builds `retrieved` once and passes the map to each row (`src/easy_cheese/skills/briesearch/ground_check.py:394-447`; `tests/python/test_briesearch_ledger.py:267-285`). |
| The Age lock materializes each complete tree snapshot. | Medium | applied | `_stream_git` hashes bounded chunks. Untracked paths retain only the current NUL-delimited tail (`src/easy_cheese/skills/age/review_lock.py:61-77,93-130`). |
| Shared paths own a Briesearch-only layout. | Medium | applied | `ResearchLayout` lives in Briesearch. Shared paths retain only flat artifact primitives (`src/easy_cheese/skills/briesearch/research_layout.py:20-50`; `src/easy_cheese/shared/paths.py:247-284`). |
| Documentation generation rewrites unchanged output. | Low | applied | Generation renders in a temporary directory and replaces only changed files. Tests preserve unchanged modification times (`scripts/gen_docs.py:163-211,629-646`; `tests/python/test_gen_docs.py:796-855`). |
| Publication serializes canonical values twice. | Low | applied | Publication hashes `validated.canonical_bytes` and one receipt serialization directly (`src/easy_cheese/shared/publication.py:565-581`). |
| Legacy resolution repeats the same worktree scan. | Low | applied | `LegacyLookup` carries the first scan roots. Parent validation reuses them (`src/easy_cheese/skills/wheypoint/legacy.py:355-380`; `src/easy_cheese/skills/wheypoint/resolve.py:453-458`). |
| The bundle checker hand-parses one option. | Low | applied | `_parse_against` uses `argparse` with constrained choices. Tests cover standard option syntax and help (`scripts/check_bundles.py:832-843`; `tests/python/test_check_bundles.py:41-65`). |
| Mold uses an undefined abbreviation. | Low | applied | Runtime text and generated prose use `current Mold specification requirements` (`src/easy_cheese/skills/mold/validate_spec.py:2`; `src/easy_cheese/skills/mold/commands.py:91-93`; `skills/mold/references/commands.md:14`). |

## Residual findings

### Blocker

- **[correctness:blocker] Publication repair lacks a non-POSIX lock.** The package declares OS-independent support (`pyproject.toml:15-22`). `_digest_lock` does nothing without `fcntl` (`src/easy_cheese/shared/publication.py:26-29,353-370`). A lockless probe replaced the file after the final stat. `_retain_content` then removed the valid replacement (`src/easy_cheese/shared/publication.py:382-399`).
- **[security:blocker] Briesearch still accepts raw signed URLs in persisted manifests.** The loader accepts query values, then redacts only its in-memory model (`src/easy_cheese/skills/briesearch/ledger.py:230-258,344-354`). The documented redacted URL and full digest also fail correlation (`src/easy_cheese/skills/briesearch/ledger.py:147-160`; `src/easy_cheese/skills/briesearch/ground_check.py:263-293`). A contract probe returned `REMOTE` for that safe pair.

### High

- **[assertions:high] The hard-gate boundary lacks a correct regression test.** Prose now assigns invocation to Plate (`skills/cure/SKILL.md:227-234`; `skills/plate/SKILL.md:45-46`). The test still calls Cure the gate-firing skill (`tests/python/test_hard_cheese.py:156-158`).
- **[spec:high] The release decision record still mixes current and superseded behavior.** The file labels unconditional legacy rejection as verified behavior before its resolved section (`.cheese/plans/release-0-14-decisions.md:12-45`).
- **[encapsulation:high] Mold still has an independent invariant parser.** `taste_test` duplicates frontmatter, test-contract, and applicability rules outside `MoldSpecDocument` (`src/easy_cheese/shared/taste_test.py:443-490,586-638,659-758`).
- **[assertions:high] The positive manifest adjacency test remains weak.** It does not assert that the `MANIFEST` advisory is absent (`tests/python/test_briesearch_ledger.py:227-233`).

### Medium

none

### Low

none

## Cohesion verdict

The cure applies 24 findings and partly applies six. Most cross-area contracts now agree. Two blocker risks remain in Publication and Briesearch. Four high residuals affect tests, records, and Mold ownership. The integrated branch remains a reject until the blocker risks close.

## Follow-ups

- Add a non-POSIX digest lock or atomic compare-and-swap repair. Add a post-stat replacement test.
- Reject query-bearing manifest URLs. Define correlation for the redacted display URL and full digest.
- Replace `test_cure_invokes_hard_cheese` with assertions for Cure forwarding and Plate invocation.
- Mark `.cheese/plans/release-0-14-decisions.md:12-35` as historical. Update its validator line reference.
- Make `taste_test` consume the canonical typed Mold document.
- Make the positive adjacency test reject the `MANIFEST` advisory.

## Second cure

| Finding | State | Commit | Evidence |
| --- | --- | --- | --- |
| Publication repair preserves a racing valid replacement. | applied | `e52fc36` | `src/easy_cheese/shared/publication.py:373-415`; `tests/python/test_publication_recovery.py:166-193` |
| Briesearch rejects query values and correlates redacted URLs. | applied | `2ce4719` | `src/easy_cheese/skills/briesearch/ledger.py:147-164,233-265`; `tests/python/test_briesearch_ledger.py:86-116` |
| Plate owns the hard-gate invocation boundary. | applied | `1fba358` | `tests/python/test_hard_cheese.py:156-167` |
| The release record marks legacy rejection as historical. | applied | `eacfd10` | `.cheese/plans/release-0-14-decisions.md:12-45`; `tests/python/test_validate_spec.py:575-584` |
| Mold taste checks consume `MoldSpecDocument`. | applied | `af41bb2` | `src/easy_cheese/shared/taste_test.py:700-817`; `tests/python/test_mold_taste_test.py:438-453` |
| The positive manifest test rejects the `MANIFEST` advisory. | applied | `3498207` | `tests/python/test_briesearch_ledger.py:240-249` |
