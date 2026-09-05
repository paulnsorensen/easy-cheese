# Shared cure round 2

This note records every finding from the five source notes for the `shared` area.
The area owns 12 paths plus one new test file, `tests/python/test_shared_migrate.py`.
A finding whose root cause is in another area is `deferred: owned by <area>`.
The owning cure node reads the same source note.

## Findings

| Source note | Severity | Finding | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- |
| review-shared.md | blocker | Quote repair changes payload data | applied before this node | b18b463b | `src/easy_cheese/shared/publication.py:132-168` |
| review-shared.md | blocker | Replay ignores the requested operation identity | applied before this node | 466ce044 | `src/easy_cheese/shared/publication.py:531-543` |
| review-shared.md | high | Pointer input has no size limit | applied | ff4a47a7 | `src/easy_cheese/shared/publication.py:418-433` |
| review-shared.md | high | Publication is not OS independent | applied | 3397d5a8 | `src/easy_cheese/shared/publication.py:301-317,326-352` |
| review-shared.md | high | The taste-test cure keeps two document parsers | deferred: owned by mold | none | `src/easy_cheese/skills/mold/validate_spec.py:223-634` |
| review-shared.md | medium | `compiled_commands` retains placeholder summaries | applied | a5796759 | `src/easy_cheese/shared/bundle_commands.py:86-95` |
| review-shared.md | low | `CorruptLeftoverError` has stale behavior prose | applied | 3f20e2df | `src/easy_cheese/shared/publication.py:89-101` |
| review-shared.md | low | One test name contradicts its assertion | applied | 3f20e2df | `tests/python/test_artifact_path.py:90` |
| review-shared.md | simplification | Delete `compiled_commands` | applied | a5796759 | `src/easy_cheese/shared/bundle_commands.py:86-95` |
| review-shared.md | simplification | Keep one Mold Markdown parser | deferred: owned by mold | none | `src/easy_cheese/shared/taste_test.py:501-802` |
| review-shared.md | simplification | Replace the five constructor protocols | deferred: owned by mold | none | `src/easy_cheese/shared/taste_test.py:37-99` |
| review-shared.md | simplification | Keep payload, receipt, and pointer reads behind one bounded reader | applied | ff4a47a7 | `src/easy_cheese/shared/publication.py:418-450` |
| review-shared.md | simplification | Put OS-specific durability calls behind one adapter | applied | 3397d5a8 | `src/easy_cheese/shared/publication.py:301-352` |
| edge-schemas-shared.md | blocker | Normalization changes valid payload text | applied before this node | b18b463b | `src/easy_cheese/shared/publication.py:132-168` |
| edge-schemas-shared.md | blocker | Replay ignores the schema operation identity | applied before this node | 466ce044 | `src/easy_cheese/shared/publication.py:531-543` |
| edge-schemas-shared.md | high | Legacy source identities can disagree | applied | 0578d964 | `src/easy_cheese/shared/publication.py:497-506` |
| edge-schemas-shared.md | high | The emitted receipt schema accepts null legacy source values | deferred: owned by schemas | none | `tests/schemas/python/goldens/normalization-receipt.json:1` |
| edge-schemas-shared.md | high | Shared reads an unbounded pointer before validation | applied | ff4a47a7 | `src/easy_cheese/shared/publication.py:418-433` |
| edge-schemas-shared.md | high | Shared invents missing Grounding probes | deferred: owned by mold | none | `src/easy_cheese/shared/taste_test.py:681-689` |
| edge-shared-schemas.md | high | Malformed legacy input escapes the error contract | applied | 0578d964 | `src/easy_cheese/shared/migrate.py:100-110` |
| edge-shared-schemas.md | high | A legacy receipt can contain two source identities | applied | 0578d964 | `src/easy_cheese/shared/publication.py:497-506` |
| edge-shared-schemas.md | high | The generated schema permits null legacy source values | deferred: owned by schemas | none | `src/easy_cheese_schemas/contracts.py:637-644` |
| edge-build-shared.md | low | Build repeats the shared command shape | deferred: owned by build | none | `scripts/render_generated_regions.py:47-50` |
| hub-shared.md | blocker | Cook accepts network artifacts from untrusted pointers | applied | ff4a47a7 | `src/easy_cheese/shared/publication.py:436-450` |
| hub-shared.md | high | Cook reads an unbounded pointer before validation | applied | ff4a47a7 | `src/easy_cheese/shared/publication.py:418-433` |
| hub-shared.md | blocker | Age disables the review lock after a Git probe error | deferred: owned by age | none | `src/easy_cheese/skills/age/review_lock.py:50-52` |
| hub-shared.md | blocker | Age permits Git text conversion during review locking | deferred: owned by age | none | `src/easy_cheese/skills/age/review_lock.py:63-67` |
| hub-shared.md | blocker | Age writes the final report before its gated writer call | deferred: owned by age | none | `skills/age/SKILL.md:111-115` |
| hub-shared.md | blocker | Cure replaces its report with a handoff preamble | deferred: owned by cure | none | `skills/cure/SKILL.md:97-99` |
| hub-shared.md | blocker | Setup documents an incomplete closing marker | deferred: owned by easy-cheese-setup | none | `skills/easy-cheese-setup/SKILL.md:38-40` |
| hub-shared.md | blocker | The normal Mold flow bypasses shared publication | deferred: owned by mold | none | `skills/mold/SKILL.md:20-24` |
| hub-shared.md | blocker | Mold exposes caller-selected publication phases | deferred: owned by mold | none | `src/easy_cheese/skills/mold/contract_handlers.py:88-102` |
| hub-shared.md | blocker | Press cannot encode its corrective continuation | deferred: owned by press | none | `skills/press/SKILL.md:123-143` |
| hub-shared.md | blocker | Press dispatch cannot preserve automatic and publication flags | deferred: owned by press | none | `src/easy_cheese/shared/press_route.py:23-27` |
| hub-shared.md | blocker | Wheypoint projections break the shared handoff grammar | deferred: owned by wheypoint | none | `src/easy_cheese/skills/wheypoint/projection.py:68-81` |
| hub-shared.md | high | Affinage omits the `status:` key for halt | deferred: owned by affinage | none | `skills/affinage/SKILL.md:171-183` |
| hub-shared.md | high | Age cannot read the Press findings that it requires | deferred: owned by age | none | `src/easy_cheese/shared/read_handoff_slug.py:19-45` |
| hub-shared.md | high | Age publishes a finding form that the parser rejects | deferred: owned by age | none | `skills/age/SKILL.md:157-166` |
| hub-shared.md | high | Age discards upstream artifact and baseline values | deferred: owned by age | none | `skills/age/SKILL.md:112-116` |
| hub-shared.md | high | Briesearch accepts slugs outside its word rule | deferred: owned by briesearch | none | `src/easy_cheese/skills/briesearch/research_layout.py:37-43` |
| hub-shared.md | high | Cook removes its report body during handoff writing | deferred: owned by cook | none | `skills/cook/SKILL.md:126-160` |
| hub-shared.md | high | Cure cannot emit its documented terminal state | deferred: owned by cure | none | `skills/cure/SKILL.md:153-171` |
| hub-shared.md | high | Setup promises repair but accepts every tenant file | deferred: owned by easy-cheese-setup | none | `src/easy_cheese/shared/hallouminate_setup.py:277-295` |
| hub-shared.md | high | Mold has two source policies for one document | deferred: owned by mold | none | `src/easy_cheese/skills/mold/validate_spec.py:637-645` |
| hub-shared.md | high | Mold publication tests do not protect route identity | deferred: owned by mold | none | `tests/python/test_mold_contract_publish.py:85-105` |
| hub-shared.md | high | Press treats non-test metadata changes as boundary-safe | deferred: owned by press | none | `src/easy_cheese/shared/press_telemetry.py:58-78` |
| hub-shared.md | high | Press has no out-of-contract concern outcome | deferred: owned by press | none | `src/easy_cheese/shared/press_route.py:10-16` |
| hub-shared.md | high | Wheypoint tests do not exercise the shared parser | deferred: owned by wheypoint | none | `tests/python/test_wheypoint_skill_contract.py:156-161` |
| hub-shared.md | medium | Five setup, press, and generated command defects | deferred: owned by easy-cheese-setup, press, build | none | `hub-shared.md` medium list |
| hub-shared.md | low | The Age `review-lock` summary describes the wrong behavior | deferred: owned by age | none | `src/easy_cheese/skills/age/commands.py:127-130` |
| this node | gate | The quote repair test contradicted the structural rule | applied | ff4a47a7 | `tests/python/test_publication_gateway.py:111-118` |
| this node | gate | The shared area reported type-check warnings | applied | 435f166d | `src/easy_cheese/shared/migrate.py:105-110` |
| this node | gate | The Wheypoint storage test left one call result unbound | applied | d4d7f110 | `tests/wheypoint/python/test_storage.py:85` |

## Notes on the deferred hub findings

The hub note names five files under `src/easy_cheese/shared/` that are not in the
12 area paths of this node: `press_route.py`, `press_telemetry.py`,
`read_handoff_slug.py`, `hallouminate_setup.py`, and `write_handoff_artifact.py`.
Rule 1 of this node limits edits to the 12 listed paths. Each of these findings
also requires a matching prose change in the consumer skill. The consumer cure
node owns both sides.

## Disagreements

- The scope rule forbids edits outside the area. The quality gate runs the
  repo-wide type check. One warning in `tests/wheypoint/python/test_storage.py`
  failed that gate. I applied the one-line repair, because no gate can pass
  without it. The Wheypoint contract does not change.

## Verification

- `uvx ruff check .` passes.
- `just typecheck` reports zero errors and zero warnings.
- `pytest tests/python` passes 1334 tests and skips 239 bundle tests.
- The reconcile gate returns status zero.

## STE100 status

compliant

## Follow-ups

- Consolidate the Mold document parser, then remove the synthetic Grounding rows
  in `src/easy_cheese/shared/taste_test.py:681-689`.
- Make the emitted `normalization-receipt` schema reject null legacy source
  values, so JSON Schema consumers match runtime validation.
- Remove `_DocumentedCommand` in `scripts/render_generated_regions.py`.
- Apply the 11 blocker and 14 high hub findings that other areas own.
