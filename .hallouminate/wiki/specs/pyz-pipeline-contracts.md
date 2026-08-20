---
source: mold-handshake
slug: pyz-pipeline-contracts
fork_taste:
  draft_sha256: adb68a0e016ca01d522990d9d5bef3c7c692568970254dc17f5848f60b0149c2
  verdict: pass
  correction_round: 2
typed_plan:
  plan_id: plan-pyz-pipeline-contracts-001
  curds: 5
  waves: 3
gate_applicability:
  disposition: red-required
  work_class: behavior
  ui_surface: non-browser
agent_introduced_scope: ["website/", "src/PYTHON_SCRIPTS.md", "ships-as banner"]
entity_referent_bindings:
  - {noun: "SKILLS registry", verdict: Bound, referent: "scripts/build_pyz.py", citation: "scripts/build_pyz.py:57", note: "hand-authored subcommand map; stays authoritative"}
  - {noun: "COMMON_CONSUMERS", verdict: Bound, referent: "scripts/build_pyz.py", citation: "scripts/build_pyz.py:213", note: "gains cook"}
  - {noun: "PACKAGE_TREES", verdict: Bound, referent: "scripts/build_pyz.py", citation: "scripts/build_pyz.py:172", note: "becomes the single schema-consumer authority"}
  - {noun: "script map", verdict: "NEW ENTITY", referent: null, citation: null, note: "generated src/PYTHON_SCRIPTS.md, designed in this spec"}
  - {noun: "import-closure gate", verdict: "NEW ENTITY", referent: null, citation: null, note: "build-time verification pass, designed in this spec"}
  - {noun: "skill-bundle contract test", verdict: "NEW ENTITY", referent: null, citation: null, note: "supersedes the drifted SKILL_SUBCOMMANDS hand copy at tests/python/test_pyz_bundle.py:24"}
---

# pyz pipeline contracts: closure gate, currency enforcement, discoverability, skill↔bundle equality

## Problem

The .pyz build pipeline has four drift classes with no local gate: (1) cross-directory
imports ride on the hand-maintained EXTRA_MODULES dict and a missing entry ships a
bundle that fails only at runtime on a lazy import; (2) nothing local enforces bundle
currency, so "bundles stale" CI failures recur (PR #424); (3) source layout is opaque —
src/ mixes the Astro docs site with Python sources and no generated artifact says
where a subcommand's source lives; (4) the SKILLS registry, skill markdown, and the
test suite's hand-copied SKILL_SUBCOMMANDS dict are three unreconciled registries —
already drifted (3 dead registrations, 9 test-only subcommands, and a documented
common.pyz fallback for cook that is never built).

## Ground evidence

- scripts/build_pyz.py:57 SKILLS, :146 EXTRA_MODULES, :172 PACKAGE_TREES, :184 VENDORED_DEP_BUNDLES, :213 COMMON_CONSUMERS.
- scripts/check_bundles.py:7-16 — CRC-based currency check, CI-only (.github/workflows/build-pyz.yml:44-70); justfile has no local equivalent.
- tests/python/test_pyz_bundle.py:24-66 — hand-copied SKILL_SUBCOMMANDS, missing press red-gate, ultracook curd-block, ultracook age-route (the three dead registrations).
- skills/cook/references/fan-pathway.md:33-35 — documents `common.pyz read_handoff_slug` fallback; COMMON_CONSUMERS excludes cook.
- astro.config.mjs — default srcDir ./src; src/components, src/pages, src/styles, src/content are Astro; the rest is Python.
- Dead registrations (3), no caller in src/**, shared/**, scripts/**, tests/**: press red-gate (registered scripts/build_pyz.py:116; absent from tests/python/test_pyz_bundle.py:55; all red-gate tests target cut.pyz — tests/cut/python/test_cook_red_gate.py:244); ultracook curd-block (registered scripts/build_pyz.py:134; tests/fanout/python/test_curd_block.py:21 imports the module directly; skills/mold/references/curdle.md:269 forbids invoking it); ultracook age-route (registered scripts/build_pyz.py:133; tests/fanout/python/test_age_route_cli.py:24,34 imports the module directly).
- Test-only subcommands (9), invoked solely by tests: mold render_html, ultracook artifact-path/phase_decision/manifest_update/wiring_topo_sort, common slugify/handoff_cli/paths_cli/render_html — each exercised only via tests/python/test_pyz_bundle.py:24-66 (SKILL_SUBCOMMANDS smoke test) or direct module imports (tests/fanout/python/test_manifest_update.py:80, tests/shared/python/test_handoff_cli.py:24-27, tests/shared/python/test_paths_cli.py:22-26, tests/python/test_pyz_bundle.py:627-640).

## Options considered

- Do Nothing — CI keeps catching staleness late; registry drift keeps accreting (already 12 unreconciled entries). Rejected.
- CI auto-commit of rebuilt bundles — zero local friction but bot pushes and rebase noise. Rejected at fork currency-enforcement.
- Internal-flag equality (keep test-only subcommands, mark internal) — registry carries two meanings. Rejected at fork contract-strictness.
- Move Python out of src/ or nest both — 60+ file moves versus one srcDir config key. Rejected at fork restructure-shape.

## Approach

Six settled decisions, one per fork:

1. import-closure-check — after staging each bundle, AST-scan every staged file and
   assert each absolute import (module-level AND function-body) resolves to stdlib, a
   staged module, or a vendored dependency; unresolved imports fail the build naming
   the module and importer.
2. currency-enforcement — wire scripts/check_bundles.py into `just check` and add a
   prek pre-commit hook scoped to src/**, shared/**, and skills/*/phase-contract.yaml
   so stale bundles fail before CI.
3. discoverability-surfaces — generate src/PYTHON_SCRIPTS.md (subcommand → source
   file → bundle table compiled from SKILLS, COMMON_SUBCOMMANDS, EXTRA_MODULES,
   PACKAGE_TREES) with a build_pyz staleness gate exactly like the schema catalog;
   add a one-line ships-as banner to every registered source file, asserted by test;
   add a thin hand-written src/README.md pointing at the generated map.
4. contract-strictness — prune the registry to the prose-referenced set: remove the
   3 dead registrations (press red-gate, ultracook curd-block, ultracook age-route),
   demote the 9 test-only subcommands to direct module tests, then land a
   skill-bundle contract test asserting strict equality between skill-markdown
   references and build_pyz registries, derived from build_pyz.SKILLS (the
   SKILL_SUBCOMMANDS hand copy is deleted, not kept in sync).
5. cook-common-consumer — add cook to COMMON_CONSUMERS so the documented
   common.pyz read_handoff_slug fallback exists on bundle-only hosts; the contract
   test also asserts common.pyz prose references imply consumer membership.
6. restructure-shape — move the Astro site source out of src/ to website/ via the
   srcDir config key (components, pages, styles, content, sidebar.mjs,
   content.config.ts), leaving src/ purely Python.

## Decisions

Consequential (settled at forks): import-closure-check includes function-body
imports; currency-enforcement is just-check-plus-prek-hook; discoverability-surfaces
is map+banner+README on top of restructure; contract-strictness is
prune-to-prose-set with strict equality; cook-common-consumer adds cook rather than
weakening the doc; restructure-shape is site-out-of-src.

Minor (agent-decided): VENDORED_DEP_BUNDLES = tuple(PACKAGE_TREES); named
PHASE_REGISTRY_CONSUMERS constant replaces the inline set at build_pyz.py:454;
memoize the schema-catalog and phase-registry compiles once per process;
scope sys.path insertions with try/finally and drop the _build_schema_contracts
sys.modules registration; src/README.md explains, the generated map enumerates.

## Interface sketches

In scripts/build_pyz.py (import-closure-check, discoverability-surfaces, cook-common-consumer):

```python
def _verify_import_closure(stage: Path, skill: str) -> None:
    """Raise RuntimeError listing every absolute import in staged files,
    module-level and function-body, not resolved by stdlib, stage, or vendor."""

def _render_script_map() -> str:
    """Deterministic markdown for src/PYTHON_SCRIPTS.md: one row per (bundle,
    subcommand, source path), compiled from SKILLS, COMMON_SUBCOMMANDS,
    EXTRA_MODULES, PACKAGE_TREES."""

def _checked_in_script_map_bytes(expected_source: str) -> bytes:
    """Same gate pattern as _checked_in_schema_catalog_bytes; stale map fails build."""

PHASE_REGISTRY_CONSUMERS: frozenset[str]     ... replaces the inline set at build_pyz.py:454
VENDORED_DEP_BUNDLES = tuple(PACKAGE_TREES)  ... derived, no second list
COMMON_CONSUMERS = frozenset({"cure", "age", "ultracook", "cook"})
```

In tests/python/test_skill_contract.py (contract-strictness, cook-common-consumer, discoverability-surfaces banner assertion):

```python
def referenced_subcommands() -> dict[str, frozenset[str]]:
    """Parse skills/**/*.md for '<bundle>.pyz <subcommand>' invocations."""

def test_registry_equals_prose(): ...          strict equality, both directions
def test_common_consumers_cover_prose(): ...   a common.pyz reference implies consumer membership
def test_source_banners(): ...                 every registered source opens with the ships-as banner
```

In the justfile and prek config (currency-enforcement): a `check-bundles` recipe running
python3 scripts/check_bundles.py, added to the `check` dependency chain, plus a local
prek hook `bundle-currency` scoped to files matching src/, shared/, and
skills/*/phase-contract.yaml.

In astro.config.mjs (restructure-shape): `srcDir: './website'` — site sources move to
website/, and src/ is pure Python.

## Test Contracts

| acceptance id | interface | seam | expected_failure | mode |
| --- | --- | --- | --- | --- |
| AC-1 | python3 scripts/build_pyz.py (import-closure-check) | build subprocess exit code and stderr | On main, staging a script whose function-body imports an undeclared cross-directory module builds cleanly; the closure gate must exit nonzero naming the unresolved module and its importer | tracer |
| AC-2 | pytest tests/python/test_skill_contract.py (contract-strictness) | pytest run against build_pyz registries and skills markdown | On main the equality assertion fails: 12 registered subcommands, including press.pyz red-gate, have no skill-markdown reference | tracer |
| AC-3 | python3 skills/cook/scripts/common.pyz read_handoff_slug (cook-common-consumer) | bundle-dispatch subprocess on a bundle-only layout | On main the invocation fails because skills/cook/scripts/common.pyz is never built; after cook joins COMMON_CONSUMERS it resolves and exits 0 on --help | tracer |
| AC-4 | python3 skills/press/scripts/press.pyz red-gate (contract-strictness) | dispatcher usage-rejection exit code | On main press.pyz red-gate dispatches successfully; asserting exit 2 usage-rejection fails until the dead registration is pruned | tracer |
| AC-5 | python3 scripts/build_pyz.py (discoverability-surfaces) | build gate RuntimeError on stale generated file | On main no src/PYTHON_SCRIPTS.md exists; the gate must fail the build until the checked-in map byte-matches the registries | tracer |
| AC-6 | just check (currency-enforcement) | recipe exit code with a deliberately stale committed bundle | On main just check passes with a stale bundle because check_bundles.py is not wired into the recipe | tracer |
| AC-7 | pytest banner assertion in test_skill_contract.py (discoverability-surfaces) | pytest run over registered source files | On main the banner test fails: src/age/age-html-report.py has no ships-as header line | tracer |
| AC-8 | pytest src purity assertion (restructure-shape) | pytest run over src/ tree contents | On main the assertion that src/ contains no Astro sources fails: src/components/Sidebar.astro exists | tracer |

## Acceptance

- AC-1: builds fail with a named unresolved import for any staged module gap, covering function-body imports (import-closure-check).
- AC-2: skill-markdown references and build_pyz registries are provably equal both directions (contract-strictness); the SKILL_SUBCOMMANDS hand copy is gone.
- AC-3: cook ships common.pyz and the documented fallback resolves (cook-common-consumer).
- AC-4: pruned dead subcommands, press red-gate first, are rejected by the dispatcher (contract-strictness).
- AC-5: src/PYTHON_SCRIPTS.md exists, is generated, and stale copies fail the build (discoverability-surfaces).
- AC-6: just check fails on stale bundles locally; the prek hook fires on the scoped paths (currency-enforcement).
- AC-7: every registered source file carries the ships-as banner (discoverability-surfaces).
- AC-8: src/ contains only Python after the site moves to website/ (restructure-shape).

## Quality gates

- `just check` — vendor, tests, lint, and (new) bundle currency.
- `python3 scripts/build_pyz.py && python3 scripts/check_bundles.py` — build with closure + map gates, then currency.
- `pytest tests/python/test_skill_contract.py tests/python/test_pyz_bundle.py` — contract equality, banners, dispatcher behavior.
- `npm run build` (Astro) — site builds from website/ after restructure-shape.

## Typed plan (summary)

Host-validated `plan-pyz-pipeline-contracts-001`: 5 curds / 3 waves — wave 1: pyz-core, currency-enforcement, site-out-of-src; wave 2: banners-and-readme; wave 3: skill-contract-tests. Full typed `PlannerResult`/`CurdPlan` persisted in the durable spec at `~/.local/share/cheese/paulnsorensen-easy-cheese/specs/pyz-pipeline-contracts.md`.

## Non-goals

- Decorator-based subcommand self-registration — tracked as [#437](https://github.com/paulnsorensen/easy-cheese/issues/437), not in this spec (user disposition).
- Gitignoring/relocating the untracked site/ build output — tracked as [#438](https://github.com/paulnsorensen/easy-cheese/issues/438) (user disposition).
