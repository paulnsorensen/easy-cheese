# R014 Megamerge Dependency Map

The map records each cross-area contract from the reconciliation notes.

## Edge summary

| From | To | Contract and change |
| --- | --- | --- |
| affinage | shared | Command dispatch, review routing, paths, and handoff helpers; summaries now come from `derive_command`. |
| affinage | age | Review dimensions, voice, report format, and fan-out remain unchanged. |
| affinage | cheese | Portability, handoff, and agent resolution remain unchanged. |
| affinage | cure | Locked findings use `handoff_context`; publication ownership remains with Affinage. |
| affinage | melt | Conflict resolution remains unchanged. |
| affinage | plate | Publication after approved replies remains unchanged. |
| affinage | hard-cheese | `--hard` reaches the final Plate gate. |
| affinage | pasteurize | Investigation claims can request a reproduction. |
| affinage | briesearch | External evidence requests remain unchanged. |
| age | shared | Commands, locks, reports, paths, severity, and handoff writing use shared helpers. |
| age | schemas | The handoff writer emits canonical handback fields. |
| age | cure | Age emits selected findings and dispatches Cure. |
| briesearch | shared | Commands, artifact paths, and research layout use shared helpers; research layout is new. |
| briesearch | cheese | Question, formatting, routing, and agent resolution remain unchanged. |
| briesearch | age | Voice and sub-agent gate contracts remain unchanged. |
| briesearch | mold | Research can route to Mold without authorizing a design. |
| briesearch | cook | Research can route to Cook without authorizing implementation. |
| build | shared | Generated command references read `Command` and `command_map`. |
| build | schemas | Generated references read models and compiled schema registries. |
| build | skills | Build scripts validate sources and emit command references and bundles. |
| build | docs | Documentation scripts and workflows build and deploy the site. |
| cheese | briesearch | The router dispatches research and internal escalation. |
| cheese | culture | The router dispatches internal reasoning and read-only discussion. |
| cheese | mold | The router dispatches Mold and consumes its specification pointer. |
| cheese | cook | The router dispatches Cook and redirects retired Ultracook calls. |
| cheese | pasteurize | The router dispatches unexplained failures. |
| cheese | press | The router resumes the corrective Cook contract. |
| cheese | age | The router dispatches review work. |
| cheese | cure | The router dispatches selected findings. |
| cheese | plate | The router forwards publication flags. |
| cheese | affinage | The router resumes approved legacy pull request notes. |
| cheese | wheypoint | The router resolves and validates Wheypoint handoffs. |
| cheese | shared | The router uses `resolve_slug`. |
| cheese | schemas | The router consumes the phase registry and contract catalog. |
| cook | shared | Commands and handlers use dispatch, publication, handoff, report, worktree, and path helpers. |
| cook | schemas | Handlers use Curd plans, canonical data, digests, validation, and transition errors. |
| cook | mold | Cook emits planner requests and routes specification failures to Mold. |
| cook | press | Cook emits behavior handoffs and accepts correction results. |
| cook | age | Cook requests curd reviews, taste tests, and final review. |
| cook | cure | Cook sends diagnosis bindings and receives repaired curd results. |
| cook | plate | Cook requests topology checks and carries publication intent. |
| cook | pasteurize | Quality gates can dispatch isolated repair for recorded debt. |
| cook | cheese | Cook uses the handoff gate and continuation route. |
| cure | shared | Commands expose shared slug, handoff, finding, gate, path, and report helpers. |
| cure | schemas | Cure validates `CurdPlan` and emits `CurdResult`. |
| cure | age | Cure requests review for touched paths. |
| cure | mold | Cure reads canonical terms and preserves Mold decisions. |
| cure | plate | Cure requests publication after a clean result. |
| cure | hard-cheese | Cure passes `--hard` through Plate. |
| cure | cheese | Cure uses routing, portability, handback, and handoff contracts. |
| cure | wiki-ingest | Cure records implementation facts after owned publication. |
| docs | build | The workflow calls `docs:build`. |
| docs | external | Site components use Brand and Starlight components. |
| easy-cheese-setup | shared | Commands use the manifest and Hallouminate setup entry points; summaries are now explicit. |
| hard-cheese | shared | CLI and command manifest helpers remain stable; commands now use decorated callables. |
| hard-cheese | age | Shared result voice rules remain unchanged. |
| hard-cheese | cheese | Portability and agent resolution remain unchanged. |
| melt | shared | Commands use decorated callables with `derive_command`. |
| melt | cheese | Code inspection and handoff selection rules remain unchanged. |
| mold | shared | Commands use publication, migration, document, taste-test, and fan-out contracts. |
| mold | schemas | Typed publication and specification validation now require `ui_surface`. |
| mold | cook | Mold emits the approved specification, plans, and durable handoff pointer. |
| mold | cheese | Selection and agent rules remain unchanged. |
| mold | briesearch | Mold requests external evidence. |
| mold | hard-cheese | Mold carries `--hard` to the final review gate. |
| mold | spec-verify | Mold can request an independent specification review. |
| pasteurize | shared | Commands use manifest, route, CLI, and rerun helpers. |
| plate | shared | Publication commands use the shared manifest. |
| plate | age | Age owns code-quality review. |
| plate | gh | GitHub inspection and administration remain outside Plate. |
| plate | wiki-ingest | Wiki updates remain outside Plate. |
| plate | hard-cheese | Plate sends final evidence to the optional gate. |
| plate | cheese | Topology questions use the shared question transport. |
| plate | cook | Repair worktrees use Cook quality-gate rules. |
| press | shared | Commands use manifest, route, and telemetry helpers. |
| press | cook | Press emits corrective continuation and reads the baseline contract. |
| press | age | Press dispatches a green result to Age. |
| press | cheese | Press uses handback, handoff, portability, and code intelligence contracts. |
| schemas | shared | Schemas emit normalization, handoff, adapter, and Grounding contracts. |
| schemas | mold | Schemas emit Mold documents and Grounding records. |
| schemas | wheypoint | Schemas emit Wheypoint compaction and lineage records. |
| schemas | build | The build compiles schemas and reads contract registries. |
| shared | schemas | Migration and publication use contract models and registries. |
| shared | all command skills | Every command area uses the shared command manifest. |
| wheypoint | schemas | Wheypoint consumes record, status, compaction, lineage, and phase contracts. |
| wheypoint | shared | Commands, paths, slugs, and dispatch use shared helpers. |
| wheypoint | cook | Wheypoint carries the Cook baseline contract. |
| wheypoint | build | The manifest supplies bundle and command documentation input. |

## Affinage

- affinage -> shared: Commands use dispatch, review routes, paths, and handoff helpers. Summaries now come from `derive_command`.
- affinage -> age: Review dimensions, voice, reports, and fan-out remain unchanged.
- affinage -> cheese: Portability, handoff, and agent resolution remain unchanged.
- affinage -> cure: Locked findings use `handoff_context`. Affinage keeps publication ownership.
- affinage -> melt: Conflict resolution remains unchanged.
- affinage -> plate: Publication after approved replies remains unchanged.
- affinage -> hard-cheese: `--hard` reaches the final Plate gate.
- affinage -> pasteurize: Investigation claims can request a reproduction.
- affinage -> briesearch: External evidence requests remain unchanged.

## Age

- age -> shared: Commands, locks, reports, paths, severity, and handoff writing use shared helpers.
- age -> schemas: The handoff writer emits canonical handback fields.
- press -> age: Age reads the Press handoff slug.
- cook -> age: Cook dispatches Age and consumes its `next` state.
- affinage -> age: Affinage uses the review flow and fan-out contract.
- age -> cure: Age emits selected findings and dispatches Cure.
- build -> age: The build packages Age and generates its command reference.

## Briesearch

- briesearch -> shared: Commands and paths use shared helpers. PR #582 adds the research layout.
- briesearch -> cheese: Question, formatting, routing, and agent rules remain unchanged.
- briesearch -> age: Voice and sub-agent rules remain unchanged.
- briesearch -> mold: Research can route to Mold without authorizing a design.
- briesearch -> cook: Research can route to Cook without authorizing implementation.
- build -> briesearch: The build packages the runtime and generates command references.

## Build

- build -> shared: Generated command references read `Command` and `command_map`.
- build -> schemas: Generated references read models and compiled registries.
- build -> skills: Build scripts validate sources and emit command references and bundles.
- build -> docs: Documentation scripts and workflows build and deploy the site.

## Cheese

- cheese -> briesearch: The router dispatches research and internal escalation.
- cheese -> culture: The router dispatches internal reasoning and read-only discussion.
- cheese -> mold: The router dispatches Mold and consumes its specification pointer.
- cheese -> cook: The router dispatches Cook and redirects retired Ultracook calls.
- cheese -> pasteurize: The router dispatches unexplained failures.
- cheese -> press: The router resumes the corrective Cook contract.
- cheese -> age: The router dispatches review work.
- cheese -> cure: The router dispatches selected findings.
- cheese -> plate: The router forwards publication flags.
- cheese -> affinage: The router resumes approved legacy pull request notes.
- cheese -> wheypoint: The router resolves and validates Wheypoint handoffs.
- cheese -> shared: The router uses `resolve_slug`.
- cheese -> schemas: The router consumes the phase registry and contract catalog.
- build -> cheese: Generated schema guidance comes from registered contracts.

## Cook

- cook -> shared: Commands and handlers use dispatch, publication, handoff, report, worktree, and path helpers.
- cook -> schemas: Handlers use plans, canonical data, digests, validation, and transition errors.
- mold -> cook: Mold emits the canonical handoff pointer that Cook accepts.
- cook -> mold: Cook emits planner requests and routes specification failures.
- cook -> press: Cook emits behavior handoffs and accepts correction results.
- cook -> age: Cook requests curd reviews, taste tests, and final review.
- cook -> cure: Cook sends diagnosis bindings and receives repaired curd results.
- cook -> plate: Cook requests topology checks and carries publication intent.
- cook -> pasteurize: Quality gates can dispatch isolated repair for recorded debt.
- cook -> cheese: Cook uses the handoff gate and continuation route.
- build -> cook: The build packages commands and generates command references.

## Cure

- cure -> shared: Commands expose shared slug, handoff, finding, gate, path, and report helpers.
- cure -> schemas: Cure validates `CurdPlan` and emits `CurdResult`.
- cook -> cure: Cook provides plans, baseline state, and diagnosis bindings.
- age -> cure: Age provides findings and a locked selection.
- cure -> age: Cure requests review for touched paths.
- affinage -> cure: Affinage invokes Cure and keeps publication ownership.
- cure -> mold: Cure reads canonical terms and preserves Mold decisions.
- cure -> plate: Cure requests publication after a clean result.
- cure -> hard-cheese: Cure passes `--hard` through Plate.
- cure -> cheese: Cure uses routing, portability, handback, and handoff contracts.
- cure -> wiki-ingest: Cure records implementation facts after owned publication.
- build -> cure: The build packages commands and generates command references.

## Docs

- docs -> build: The documentation workflow calls `docs:build`.
- build -> docs: `scripts/gen_docs.py` generates site content.
- skills -> docs: Skill prose supplies generated site content.
- docs -> `@cheeselord/design`: `website/components/SiteTitle.astro` uses `Brand.astro`. `website/pages/index.astro` uses `Header.astro`, `styles/cheeselord.css`, and `styles/flavors/easy-cheese.css`.
- docs -> `@astrojs/starlight`: `website/components/Sidebar.astro` overrides the sidebar component and reads `Astro.locals.starlightRoute`. `website/content.config.ts` uses `docsLoader` and `docsSchema`.
- docs -> `astro`: `website/content.config.ts` uses `defineCollection` from `astro:content`. `website/pages/index.astro` uses `import.meta.env.BASE_URL` and `Astro.site`.
- docs -> GitHub Actions: `.github/workflows/docs.yml` pins `actions/checkout`, `actions/setup-python`, `pnpm/action-setup`, `actions/setup-node`, `actions/configure-pages`, `actions/upload-pages-artifact`, and `actions/deploy-pages` by commit.

## Easy-cheese-setup

- easy-cheese-setup -> shared: Commands use the manifest and Hallouminate setup entry points. Summaries are now explicit.
- build -> easy-cheese-setup: The build packages commands and generates command references.
- build -> easy-cheese-setup: The installer calls `global --apply` through the bundle.

## Hard-cheese

- hard-cheese -> shared: CLI and command helpers remain stable. Commands now use decorated callables.
- cheese -> hard-cheese: Cheese passes `--hard` to Plate.
- mold -> hard-cheese: Mold passes `--hard` to the final gate.
- cook -> hard-cheese: Cook carries `--hard` through later phases.
- press -> hard-cheese: Press passes `--hard` to Age.
- age -> hard-cheese: Age passes `--hard` through Cure and Plate.
- cure -> hard-cheese: Cure passes `--hard` to Plate.
- plate -> hard-cheese: Plate sends final verified artifacts.
- hard-cheese -> age: Shared voice rules remain unchanged.
- hard-cheese -> cheese: Portability and agent rules remain unchanged.
- build -> hard-cheese: The build packages the runtime and generates command references.

## Melt

- melt -> shared: Commands use decorated callables with `derive_command`.
- melt -> cheese: Code inspection and handoff selection rules remain unchanged.
- build -> melt: The build packages the runtime and generates command references.

## Mold

- mold -> shared: Commands use publication, migration, document, taste-test, and fan-out contracts.
- mold -> schemas: Typed publication and validation now require `ui_surface`.
- mold -> cook: Mold emits the approved specification, plans, and durable handoff pointer.
- cheese -> mold: Cheese routes tier-one mini-spec work to Mold.
- mold -> cheese: Selection and agent rules remain unchanged.
- mold -> briesearch: Mold requests external evidence.
- culture -> mold: Culture can supply provenance before Mold writes a mini-spec.
- mold -> hard-cheese: Mold carries `--hard` to the final review gate.
- mold -> spec-verify: Mold can request an independent specification review.
- build -> mold: The build packages the runtime and generates command references.

## Pasteurize

- pasteurize -> shared: Commands use manifest, route, CLI, and rerun helpers.
- build -> pasteurize: The build packages the command manifest.

## Plate

- plate -> shared: Publication commands use the shared manifest.
- plate -> age: Age owns code-quality review.
- plate -> gh: GitHub inspection and administration remain outside Plate.
- plate -> wiki-ingest: Wiki updates remain outside Plate.
- plate -> hard-cheese: Plate sends final evidence to the optional gate.
- plate -> cheese: Topology questions use the shared question transport.
- plate -> cook: Repair worktrees use Cook quality-gate rules.

## Press

- press -> shared: Commands use manifest, route, and telemetry helpers.
- press -> cook: Press emits corrective continuation and reads the baseline contract.
- press -> age: Press dispatches a green result to Age.
- press -> cheese: Press uses handback, handoff, portability, and code intelligence contracts.
- ultracook -> press: The retired compatibility route writes the Press handoff and stops.
- build -> press: The build packages the command manifest.

## Schemas

- schemas -> shared: Schemas emit normalization, handoff, adapter, and Grounding contracts.
- shared -> schemas: Migration and publication use contract models and registries.
- schemas -> mold: Schemas emit Mold documents and Grounding records.
- mold -> schemas: Mold validates specifications with those contracts.
- schemas -> wheypoint: Schemas emit Wheypoint compaction and lineage records.
- wheypoint -> schemas: Wheypoint consumes compaction and lineage contracts.
- build -> schemas: The build compiles schemas and reads contract registries.
- schemas -> build: The Just recipe installs schema requirements before compilation.

## Shared

- schemas -> shared: Generated document rules contain the Grounding rules.
- shared -> schemas: Migration and publication use models and transition registries.
- build -> shared: Generated command references read `Command.summary`.
- affinage -> shared: Commands use the shared manifest.
- age -> shared: Commands use the shared manifest.
- briesearch -> shared: Commands and research layout use shared helpers.
- cook -> shared: Commands and contract handlers use shared helpers.
- cure -> shared: Commands use the shared manifest.
- easy-cheese-setup -> shared: Commands use `Command` and `dispatch`.
- hard-cheese -> shared: Commands use the shared manifest.
- melt -> shared: Commands use the shared manifest.
- mold -> shared: Commands and validators use publication, migration, document, and taste-test contracts.
- pasteurize -> shared: Commands use the shared manifest.
- plate -> shared: Commands use the shared manifest.
- press -> shared: Commands use manifest, route, and telemetry contracts.
- wheypoint -> shared: Commands and runtime modules use shared declarations and paths.

## Wheypoint

- wheypoint -> schemas: The runtime consumes records, status, compaction, lineage, and phase contracts.
- wheypoint -> shared: Commands, paths, slugs, and dispatch use shared helpers.
- cheese -> wheypoint: Cheese resolves and validates handoffs before resume.
- wheypoint -> cook: Wheypoint carries the Cook baseline contract.
- wheypoint -> build: The manifest supplies bundle and command documentation input.
