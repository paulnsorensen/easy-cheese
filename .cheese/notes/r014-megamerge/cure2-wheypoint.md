# Wheypoint cure round 2

This node applies the review, edge, and hub findings for the `wheypoint` area.
It edits only files in the `wheypoint` area paths.
It records each fix that belongs to another area as `deferred`.

## Finding table

| Source note | Severity | Finding | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- |
| review-wheypoint.md | blocker | A failed mirror write leaves false durability evidence. | applied | `9a15b5cc` | `src/easy_cheese/skills/wheypoint/commit.py:336-352`; `src/easy_cheese/skills/wheypoint/wheypoint.py:295-323` |
| review-wheypoint.md | blocker | The authoring path drops documented handoff data. | applied in part | `c8a0b8c2`, `4c65cb30` | The command now refuses each unknown key at `src/easy_cheese/skills/wheypoint/wheypoint.py:198-204`. The prose separates the two formats at `skills/wheypoint/SKILL.md:79-121`. |
| review-wheypoint.md | blocker | Typed fields for mode, order, parallel, tasks, and baseline. | deferred: owned by schemas | none | `src/easy_cheese_schemas/wheypoint.py:282-290,542-569` |
| review-wheypoint.md | blocker | The generated projection breaks the shared handoff parser. | applied | `00963235` | `src/easy_cheese/skills/wheypoint/projection.py:38-50,77-120`; `tests/wheypoint/python/test_shared_handoff_seam.py:27-108` |
| review-wheypoint.md | blocker | `cut` can enter a record, but no dispatch contract names it. | applied on this side | `4c65cb30` | `skills/wheypoint/SKILL.md:85,189-193`; `tests/python/test_wheypoint_skill_contract.py:171-192` |
| review-wheypoint.md | blocker | Cheese must also add `cut` to its resume contract. | deferred: owned by cheese | none | `skills/cheese/references/continue-resume.md:109-124` |
| review-wheypoint.md | high | Lint accepts a prior compaction from the same revision or a descendant. | applied | `12cb4002` | `src/easy_cheese/skills/wheypoint/lint.py:464-521`; `tests/wheypoint/python/test_compaction_proof.py:116-176` |
| review-wheypoint.md | high | Contract tests assert prose tokens instead of edge behavior. | applied | `00963235`, `4c65cb30` | `tests/wheypoint/python/test_shared_handoff_seam.py`; `tests/python/test_wheypoint_skill_contract.py:171-192` |
| review-wheypoint.md | medium | Coverage validates only the digest when both pins exist. | applied | `2468f0eb` | `src/easy_cheese/skills/wheypoint/records.py:188-200`; `tests/wheypoint/python/test_storage.py:784-826` |
| review-wheypoint.md | simplification | Choose one canonical handoff format. | applied as separation | `4c65cb30` | See `Disagreements`. |
| review-wheypoint.md | simplification | Replace `lint._Chain` and `_walk_chain` with `lineage.Lineage`. | applied | `12cb4002` | `src/easy_cheese/skills/wheypoint/lint.py:36,244-249` |
| review-wheypoint.md | simplification | Move the mirror transaction behind the commit boundary. | applied in part | `9a15b5cc` | The durability sequence now lives in `commit._finalize`. The transport stays in `wheypoint.py`. See `Disagreements`. |
| review-wheypoint.md | simplification | Replace prose-presence contract tests with behavior tests. | applied | `00963235` | `tests/wheypoint/python/test_shared_handoff_seam.py` |
| edge-cheese-wheypoint.md | blocker | Wheypoint drops fields that Cheese requires. | applied in part | `c8a0b8c2` | This row repeats the intent field row above. The typed fields stay deferred to schemas. |
| edge-cheese-wheypoint.md | blocker | An authoritative Cut handoff has no Cheese route. | applied on this side | `4c65cb30` | The Cheese route stays deferred to cheese. |
| edge-cheese-wheypoint.md | high | The canonical projection violates the Cheese status grammar. | applied | `00963235` | A gated projection now carries a derived reason at `src/easy_cheese/skills/wheypoint/projection.py:77-95`. |
| edge-cheese-wheypoint.md | high | Cheese does not route every legacy status disposition. | applied on this side | `1a7afb54` | The resolver already routes by disposition at `src/easy_cheese/skills/wheypoint/resolve.py:513-516`. The skill prose now says a legacy halt stops at `skills/wheypoint/SKILL.md:185-188`. The Cheese branches stay deferred to cheese. |
| edge-cheese-wheypoint.md | high | Legacy validation rejects the documented Affinage artifact. | applied | `94abd277` | `src/easy_cheese/skills/wheypoint/resolve.py:372-411`; `tests/wheypoint/python/test_legacy_artifact.py:40-85` |
| edge-cheese-wheypoint.md | high | Tests protect prose fragments instead of the edge. | applied | `00963235`, `94abd277` | `tests/wheypoint/python/test_shared_handoff_seam.py`; `tests/wheypoint/python/test_legacy_artifact.py` |
| edge-cheese-wheypoint.md | medium | Cheese overstates the `lint` command. | deferred: owned by cheese | none | `skills/cheese/references/continue-resume.md:54-59` |
| edge-cheese-wheypoint.md | ste100 | Two Cheese prose defects. | deferred: owned by cheese | none | `skills/cheese/SKILL.md:136`; `skills/cheese/references/continue-resume.md:255` |
| edge-schemas-wheypoint.md | blocker | The walker compares no work identifier and no revision number. | applied | `b70ddce3` | `src/easy_cheese/skills/wheypoint/lineage.py:20,94-109`; `tests/wheypoint/python/test_lineage_ancestry.py:35-81` |
| edge-schemas-wheypoint.md | high | Lint accepts an incomplete compaction proof. | applied | `12cb4002` | `src/easy_cheese/skills/wheypoint/lint.py:418-461`; `tests/wheypoint/python/test_compaction_proof.py:63-113` |
| edge-schemas-wheypoint.md | high | Lint accepts a prior compaction that points forward or to itself. | applied | `12cb4002` | This row repeats the prior compaction row above. |
| edge-schemas-wheypoint.md | high | Wheypoint prose omits the schema value `cut`. | applied | `4c65cb30` | `skills/wheypoint/SKILL.md:85,189-193` |
| edge-wheypoint-cook.md | blocker | Wheypoint cannot carry a non-empty Cook baseline. | applied in part | `c8a0b8c2`, `1a7afb54` | The command refuses the key rather than drop it. The prose no longer promises carry-forward at `skills/wheypoint/SKILL.md:151-161`. The typed field stays deferred to schemas. |
| edge-wheypoint-cook.md | high | No test carries a baseline across the seam. | deferred: owned by schemas | none | The seam test needs the typed field the schemas area owns. |
| edge-wheypoint-cook.md | high | The two skill descriptions disagree about the checkpoint route. | applied | `25d43a95` | `skills/wheypoint/SKILL.md:18-23` |
| edge-wheypoint-cook.md | high | The resume command does not match Cook's typed fan contract. | deferred: owned by cheese | none | `skills/cheese/references/continue-resume.md:109-120` |
| hub-shared.md | blocker | Wheypoint projections break the shared handoff grammar. | applied | `00963235` | This row repeats the projection blocker above. |
| hub-shared.md | high | Wheypoint tests do not exercise the shared parser. | applied | `00963235` | `tests/wheypoint/python/test_shared_handoff_seam.py` |
| hub-schemas.md | ok | `wheypoint -> schemas` is sound. | no change needed | none | `src/easy_cheese/skills/wheypoint/records.py:30-39` |
| hub-build.md | untested | `check_bundles.py` does not read `@bundle_command` entries. | deferred: owned by build | none | `scripts/check_bundles.py:461-499` |
| cure2-schemas.md | follow-up | The disagreeing `revision_number` case builds a receipt the model now refuses. | applied | `7dc8cc26` | `tests/wheypoint/python/test_storage.py:399-421` |
| Copilot PR #614 | external | `pending_path()` permits a dot-prefixed stem. | no change needed | none | The guard is already present at `src/easy_cheese/skills/wheypoint/storage.py:191`. |
| Copilot PR #614 | external | A reference file hard-codes a personal path. | no change needed | none | No reference file under `skills/wheypoint/` contains such a path. |

## Applied commits

- `7dc8cc26` test(wheypoint): give the disagreeing revision_number case a valid parent.
- `00963235` fix(wheypoint): render the shared handoff preamble in every projection.
- `9a15b5cc` fix(wheypoint): write the mirror before the record is promoted.
- `b70ddce3` fix(wheypoint): require each parent receipt to be the previous revision.
- `12cb4002` fix(wheypoint): re-derive the whole compaction proof in lint.
- `2468f0eb` fix(wheypoint): validate every coverage pin a claim supplies.
- `94abd277` fix(wheypoint): validate a legacy artifact by the move that reads it.
- `c8a0b8c2` fix(wheypoint): refuse an intent key the record cannot hold.
- `4c65cb30` docs(wheypoint): document cut and the two handoff slug formats.
- `25d43a95` docs(wheypoint): name the checkpoint route and the multi-move owner.
- `1a7afb54` docs(wheypoint): state what a legacy halt and a baseline actually do.
- `892fc7b4` refactor(wheypoint): resolve the intent field names once, with a typed cast.

## Regression tests

- `tests/wheypoint/python/test_shared_handoff_seam.py` parses every generated
  projection with `parse_handoff_slug()`. It covers the `ok` status, the
  `gated` status and its reason, every declared move, an absent artifact, and
  the reason length limit.
- `tests/wheypoint/python/test_lineage_ancestry.py` refuses a parent from
  another work and a revision gap. It keeps a contiguous chain clean.
- `tests/wheypoint/python/test_compaction_proof.py` refuses a false rehydrated
  record digest, an empty entry ledger over a live gate, a self-reference, and
  a descendant reference. It keeps a complete proof clean.
- `tests/wheypoint/python/test_legacy_artifact.py` accepts `PR#<n>` and a pull
  request URL for `next: affinage`. It gates every other artifact form there,
  and keeps the repository file rule for a file move.
- `tests/wheypoint/python/test_checkpoint.py` refuses `mode`, `tasks`,
  `order`, `baseline`, and `durable_flags` in an intent. It also requires a
  failed mirror to leave no promoted record.
- `tests/wheypoint/python/test_storage.py` checks both pins on a dual-pinned
  coverage claim.

## Disagreements

- `review-wheypoint.md` asks for one canonical handoff format and for the
  removal of the legacy authoring instructions. The `resolve` command still
  reads a handwritten legacy note, and `LegacyHandoffSlug` still decodes those
  keys. Deleting the instructions would leave a live code path undocumented.
  I separated the two formats into two labelled sections instead, and I made
  the `checkpoint` command refuse every legacy key.
- `review-wheypoint.md` asks to move the whole mirror transaction behind the
  commit or storage boundary. I moved the ordering rule, which is the part
  that produced the false durability evidence. The request ledger and the note
  path stay in `wheypoint.py`, because both belong to the command surface and
  moving them changes no behaviour.
- The projection now supports an orientation that spans more than one physical
  line. `NextAction.orientation` accepts one, and the old reader silently
  discarded every line after the first. Rule 3 keeps the typed schema
  contract, so the reader now restores the whole value. The shared parser
  reads the first physical line, which is the documented one-line orientation.

## Verification

- `uvx ruff check .` passes.
- `just typecheck` reports zero errors and zero warnings.
- `.github/scripts/validate_skills.py` validates 18 skill files.
- The area suites pass 371 tests.

## Follow-ups

- The schemas area owns the typed fields for `mode`, `order`, `parallel`,
  `tasks`, and `baseline`. Every dropped-field row above depends on them.
- The cheese area owns the `cut` dispatch route, the legacy disposition
  branches, the `lint` prose correction, the `/cook --resume` route, and two
  STE100 defects.
- The build area owns `@bundle_command` discovery in `scripts/check_bundles.py`.
- A non-empty Cook baseline seam test needs the typed baseline field first.

## STE100 status

compliant

- `skills/wheypoint/SKILL.md` complies.
- `skills/wheypoint/references/parallel-handoffs.md` complies.
- `skills/wheypoint/references/commands.md`,
  `skills/wheypoint/references/delta-contract.md`, and
  `skills/wheypoint/references/provenance-fields.md` were not changed and
  still comply.
- This note complies.
