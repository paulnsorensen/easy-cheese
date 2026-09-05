# R014 Megamerge Holistic Review

## Summary

Verdict: **reject**.

The review covers `origin/main...HEAD` as one integrated change.
The structural diff covers 253 files and reports 111 modified symbols plus 475 added symbols.
Eight blocker findings prevent merge.
The strongest failures affect review identity, artifact publication, credential handling, and Wheypoint durability.

Verification uses source inspection and two behavioral probes.
The review-lock probe changes `HEAD` between clean commits and produces the same digest.
The URL probe collapses three authorization and path variants into one identity.
The same probe truncates a parenthesized URL.

## Commits

none

## Source PRs

- #592
- #568
- #565
- #581 through #589

## Disagreements

- The Age tree-lock decision remains incomplete because the digest omits `HEAD` and all `.cheese` content.
- The publication replay decision includes route and schema fields, but tests do not protect those fields.
- The Wheypoint checkpoint decision remains unsafe after a mirror write fails after commit.

## Outward dependencies

none

## STE100 status

- `skills/mold/references/commands.md` still uses the undefined abbreviation `SAP`.

## Follow-ups

none

## Blocker

- **[correctness:blocker] The Age lock can certify a different reviewed tree.** `src/easy_cheese/skills/age/review_lock.py:36,57-68` hashes `git diff HEAD` and selected untracked files. A different clean commit produces the same digest. The code also excludes all `.cheese` files, including specs and notes. The behavioral probe confirmed equal digests for different clean commits. Location: contract. Fix cost now: contained. Fix cost later: structural. Confidence: certain. Overlap: spec, assertions. **Fix:** Bind the lock to the captured tree object. Hash every review input except the lock and report outputs. Add clean-checkout and `.cheese/specs` mutation tests.

- **[nih:blocker] Publication uses a second, weaker artifact resolver.** `src/easy_cheese/shared/publication.py:595-609` reads an `ArtifactRef` with local path and digest checks only. `src/easy_cheese_schemas/artifacts.py:58-114,217-245,449-497` already validates authority, query, fragment, size, media type, links, and digest. The weaker path can read an unbounded file and accept false reference metadata. Location: contract. Fix cost now: sprawling. Fix cost later: structural. Confidence: certain. Overlap: correctness, security, encapsulation. **Fix:** Extend `resolve_artifact` to return verified bytes under the publication root. Delete `_uri_to_path`, `_verify_artifact_ref`, and the duplicate read path.

- **[correctness:blocker] Corrupt payload repair can delete a valid concurrent write.** `src/easy_cheese/shared/publication.py:347-351` reads a corrupt digest path and then unlinks that path. Another retry can replace the path with valid bytes before the unlink. The first process then removes the valid payload after pointer reveal. Location: contract. Fix cost now: moderate. Fix cost later: structural. Confidence: certain. Overlap: security, telemetry. **Fix:** Serialize repair per digest. Use inode-aware quarantine or compare-and-swap behavior. Revalidate the payload immediately before pointer reveal.

- **[correctness:blocker] Wheypoint reports failure after it advances canonical state.** `src/easy_cheese/skills/wheypoint/wheypoint.py:200-239` commits `repo-snapshot` durability before the required mirror write. A mirror failure returns `note-unwritable` after the revision exists. A normal retry can bind the new parent and append protected entries again. Location: contract. Fix cost now: moderate. Fix cost later: structural. Confidence: certain. Overlap: spec, telemetry, encapsulation. **Fix:** Make mirror publication a recoverable transaction phase. Persist request identity and resume the committed revision. Report success only after the mirror becomes durable.

- **[correctness:blocker] Plate never detects a normal `gh stack` installation.** `src/easy_cheese/skills/plate/stack_tools.py:104-117` compares the first output column with `github/gh-stack`. GitHub CLI puts the command name first and the repository second. `tests/python/test_plate_runtime.py:150-156` uses the inverse shape, so the test protects the bug. Location: contract. Fix cost now: contained. Fix cost later: contained. Confidence: certain. Overlap: spec, assertions. **Fix:** Parse the tabular repository column or use a targeted machine-readable query. Replace the fixture with actual CLI output.

- **[security:blocker] Briesearch persists credential-bearing URLs in durable state.** `skills/briesearch/references/context-isolation.md:34,41-54,75-77` requires raw extraction URLs in a cross-session manifest. `src/easy_cheese/skills/briesearch/ledger.py:196-207` retains the raw value. Basic-auth URLs and signed query URLs can therefore remain after credential rotation. Location: contract. Fix cost now: moderate. Fix cost later: structural. Confidence: certain. Overlap: telemetry, spec. **Fix:** Reject URL user information. Store a redacted display URL and a non-reversible full-URL digest. Never write raw credentials to disk.

- **[security:blocker] Briesearch emits URL secrets on failure paths.** `src/easy_cheese/skills/briesearch/budget.py:134-145` prints canonical query strings for duplicate extraction. `src/easy_cheese/skills/briesearch/ground_check.py:243-259` prints raw missing URLs. Signed tokens can enter terminal, agent, and CI logs. Location: cross-module. Fix cost now: moderate. Fix cost later: spreading. Confidence: certain. Overlap: telemetry. **Fix:** Route URL diagnostics through one safe renderer. Remove user information and query values. Keep a short digest when correlation is necessary.

- **[spec:blocker] Mold names the wrong hard-cheese boundary.** `skills/mold/SKILL.md:121-123` says the check runs at Cure's share boundary. `skills/hard-cheese/SKILL.md:29-32` says only Plate runs the check after its final writing gate. Agents can run the gate before Plate changes the final tree. Location: contract. Fix cost now: contained. Fix cost later: spreading. Confidence: certain. Overlap: correctness, encapsulation. **Fix:** State that Cure only forwards `--hard`. Name Plate's verified-artifacts boundary as the only execution point.

## High

- **[security:high] URL identity discards authorization context.** `src/easy_cheese/skills/briesearch/ledger.py:143-146` builds the authority from `hostname` and `port`. It drops the username and password. `ground_check.py:248-250` trusts that identity. Retrieval under one authorization context can ground another context or an unauthenticated citation. Location: cross-module. Fix cost now: moderate. Fix cost later: spreading. Confidence: certain. Overlap: correctness, spec. **Fix:** Reject user information during ledger ingestion and citation scanning. Add tests for distinct authorization contexts.

- **[correctness:high] URL identity merges distinct trailing-slash resources.** `src/easy_cheese/skills/briesearch/ledger.py:143-146` removes every trailing slash. `tests/python/test_briesearch_ledger.py:50-53` locks `/a/` and `/a` together, although servers can route them differently. The behavioral probe confirmed the collision. Location: module. Fix cost now: contained. Fix cost later: contained. Confidence: certain. Overlap: assertions. **Fix:** Normalize only an empty path to `/`. Preserve non-root trailing slashes and replace the incorrect test oracle.

- **[correctness:high] Citation parsing truncates valid parenthesized URLs.** `src/easy_cheese/skills/briesearch/ground_check.py:63-72` stops a remote URL at every closing parenthesis. A valid path such as `/wiki/Foo_(bar)` cannot match its ledger entry. The behavioral probe returned `/wiki/Foo_(bar`. Location: module. Fix cost now: contained. Fix cost later: contained. Confidence: certain. Overlap: assertions. **Fix:** Parse Markdown links with balanced delimiters. Strip only unmatched closing punctuation. Add a parenthesized citation test.

- **[correctness:high] The standalone Mold validator has a dependency-order failure.** `src/easy_cheese/skills/mold/validate_spec.py:73-88` falls back only when the missing module is `attrs`. `src/easy_cheese_schemas/compat.py:32-36` can fail first on `cattrs`. The isolated import then exits before it loads the dependency-free format module. Location: module. Fix cost now: contained. Fix cost later: spreading. Confidence: certain. Overlap: portability. **Fix:** Load the local format module after any package-import dependency failure. Re-raise when the local module is absent. Test with `attrs` present and `cattrs` absent.

- **[spec:high] The release decision file contradicts the integrated implementation.** `.cheese/plans/release-0-14-decisions.md:44-72` rejects legacy format acceptance. Lines 271-284 defer the command boundary work to release 0.15. The merged validator and command manifests implement both choices. The disagreement log records neither supersession. Location: module. Fix cost now: contained. Fix cost later: spreading. Confidence: certain. Overlap: cohesion, correctness. **Fix:** Record the newer PR decision explicitly. Rewrite the release file as a resolved record. Keep historical alternatives clearly marked.

- **[correctness:high] Publication replay accepts a corrupt receipt.** `src/easy_cheese/shared/publication.py:382-399` verifies only payload bytes during replay. `accept()` verifies payload and receipt at `publication.py:612-677`. A replay can report success for a pointer that its consumer immediately rejects. Location: cross-module. Fix cost now: contained. Fix cost later: spreading. Confidence: certain. Overlap: encapsulation. **Fix:** Use one pointer resolver for replay and acceptance. Validate the payload and optional receipt before either path returns success.

- **[encapsulation:high] Built-in migration behavior depends on import order.** `src/easy_cheese_schemas/compat.py:446-456` owns a mutable adapter registry. `src/easy_cheese/shared/migrate.py:193-213` registers the only built-in adapter during import. Schema consumers see different registries unless they import the higher-level migration module first. Location: cross-module. Fix cost now: sprawling. Fix cost later: spreading. Confidence: certain. Overlap: correctness, complexity. **Fix:** Pass the built-in adapter explicitly or register it in its owning package. Remove import-time mutation from `shared.migrate`.

- **[encapsulation:high] Wheypoint uses two incompatible ancestry validators.** `src/easy_cheese/skills/wheypoint/commit.py:347-372` silently returns no prior compaction for missing or cyclic ancestry. It does not check parent digests. `src/easy_cheese/skills/wheypoint/lint.py:356-427` rejects those states. Commit can persist a reset compaction link that lint later rejects. Location: module. Fix cost now: contained. Fix cost later: spreading. Confidence: certain. Overlap: correctness, complexity, efficiency. **Fix:** Extract one provenance-aware lineage walker. Use it under the commit lock and adapt the same result into lint findings.

- **[encapsulation:high] Mold document invariants have two owners.** `src/easy_cheese_schemas/contracts.py:2360-2420,2523-2582` defines typed mode, grounding, and acceptance rules. `src/easy_cheese/skills/mold/validate_spec.py:379-549` implements the same rules without constructing those types. `src/easy_cheese/shared/taste_test.py:443-492` adds another frontmatter parser with different scalar rules. Location: cross-module. Fix cost now: sprawling. Fix cost later: spreading. Confidence: certain. Overlap: correctness, spec, complexity. **Fix:** Parse Markdown once into the schema types. Keep only Markdown shape and explicit legacy policy in the text validator.

- **[assertions:high] Replay identity lacks a direct test.** `tests/python/test_publication_gateway.py:195-205` changes invalid route and schema values. `publish_canonical` rejects them before replay validation. The test still passes if `request_digest` omits route or schema identity. This leaves the recorded publication disagreement unlocked. Location: module. Fix cost now: contained. Fix cost later: spreading. Confidence: certain. Overlap: correctness, spec. **Fix:** Test `request_digest` directly. Prove that each route and schema field changes the digest independently.

- **[assertions:high] Legacy receipt tests miss half-populated source metadata.** `tests/schemas/python/test_contracts.py:1029-1054` omits `source_schema_uri` and `source_version` together. Both tests pass if production changes the required `or` predicate to `and`. Location: module. Fix cost now: contained. Fix cost later: contained. Confidence: certain. Overlap: correctness. **Fix:** Parameterize both validation layers with each single missing source field. Require rejection for both cases.

- **[assertions:high] The manifest adjacency test can pass without loading a manifest.** `tests/python/test_briesearch_ledger.py:206-212` asserts only exit status zero. The documented missing-manifest path also returns zero with an advisory. Location: module. Fix cost now: contained. Fix cost later: contained. Confidence: certain. Overlap: spec. **Fix:** Capture diagnostics and reject the `MANIFEST` advisory. Add a mismatched adjacent manifest that must fail.

## Medium

- **[deslop:medium] The active Mold graph advertises a forbidden legacy path.** `src/easy_cheese/skills/mold/gate_graph.py:107-134` and `skills/mold/scripts/mold.dot:27` name a `Curd-block decomposer`. `skills/mold/references/curdle.md:384` limits that projection to explicit migration. Location: contract. Fix cost now: moderate. Fix cost later: spreading. Confidence: certain. Overlap: spec, correctness. **Fix:** Rename the graph node and edges to the typed planner stage. Keep `CurdBlock` only in migration documentation.

- **[efficiency:medium] The bundle gate repeats archive and Git work.** `scripts/check_bundles.py:378-386,444-462` reads and parses first-party modules twice. Lines 528-537 hash most package members twice. The bundle loop also starts one baseline Git process per archive at lines 720-750. Location: module. Fix cost now: moderate. Fix cost later: contained. Confidence: certain. Overlap: complexity. **Fix:** Build one archive analysis result per bundle. Update both hashes in one pass. Fetch baseline blobs in one batch.

- **[efficiency:medium] Ground checking rescans the ledger for every report row.** `src/easy_cheese/skills/briesearch/ground_check.py:243-250` calls `Ledger.retrieved()` inside each row check. That method scans all calls and allocates a new dictionary. Runtime grows as report rows times ledger calls. Location: module. Fix cost now: contained. Fix cost later: contained. Confidence: certain. Overlap: complexity. **Fix:** Build the retrieved URL map once in `check_report`. Pass the immutable map to row checks.

- **[efficiency:medium] The Age lock materializes each complete tree snapshot.** `src/easy_cheese/skills/age/review_lock.py:40-68` captures the full diff and untracked list as strings. It then encodes the diff into another allocation. Large reviews pay this cost at capture and verification. Location: module. Fix cost now: contained. Fix cost later: contained. Confidence: certain. Overlap: complexity. **Fix:** Stream Git output into the digest. Batch untracked paths without retaining the complete output.

- **[encapsulation:medium] Shared paths own a Briesearch-only layout.** `src/easy_cheese/shared/paths.py:296-328` exports `ResearchLayout`. Its sole production consumer is `src/easy_cheese/skills/briesearch/research_layout.py:28`. Shared code now owns one skill's `raw` and manifest structure. Location: cross-module. Fix cost now: sprawling. Fix cost later: spreading. Confidence: certain. Overlap: complexity. **Fix:** Move layout composition into Briesearch. Keep only corpus-root and slug primitives in shared paths.

## Low

- **[efficiency:low] Documentation generation rewrites unchanged output.** `scripts/gen_docs.py:535-548` removes the generated content tree and sidebar before every build. Repeated development builds rewrite all pages. Location: module. Fix cost now: contained. Fix cost later: contained. Confidence: certain. **Fix:** Render to a temporary result. Replace changed files only. Remove only stale paths.

- **[efficiency:low] Publication serializes canonical values twice.** `src/easy_cheese/shared/publication.py:477,491-492` rebuilds bytes that already exist as `validated.canonical_bytes` and `receipt_bytes`. Location: module. Fix cost now: contained. Fix cost later: contained. Confidence: certain. **Fix:** Hash the existing byte values directly.

- **[efficiency:low] Legacy resolution repeats the same worktree scan.** `src/easy_cheese/skills/wheypoint/resolve.py:340-365` calls `worktree_roots` after `find_legacy_note` already performed the same Git query. Location: module. Fix cost now: moderate. Fix cost later: contained. Confidence: certain. Overlap: complexity. **Fix:** Carry the first `WorktreeScan.roots` through `LegacyLookup`.

- **[nih:low] The bundle checker hand-parses one option.** `scripts/check_bundles.py:714-720` implements a custom `--against` parser. It turns standard `--help` into an error and accepts only one token order. Location: contract. Fix cost now: contained. Fix cost later: contained. Confidence: certain. Overlap: deslop. **Fix:** Use `argparse.ArgumentParser` with one constrained `--against` option.

- **[deslop:low] Mold uses an undefined abbreviation.** `src/easy_cheese/skills/mold/commands.py:91`, `src/easy_cheese/skills/mold/validate_spec.py:2`, and `skills/mold/references/commands.md:14` say `SAP`. The repository does not define the term. This violates the required STE100 term rule. Location: contract. Fix cost now: moderate. Fix cost later: spreading. Confidence: certain. Overlap: spec. **Fix:** Use one plain term, such as `current Mold specification requirements`. Regenerate the command reference and bundle.

## Simplifications

- Extend the schema artifact resolver instead of maintaining publication-only URI and digest code.
- Parse each Mold document once. Construct `MoldSpecDocument` and use its existing validators.
- Split `validate()` into Markdown shape, legacy policy, and typed model construction.
- Give publication one request context and one replay resolver. Do not add another facade.
- Make Wheypoint branches produce one typed pending revision. Let one finalizer own durability evidence.
- Analyze each bundle archive once. Reuse parsed modules, hashes, command names, and baseline blobs.
- Keep `research-layout` as the only Briesearch layout interface. Remove manual path reconstruction and the `artifact-path research` special case.
- Move `ResearchLayout` beside its only production consumer.
- Replace the custom bundle option parser with `argparse`.

## Cohesion

- The command-summary disagreements are consistent. Skill manifests use `derive_command` with explicit summaries.
- The Age outcome and fallback decisions are consistent. The tree-lock decision is not complete.
- The Briesearch fallback-provider decision is consistent. The ledger lacks one safe URL identity and display contract.
- The documentation path decision is consistent. Runtime-only shared changes no longer trigger documentation builds.
- The Grounding decision is behaviorally consistent. Schema and Mold text validators still duplicate its ownership.
- The migration decision consistently uses `publish_canonical`. Import-time adapter registration still makes migration availability context-dependent.
- The publication digest includes route and schema identity. Tests do not protect that decision, and replay validates less than acceptance.
- The Wheypoint checkpoint decision is coherent on successful writes. Mirror failure breaks retry and durability semantics.
- Mold and hard-cheese name different hard-gate boundaries.
- The release decision file still describes choices that this megamerge supersedes.
- Telemetry has no independent missing-signal finding. URL diagnostics expose secrets, and Wheypoint reports a false failure after state changes.

