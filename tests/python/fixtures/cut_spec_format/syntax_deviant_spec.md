---
slug: skills-only-spec-format-enforcement
status: approved
source: mold-handshake
created: 2026-08-23
confidence: high
gates_overridden: []
agent_introduced_scope: ["@document_contract", "Section/TableRule", "validate-spec", "normalize", "validate", "_document_rules.py", "intertwine map", "BEGIN GENERATED blocks", "spec-format-valid gate node", "handshake checklist item"]
entity_referent_bindings:
  - {noun: "@contract marker", verdict: bound, referent: "src/easy_cheese_schemas/contracts.py:40-86", citation: "explorer digest", note: "existing decorator pattern being extended"}
  - {noun: "schema catalog", verdict: bound, referent: "src/easy_cheese_schemas/_schema_catalog_compiler.py:1-49", citation: "tilth read", note: "generated dependency-free projection"}
  - {noun: "phase registry", verdict: bound, referent: "src/easy_cheese_schemas/_phase_registry_compiler.py:128", citation: "tilth read", note: "_require_registered_schema already foreign-key-checks URIs"}
  - {noun: "normalize_agent_value", verdict: bound, referent: "src/easy_cheese_schemas/schema_runtime.py:1246-1269", citation: "explorer digest", note: "host-owned field rejection"}
  - {noun: "COMMON_CONSUMERS", verdict: bound, referent: "scripts/build_pyz.py:216", citation: "tilth read", note: "ADR-005 target"}
  - {noun: "@document_contract", verdict: "NEW ENTITY", referent: "NEW ENTITY", citation: "this spec", note: "sibling of @contract for document roots"}
  - {noun: "_document_rules.py", verdict: "NEW ENTITY", referent: "NEW ENTITY", citation: "this spec", note: "generated dependency-free rules module for mold.pyz"}
  - {noun: "cook writer-view reference", verdict: "NEW ENTITY", referent: "skills/cook/references/writer-views.md (NEW ENTITY)", citation: "this spec", note: "created with this work to host cook's generated schema region"}
  - {noun: "schema intertwine map", verdict: "NEW ENTITY", referent: "skills/cheese/references/schema-intertwine.md (NEW ENTITY, wholly generated)", citation: "this spec", note: "user-picked destination under cheese's shared references"}
gate_applicability:
  disposition: red-required
  work_class: behavior
  ui_surface: non-browser
---

# Curdle-time spec-format enforcement and schema awareness for mold and cook

## problem

The mold spec format is prose-template-only: nothing mechanically checks a
spec's frontmatter, required sections, or Test Contracts table before curdle,
so malformed specs reach /cut and /cook and burn correction turns. Separately,
cook's typed steel thread (normalize_agent_value, materialize_planner_result)
has no documented CLI invocation for bundle-only hosts, and no schema is
taught to agents upfront anywhere — agents author payloads blind, then fail
validation they could not have anticipated.

## Goals.

- Mechanical curdle-time validation of mold-produced specs.
- CLI seams on cook.pyz for writer-view normalization and payload validation.
- Agents see the mold-spec and cook writer-view schemas inline at the point
  of instruction, before authoring — fewer wasted correction turns. Further
  schema surfaces extend per-surface with the F001 follow-up.
- The schema intertwine (phase registry × catalog × models) is visible in one
  generated place.

## Non-goals

- Format validation for other prose artifacts (research reports, age
  findings) — deferred follow-up F001.
- Class-ref unification of the phase-transition registry — deferred follow-up
  F002 (phase-registry-untouched fork).
- Full template publication of skill files — deferred follow-up F003 (the D2
  evolution of inline-generated-blocks).
- LLM-judgment validation; a standalone schema-dump CLI subcommand.

## Deferred follow-ups

- **skills-only-spec-format-enforcement-F001** — format validation for other
  prose artifact types (research reports, age findings, culture notes).
  - Destination: github_issue
  - State: created
  - Reference: https://github.com/paulnsorensen/easy-cheese/issues/463 (draft: .cheese/issues/skills-only-spec-format-enforcement-001.md)
- **skills-only-spec-format-enforcement-F002** — investigate class-ref
  unification of the phase-transition registry (fork B).
  - Destination: github_issue
  - State: created
  - Reference: https://github.com/paulnsorensen/easy-cheese/issues/464 (draft: .cheese/issues/skills-only-spec-format-enforcement-002.md)
- **skills-only-spec-format-enforcement-F003** — full template publication of
  skill markdown (D2), if generated regions proliferate.
  - Destination: github_issue
  - State: created
  - Reference: https://github.com/paulnsorensen/easy-cheese/issues/465 (draft: .cheese/issues/skills-only-spec-format-enforcement-003.md)

## Approach

Settled forks reflected here: hand-rolled-validator, scope-mold-cook,
sap-posture, decorator-bindings, build-time-projection,
inline-generated-blocks, phase-registry-untouched, adr-005-ride-along,
curdle-gate-wiring.

Declare the mold spec format as decorated models beside the existing
`@contract` markers (decorator-bindings): a `@document_contract("mold-spec")`
root carrying a frontmatter attrs model plus Section/TableRule declarations,
with cross-field semantic rules as validators. A build-only compiler — the
same family as `_schema_catalog_compiler` — projects the marked models three
ways, each generated at build time and drift-gated in CI
(build-time-projection):

1. `_document_rules.py`, a generated dependency-free rules module staged into
   mold.pyz, consumed by a new hand-rolled Python `validate-spec` subcommand
   (hand-rolled-validator; no mdschema, no jsonish vendoring). The checker
   follows BAML's SAP posture (sap-posture): lenient syntax repair — heading
   case/punctuation fuzz, table whitespace, fence dialects — and strict
   semantic rejection with precise accumulated ERROR: lines. The validator
   blocks curdle through the existing gate mechanism (curdle-gate-wiring):
   handshake.md gains a checklist item — "Spec format valid: validate-spec
   exits 0 on the draft" — which COHERENCE_GATES/gate_id() derives as the
   `spec-format-valid` gate-graph node ordered before curdle. The handshake
   cannot extract a spec that fails validate-spec — this is what makes the
   check curdle-time rather than merely available, per the user directive.
2. Compact BAML-style type blocks rendered into in-place
   `BEGIN GENERATED` regions of skill references (inline-generated-blocks —
   D3): the spec template section of curdle.md and cook's writer-view
   reference — `skills/cook/references/writer-views.md`, a NEW ENTITY
   created with this work — show the real, current schema at the point of
   instruction.
3. A generated intertwine map joining phase registry × schema catalog ×
   models per transition, emitted wholly as
   `skills/cheese/references/schema-intertwine.md` under cheese's shared
   references so every skill's agents can consult it
   (phase-registry-untouched: the URI-string mechanism and its existing
   `_require_registered_schema` compile gate stay exactly as they are —
   A plus C).

Cook gains `normalize` and `validate` subcommands wrapping
`normalize_agent_value` and catalog-contract validation (scope-mold-cook:
this spec covers both the mold markdown surface and cook's JSON surface).
Cook also joins `COMMON_CONSUMERS` and ships `skills/cook/scripts/common.pyz`
per accepted ADR pyz-pipeline-contracts-005 (adr-005-ride-along).

## Decisions

- hand-rolled-validator — the bounded search found no maintained Python
  declarative markdown-schema tool (research part 2, graded speculating);
  mdschema validates declarative shape only, not content-schema inside
  fenced blocks (part 2), so the conditional cross-field contract rules
  would need a Python wrapper regardless — at which point the wrapper is
  the whole tool; jsonish is not standalone (part 4, issue #998).
- scope-mold-cook — user directive: both format layers, mold and cook now,
  other cases later.
- sap-posture — BAML SAP verified at source level: repair syntax, never
  invent meaning; schema taught upfront (research part 4).
- decorator-bindings — extends the proven `@contract` + compile-and-gate
  pattern already in contracts.py.
- build-time-projection — matches every existing generated-artifact gate;
  no runtime discovery.
- inline-generated-blocks — D3: schema inline at point of use without
  turning skill files into build artifacts; D2 deferred.
- phase-registry-untouched — enforcement already exists at
  `_phase_registry_compiler.py:128`; unification adds cost without gain
  (A plus C).
- adr-005-ride-along — cook's new subcommands make it a real common.pyz
  consumer; the accepted ADR lands with this work.
- curdle-gate-wiring — the user directive is curdle-time checking, not an
  available-but-optional CLI; the handshake checklist is the existing gate
  mechanism, so the wiring rides on it rather than inventing a new one.
- _Minor decisions:_ dependency-free-rules-module — mold.pyz consumes the
  generated `_document_rules.py` rather than joining
  PACKAGE_TREES/VENDORED_DEP_BUNDLES (keeps mold light; vetoable
  alternative was vendoring attrs into mold); subcommand names
  `validate-spec`, `normalize`, `validate`; ERROR:-line accumulation and
  exit codes matching validate_wiki.py style; cook's region hosted in new
  `skills/cook/references/writer-views.md`; intertwine map destination
  `skills/cheese/references/schema-intertwine.md` (user pick).

## Acceptance

Settled forks reflected here: hand-rolled-validator, scope-mold-cook,
sap-posture, decorator-bindings, build-time-projection,
inline-generated-blocks, phase-registry-untouched, adr-005-ride-along,
curdle-gate-wiring.

- AC-1: WHEN `mold.pyz validate-spec <path>` runs on a spec that satisfies
  every semantic rule but deviates in surface syntax (heading case or
  trailing punctuation, table whitespace, fence dialect) THE SYSTEM SHALL
  exit 0 with no errors (sap-posture lenient half, via the
  hand-rolled-validator).
- AC-2: WHEN `mold.pyz validate-spec <path>` runs on a spec violating a
  semantic rule (missing required section; acceptance ID absent from or
  duplicated in the Test Contracts table; matrix metadata on a tracer row;
  contract-matrix row missing interface version or matrix rows;
  not-applicable with contracts or without reason) THE SYSTEM SHALL exit 1
  and print one ERROR: line per finding naming the rule and location
  (sap-posture strict half).
- AC-3: WHEN the build runs with decorated document models
  (decorator-bindings) changed but generated projections stale THE SYSTEM
  SHALL fail, and WHEN regeneration runs THE SYSTEM SHALL emit
  `_document_rules.py` deterministically (build-time-projection).
- AC-4: WHEN the build refreshes skill references THE SYSTEM SHALL rewrite
  every `BEGIN GENERATED` region (compact type blocks and the intertwine
  map documenting the untouched phase registry — inline-generated-blocks,
  phase-registry-untouched), fail CI when a region is stale, and SHALL
  leave a fresh rendered region present in both real instruction surfaces:
  curdle.md's spec-template section and
  `skills/cook/references/writer-views.md`.
- AC-5: WHEN `cook.pyz normalize <writer-view.json>` receives a payload
  containing a host-owned field THE SYSTEM SHALL exit 1 naming the exact
  offending field path (scope-mold-cook JSON surface).
- AC-6: WHEN `cook.pyz validate <payload.json> --schema <slug>` receives a
  payload that does not structure against the named catalog contract THE
  SYSTEM SHALL exit 1 with the structuring error, and exit 0 on a
  conforming payload.
- AC-7: WHEN `just build-pyz` completes THE SYSTEM SHALL have cook in
  COMMON_CONSUMERS and produce `skills/cook/scripts/common.pyz`
  (adr-005-ride-along).
- AC-8: WHEN `mold.pyz gate-graph` renders THE SYSTEM SHALL include a
  `spec-format-valid` gate node — derived by COHERENCE_GATES/gate_id()
  from the new handshake.md checklist item — ordered before curdle,
  keeping the hand-rolled-validator on the curdle path
  (curdle-gate-wiring) per the gate-graph/handshake alignment tests.
- AC-9: WHEN the build runs THE SYSTEM SHALL generate
  `skills/cheese/references/schema-intertwine.md` — the intertwine map
  joining phase registry × schema catalog × models per transition
  (phase-registry-untouched) — and fail CI when the generated file is
  stale against the compiled sources.

## Test Contracts

Settled forks reflected here: hand-rolled-validator, scope-mold-cook,
sap-posture, decorator-bindings, build-time-projection,
inline-generated-blocks, phase-registry-untouched, adr-005-ride-along,
curdle-gate-wiring.

| Acceptance ID | Interface referent | Outermost stable seam | Expected failure | Mode | Interface version | Matrix rows |
| --- | --- | --- | --- | --- | --- | --- |
|   AC-1   |  mold.pyz validate-spec CLI   | pytest invoking the built mold.pyz dispatcher as a subprocess | dispatcher exits 2 with unknown-subcommand error because validate-spec is not in the SKILLS registry; test asserts exit 0 on the syntax-deviant fixture | tracer | | |
| AC-2 | mold.pyz validate-spec CLI | pytest invoking the built mold.pyz dispatcher as a subprocess | dispatcher exits 2 with unknown-subcommand error; test asserts exit 1 plus one ERROR: line per seeded semantic violation | tracer | | |
| AC-3 | build_pyz document-schema compile gate | pytest invoking scripts/build_pyz.py compile-and-diff on a fixture tree | ImportError: no _document_rules module and no document compiler exists; test asserts drift detection and deterministic regeneration | tracer | | |
| AC-4 | build generated-region refresher | pytest invoking the refresh entrypoint against the real curdle.md and skills/cook/references/writer-views.md files | refresh entrypoint does not exist (ModuleNotFoundError) and the repo contains zero BEGIN GENERATED regions; test asserts both real surfaces carry a region whose content equals the rendered projection | tracer | | |
| AC-5 | cook.pyz normalize CLI | pytest invoking the built cook.pyz dispatcher as a subprocess | dispatcher exits 2 with unknown-subcommand error because normalize is not registered; test asserts exit 1 naming the host-owned field path | tracer | | |
| AC-6 | cook.pyz validate CLI | pytest invoking the built cook.pyz dispatcher as a subprocess | dispatcher exits 2 with unknown-subcommand error; test asserts exit 1 with structuring error on the nonconforming fixture and exit 0 on the conforming one | tracer | | |
| AC-7 | scripts/build_pyz.py COMMON_CONSUMERS | pytest asserting on build output tree after a full build | skills/cook/scripts/common.pyz is absent because COMMON_CONSUMERS excludes cook; test asserts the file exists and the frozenset contains cook | tracer | | |
| AC-8 | mold.pyz gate-graph CLI | pytest invoking the built mold.pyz gate-graph as a subprocess | COHERENCE_GATES carries no spec-format checklist entry so the rendered graph lacks a spec-format-valid node; test asserts the node exists with an edge ordered before the curdle node (curdle-gate-wiring) | tracer | | |
| AC-9 | build intertwine-map generator | pytest invoking the generator and diffing skills/cheese/references/schema-intertwine.md | generator module does not exist and skills/cheese/references/schema-intertwine.md is absent; test asserts the file is generated deterministically from registry, catalog, and models, and that a seeded stale copy fails the drift gate (phase-registry-untouched) | tracer | | |

## Interface sketches

~~~pseudocode
// fork: decorator-bindings — extends @contract (contracts.py:40-86)
@document_contract("mold-spec")
class MoldSpecDocument:
    frontmatter: MoldSpecFrontmatter          # attrs model incl. gate_applicability
    sections: (Section("Problem"), Section("Goals"), Section("Non-goals"),
               Section("Deferred follow-ups", optional=True),
               Section("Approach"), Section("Decisions"), Section("Acceptance"),
               Section("Test Contracts", table=TableRule(columns=SEVEN_COLUMNS,
                                                         per_row=CONTRACT_RULES)),
               Section("Interface sketches"), Section("Risks"),
               Section("Open questions"), Section("Quality gates"),
               Section("Curds"),
               Section("Reproduction", optional=True),   # Diagnose only
               Section("References", optional=True))
    # full curdle.md template section set — the validator enforces every
    # mandatory section, not a subset
    # cross-field validators: AC coverage exactly-once; tracer rows blank
    # version/matrix cells; contract-matrix rows require both; not-applicable
    # closed class + reason + no contracts

// fork: build-time-projection — build-only compiler family, drift-gated
_document_rules.py            # generated, dependency-free → staged into mold.pyz
                              # (fork: hand-rolled-validator consumes this)
skill references              # fork: inline-generated-blocks — in-place regions:
  <!-- BEGIN GENERATED: schema mold-spec -->   compact BAML-style type block
  <!-- END GENERATED -->
skills/cheese/references/schema-intertwine.md   # fork: phase-registry-untouched —
                              # wholly generated join of registry × catalog ×
                              # models; transition mechanism unchanged
skills/cook/references/writer-views.md          # NEW ENTITY hosting cook's
                              # generated writer-view schema region

// fork: sap-posture — lenient syntax parse, strict semantic errors
mold.pyz validate-spec <spec-path>            -> exit 0 | exit 1 + ERROR: lines

// fork: scope-mold-cook — cook JSON surface
cook.pyz normalize <writer-view.json>         -> canonical JSON | exit 1 + field path
cook.pyz validate <payload.json> --schema <slug> -> exit 0 | exit 1 + structuring error

// fork: adr-005-ride-along
COMMON_CONSUMERS = frozenset({"cure", "age", "ultracook", "cook"})

// fork: curdle-gate-wiring — checklist item -> derived gate node
handshake.md checklist += "Spec format valid: validate-spec exits 0 on the draft"
COHERENCE_GATES/gate_id() derives node "spec-format-valid", edge ordered before curdle
~~~

## Risks

- The lenient-syntax layer applied to file artifacts has no external
  precedent (BAML SAP covers live completions only) — mitigated by keeping
  leniency to enumerated syntax classes with tests per class.
- Generated in-place regions in hand-edited files risk merge friction —
  mitigated by the CI drift gate and small region granularity.
- mold.pyz size growth from _document_rules.py — mitigated by the
  dependency-free projection (no attrs vendored into mold).

## Open questions

- [TBD] exact set of lenient syntax classes accepted at launch (heading
  case/punctuation, table whitespace, fence dialect are committed; more only
  with tests).

## Quality gates

- `just check`: green, including new pytest suites for validate-spec,
  document compiler drift, generated regions, cook normalize/validate, and
  the cook common.pyz build assertion.
- `python3 skills/mold/scripts/mold.pyz validate-spec .cheese/specs/skills-only-spec-format-enforcement.md`: exits 0 (self-hosting check).

## Curds

Host-validated typed PlannerResult (contains the typed CurdPlan at `.plan`;
6 curds / 4 waves; approved at the two-key handshake, digest-bound taste
verdict draft sha256 8ce7bd9c9540d7600248c6176fe9f0b4c3bdee38cf25a3adb870f16f769be493).

```json
{
  "contract_version": {
    "major": "1",
    "minor": "0",
    "schema_uri": "https://schemas.easy-cheese.dev/planner-result"
  },
  "disposition": "complete",
  "plan": {
    "context": {
      "constraints": [
        "scripts/build_pyz.py is edited only by build-pyz-wiring; all SKILLS registration, COMMON_CONSUMERS, staging, and compile-and-diff changes concentrate there.",
        "justfile is edited only by generated-regions-and-intertwine.",
        "Checked-in bundle artifact refreshes are split: skills/cook/scripts/ belongs to build-pyz-wiring; skills/mold/scripts/ belongs to curdle-gate-wiring (the final mold-source curd).",
        "Curds preceding build-pyz-wiring must verify CLI behavior by invoking their source modules directly with the same argv contract the dispatcher execs; dispatcher-level subprocess coverage lands in build-pyz-wiring.",
        "Generated artifacts (_document_rules.py, BEGIN GENERATED regions, schema-intertwine.md, .pyz bundles) are produced only by their compiler or refresh entrypoints, never hand-edited."
      ],
      "invariants": [
        "just check remains green at every curd boundary, including all pre-existing suites.",
        "The phase-transition registry mechanism (URI strings and _require_registered_schema at _phase_registry_compiler.py:128) is unchanged throughout (phase-registry-untouched).",
        "_document_rules.py stays dependency-free (stdlib-only); no attrs or other deps are vendored into mold.pyz.",
        "Validator posture is SAP: lenient repair limited to the enumerated syntax classes with a test per class; strict semantic rejection with accumulated ERROR: lines; repair never invents meaning.",
        "No host-owned identifiers (plan ids, digests) are introduced into agent-authored payloads or schemas."
      ],
      "shared_inputs": []
    },
    "contract_version": {
      "major": "1",
      "minor": "0",
      "schema_uri": "https://schemas.easy-cheese.dev/curd-plan"
    },
    "curds": [
      {
        "criteria": [
          {
            "check": "python3 -m pytest tests/python/test_document_rules_compiler.py -q passes, including a test enumerating the declared section set against the curdle.md template headings.",
            "criterion_id": "curd-ssfe-1/criterion/1",
            "description": "MoldSpecDocument declares every mandatory curdle.md template section (Problem through Curds, optional sections marked) plus the seven-column Test Contracts TableRule and all cross-field semantic rules; this is the schema foundation the AC-1/AC-2 validator and AC-3 projection consume downstream."
          },
          {
            "check": "pytest test_document_rules_compiler.py runs the compiler twice, asserts identical output equal to the checked-in file, and asserts the generated module imports only stdlib names.",
            "criterion_id": "curd-ssfe-1/criterion/2",
            "description": "The compiler emits _document_rules.py deterministically and dependency-free (stdlib-only imports, no attrs), byte-identical to the checked-in src/mold/_document_rules.py."
          }
        ],
        "curd_id": "curd-ssfe-1",
        "dependencies": [],
        "inputs": [],
        "lineage": {
          "identity_action": "new",
          "source_curd_ids": []
        },
        "outcome": "The mold-spec document format is declared as @document_contract-decorated models beside @contract, and a build-only compiler deterministically emits the dependency-free generated module src/mold/_document_rules.py.",
        "outputs": [
          "@document_contract decorator plus MoldSpecDocument/MoldSpecFrontmatter models with Section/TableRule declarations covering the full curdle.md template section set",
          "cross-field semantic validators (AC coverage exactly-once; tracer rows blank version/matrix cells; contract-matrix rows require both; not-applicable closed class plus reason plus no contracts)",
          "_document_rules_compiler.py build-only projection compiler in the _schema_catalog_compiler family",
          "generated, checked-in, dependency-free src/mold/_document_rules.py"
        ],
        "scope": {
          "excluded_paths": [],
          "paths": [
            "src/easy_cheese_schemas/contracts.py",
            "src/easy_cheese_schemas/_document_rules_compiler.py",
            "src/mold/_document_rules.py",
            "tests/python/test_document_rules_compiler.py"
          ]
        }
      },
      {
        "criteria": [
          {
            "check": "python3 -m pytest tests/python/test_validate_spec.py -q \u2014 lenient-class tests invoke the validator CLI (python3 src/mold/validate-spec.py <fixture> with src/mold on the module path, the same argv contract the mold.pyz dispatcher execs) and assert exit 0 with empty error output, one test per lenient class.",
            "criterion_id": "curd-ssfe-2/criterion/1",
            "description": "AC-1: validate-spec exits 0 with no errors on fixtures satisfying every semantic rule while deviating in surface syntax (heading case/trailing punctuation, table whitespace, fence dialect) \u2014 sap-posture lenient half via the hand-rolled validator."
          },
          {
            "check": "pytest test_validate_spec.py semantic-violation tests assert exit 1 and exactly one ERROR: line per seeded finding, and a multi-violation fixture accumulates all ERROR: lines in a single run.",
            "criterion_id": "curd-ssfe-2/criterion/2",
            "description": "AC-2: validate-spec exits 1 and prints one ERROR: line per finding naming the rule and location for each seeded semantic violation (missing required section; acceptance ID absent from or duplicated in the Test Contracts table; matrix metadata on a tracer row; contract-matrix row missing interface version or matrix rows; not-applicable with contracts or without reason) \u2014 sap-posture strict half."
          }
        ],
        "curd_id": "curd-ssfe-2",
        "dependencies": [
          "curd-ssfe-1"
        ],
        "inputs": [],
        "lineage": {
          "identity_action": "new",
          "source_curd_ids": []
        },
        "outcome": "A hand-rolled SAP-posture validate-spec CLI module in src/mold consumes _document_rules and accepts syntax-deviant-but-semantically-valid specs while rejecting semantic violations with accumulated ERROR: lines.",
        "outputs": [
          "validate-spec CLI module (lenient syntax repair for enumerated classes; strict semantic rejection; exit 0/1; one ERROR: line per finding naming rule and location, validate_wiki.py-style)",
          "spec fixtures covering each committed lenient syntax class and each semantic rule violation"
        ],
        "scope": {
          "excluded_paths": [],
          "paths": [
            "src/mold/validate-spec.py",
            "tests/python/test_validate_spec.py",
            "tests/python/fixtures/spec_format"
          ]
        }
      },
      {
        "criteria": [
          {
            "check": "python3 -m pytest tests/python/test_cook_cli.py -q \u2014 normalize tests invoke the CLI module on both fixtures and assert exit codes, the offending field path in stderr, and canonical JSON on stdout.",
            "criterion_id": "curd-ssfe-3/criterion/1",
            "description": "AC-5: normalize on a writer-view payload containing a host-owned field exits 1 naming the exact offending field path; on a clean payload it emits canonical JSON and exits 0 (scope-mold-cook JSON surface)."
          },
          {
            "check": "pytest test_cook_cli.py validate tests assert both exit paths and that the nonconforming run prints the structuring error.",
            "criterion_id": "curd-ssfe-3/criterion/2",
            "description": "AC-6: validate <payload.json> --schema <slug> exits 1 with the structuring error on a payload that does not structure against the named catalog contract, and exits 0 on a conforming payload."
          }
        ],
        "curd_id": "curd-ssfe-3",
        "dependencies": [],
        "inputs": [],
        "lineage": {
          "identity_action": "new",
          "source_curd_ids": []
        },
        "outcome": "Cook gains normalize and validate CLI modules wrapping normalize_agent_value and schema-catalog contract validation with the specified exit-code and error-naming behavior.",
        "outputs": [
          "src/cook/normalize.py CLI wrapping normalize_agent_value (schema_runtime.py:1246) emitting canonical JSON on success",
          "src/cook/validate.py CLI structuring a payload against a named catalog contract via --schema <slug>",
          "payload fixtures: conforming, nonconforming, and host-owned-field writer views"
        ],
        "scope": {
          "excluded_paths": [],
          "paths": [
            "src/cook",
            "tests/python/test_cook_cli.py",
            "tests/python/fixtures/cook_payloads"
          ]
        }
      },
      {
        "criteria": [
          {
            "check": "python3 -m pytest tests/python/test_generated_regions.py -q \u2014 asserts each on-disk region equals the freshly rendered projection, that both named surfaces contain a region, and that a seeded stale copy in a temp tree is detected as drift.",
            "criterion_id": "curd-ssfe-4/criterion/1",
            "description": "AC-4: the refresh entrypoint rewrites every BEGIN GENERATED region; a stale region fails the drift test; a fresh rendered region is present in both real instruction surfaces \u2014 curdle.md's spec-template section and skills/cook/references/writer-views.md."
          },
          {
            "check": "pytest test_generated_regions.py intertwine tests: generator runs twice with byte-identical output equal to the checked-in file, stale copy detected; git diff --stat shows zero changes to src/easy_cheese_schemas/_phase_registry_compiler.py and _compiled_phase_registry.py.",
            "criterion_id": "curd-ssfe-4/criterion/2",
            "description": "AC-9: skills/cheese/references/schema-intertwine.md is generated deterministically from phase registry, schema catalog, and models, and a seeded stale copy fails the drift gate; the phase-transition URI mechanism and _require_registered_schema stay untouched (phase-registry-untouched)."
          }
        ],
        "curd_id": "curd-ssfe-4",
        "dependencies": [
          "curd-ssfe-1"
        ],
        "inputs": [],
        "lineage": {
          "identity_action": "new",
          "source_curd_ids": []
        },
        "outcome": "Build-refreshed BEGIN GENERATED regions render the current mold-spec and cook writer-view schemas inline in curdle.md and the new writer-views reference, and the wholly generated schema-intertwine map exists, all drift-gated.",
        "outputs": [
          "region refresh entrypoint scripts/render_generated_regions.py rendering compact BAML-style type blocks from the decorated document models and cook writer-view schemas",
          "BEGIN GENERATED region in curdle.md's spec-template section",
          "skills/cook/references/writer-views.md (new) hosting cook's generated writer-view schema region",
          "skills/cheese/references/schema-intertwine.md, wholly generated join of phase registry x schema catalog x models per transition",
          "drift-gate tests wired into just check via the justfile"
        ],
        "scope": {
          "excluded_paths": [],
          "paths": [
            "skills/mold/references/curdle.md",
            "skills/cook/references/writer-views.md",
            "skills/cheese/references/schema-intertwine.md",
            "scripts/render_generated_regions.py",
            "tests/python/test_generated_regions.py",
            "justfile"
          ]
        }
      },
      {
        "criteria": [
          {
            "check": "python3 -m pytest tests/python/test_pyz_bundle.py -q \u2014 document-rules drift tests invoke scripts/build_pyz.py compile-and-diff on a fixture tree with a mutated model, assert the build fails on drift, and assert regeneration is byte-deterministic.",
            "criterion_id": "curd-ssfe-5/criterion/1",
            "description": "AC-3: the build fails when decorated document models changed but the generated _document_rules.py projection is stale, and regeneration emits it deterministically via the build compile-and-diff seam."
          },
          {
            "check": "just build-pyz && test -f skills/cook/scripts/common.pyz; pytest test_pyz_bundle.py asserts the frozenset contains cook and the artifact is staged.",
            "criterion_id": "curd-ssfe-5/criterion/2",
            "description": "AC-7: after just build-pyz, COMMON_CONSUMERS contains cook and skills/cook/scripts/common.pyz exists on the build output tree."
          },
          {
            "check": "pytest subprocess tests via build_pyz.cached_bundle run each new subcommand against the fixtures from mold-spec-validator and cook-cli-subcommands and assert the documented exit codes and output shapes.",
            "criterion_id": "curd-ssfe-5/criterion/3",
            "description": "The built dispatchers expose the new subcommands end-to-end: mold.pyz validate-spec and cook.pyz normalize/validate dispatch without exit-2 unknown-subcommand, exercising the AC-1/AC-2/AC-5/AC-6 seams through the registered pyz path."
          }
        ],
        "curd_id": "curd-ssfe-5",
        "dependencies": [
          "curd-ssfe-1",
          "curd-ssfe-2",
          "curd-ssfe-3"
        ],
        "inputs": [],
        "lineage": {
          "identity_action": "new",
          "source_curd_ids": []
        },
        "outcome": "scripts/build_pyz.py registers validate-spec/normalize/validate in the SKILLS dict, stages _document_rules.py into mold.pyz behind a compile-and-diff drift gate, and adds cook to COMMON_CONSUMERS so the build produces skills/cook/scripts/common.pyz.",
        "outputs": [
          "SKILLS entries: mold validate-spec -> validate-spec.py; cook normalize/validate -> src/cook modules",
          "_document_rules.py compile-and-diff drift gate and staging into the mold bundle",
          "COMMON_CONSUMERS = frozenset including cook (adr-005-ride-along) and refreshed skills/cook/scripts/ bundle artifacts including common.pyz"
        ],
        "scope": {
          "excluded_paths": [],
          "paths": [
            "scripts/build_pyz.py",
            "tests/python/test_pyz_bundle.py",
            "skills/cook/scripts"
          ]
        }
      },
      {
        "criteria": [
          {
            "check": "python3 -m pytest tests/python/test_gate_graph.py -q passes, including new assertions that the spec-format-valid node exists, is derived from the checklist label, and precedes curdle in the rendered graph.",
            "criterion_id": "curd-ssfe-6/criterion/1",
            "description": "AC-8: the rendered mold.pyz gate-graph includes a spec-format-valid node derived by COHERENCE_GATES/gate_id() from the new handshake.md checklist item, with an edge ordering it before the curdle node, per the gate-graph/handshake alignment tests (curdle-gate-wiring)."
          },
          {
            "check": "python3 skills/mold/scripts/mold.pyz validate-spec .cheese/specs/skills-only-spec-format-enforcement.md exits 0.",
            "criterion_id": "curd-ssfe-6/criterion/2",
            "description": "Self-hosting quality gate: the refreshed checked-in mold.pyz validates the extracted spec for this work."
          }
        ],
        "curd_id": "curd-ssfe-6",
        "dependencies": [
          "curd-ssfe-5"
        ],
        "inputs": [],
        "lineage": {
          "identity_action": "new",
          "source_curd_ids": []
        },
        "outcome": "The handshake checklist gains the spec-format item, the gate graph derives a spec-format-valid node ordered before curdle, and the checked-in mold bundle artifacts are refreshed with all mold-side changes.",
        "outputs": [
          "handshake.md checklist item: Spec format valid: validate-spec exits 0 on the draft (the handshake cannot extract a spec that fails validate-spec)",
          "COHERENCE_GATES entry in src/mold/gate-graph.py whose gate_id() derivation yields the spec-format-valid node with an edge ordered before curdle",
          "refreshed skills/mold/scripts/mold.pyz and mold.dot carrying validate-spec, _document_rules.py, and the new gate node"
        ],
        "scope": {
          "excluded_paths": [],
          "paths": [
            "skills/mold/references/handshake.md",
            "src/mold/gate-graph.py",
            "tests/python/test_gate_graph.py",
            "skills/mold/scripts"
          ]
        }
      }
    ],
    "digest": "sha256:56163a5bc9d3d84023b0b6df1a71f6cfdb3bb4fb3b276806b8186f032e90eff3",
    "objective": "Enforce mold-spec format at curdle time and expose cook normalization/validation CLIs by projecting decorated document models into a mold validate-spec validator, generated skill-reference schema regions, an intertwine map, build_pyz wiring with drift gates, and a spec-format-valid handshake gate.",
    "parent_plan_ref": null,
    "plan_id": "curdplan-skills-only-spec-format-enforcement-1",
    "revision": 1
  },
  "reason": null,
  "request_id": "planreq-skills-only-spec-format-enforcement-1",
  "unresolved_work": []
}
```
