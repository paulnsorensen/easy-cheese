# Docs area review

## Verdict

reject

## Blocker

none

## High

- **[spec] The re-review gives two current states.** `.cheese/notes/r014-megamerge/re-review.md:3-5,42-75` reports six residual findings and a reject. Lines 77-86 report every residual as applied. **Fix:** Recompute the summary, residual list, verdict, and follow-ups after the second cure. Keep the first-cure state under a historical heading.
- **[spec] The release records keep superseded limitations active.** `.cheese/issues/477-suggestions.md:41,179-185` schedules command enforcement for release 0.15. `.cheese/plans/release-0-14-decisions.md:228-234` says `research-layout` and the Plate preflight do not exist. Both features exist at `src/easy_cheese/skills/briesearch/commands.py:35-39` and `skills/plate/references/gh-stack.md:50-70`. The same plan records the enforcement work at lines 249-252. **Fix:** Mark the issue record as superseded. Replace each stale limitation with current release behavior. Keep old text only under a historical heading.
- **[spec] The contributor guide describes a rejected command pattern.** `CONTRIBUTING.md:41-45` instructs direct `Command` construction but omits required decorator declarations. `src/easy_cheese/shared/bundle_commands.py:108-127` rejects each command without a matching `@bundle_command` declaration. Current manifests use `derive_command` at `src/easy_cheese/skills/affinage/commands.py:42-54`. **Fix:** Document `@bundle_command`, `derive_command`, and the immutable `COMMANDS` tuple. Explain that the decorator adds metadata and does not create a mutable registry.
- **[spec] The contributor verification procedure omits required tools and suites.** `CONTRIBUTING.md:14-20` omits Node, Corepack, and Rust. `justfile:14-35,111-119` requires Node, Corepack, Cargo, and the full test matrix. `CONTRIBUTING.md:58-73` lists only one Python root and one Bash suite. **Fix:** Document every prerequisite. Use `just test` and `just check` as the canonical verification commands.

## Medium

- **[spec] The dependency notes omit active external contracts.** `.cheese/notes/r014-megamerge/dependency-map.md:182-187` and `docs.md:29-35` name only Brand and the Starlight sidebar. `website/pages/index.astro:2-4` also imports Header and two design style files. `website/content.config.ts:1-3` imports Astro content APIs and Starlight loaders. The workflow also calls five pinned GitHub Actions at `.github/workflows/docs.yml:55-111`. **Fix:** List each external package and GitHub Actions contract in both dependency notes.
- **[deslop] Twenty-two Markdown files violate the required prose tense or voice.** The files appear under STE100 status. Several notes also claim compliance. **Fix:** Give each instruction an active subject. Use the present tense. Keep each sentence within its limit.

## Low

- **[spec] A completed Mold follow-up remains open.** `.cheese/notes/r014-megamerge/hard-cheese.md:28,44` requests a Mold boundary repair. `skills/mold/SKILL.md:121-125` now assigns the check to Plate. **Fix:** Mark the follow-up as complete or remove it.
- **[deslop] One test title uses the wrong verb form.** `tests/js/sidebar-toc.test.mjs:65` says “items does not throw.” **Fix:** Change the title to “undefined TOC items do not throw.”

## Simplifications

- Remove the `isActive` parameter from `injectToc`. Its only production caller reads `entry.isCurrent` at `website/components/Sidebar.astro:11`.
- Replace the manual test list in `CONTRIBUTING.md` with `just test`.
- Keep one current release state. Put superseded decisions under one historical heading.
- Keep one current re-review verdict. Put the first-cure snapshot under one historical heading.
- The website code contains no duplicate helper or superseded implementation.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| docs -> build: `docs:build` | ok | `.github/workflows/docs.yml:85-86` calls the script that `package.json:7-11` defines. |
| build -> docs: generated content and sidebar | ok | `scripts/gen_docs.py:606-646` emits and synchronizes both outputs. `astro.config.mjs:5,11,18` consumes them. |
| skills -> docs: skill pages and references | ok | `scripts/gen_docs.py:402-442,606-611` reads each `SKILL.md` file and folds its references. |
| docs -> `@cheeselord/design` | ok | `website/components/SiteTitle.astro:2-5` and `website/pages/index.astro:2-4,31` use Brand, Header, and styles. `pnpm-lock.yaml:14-19` pins the package. |
| docs -> Astro and Starlight | ok | `website/components/Sidebar.astro:2,8-11` uses supported route fields. `website/content.config.ts:1-6` uses the documented loader and schema. `pnpm-lock.yaml:11-19` pins both packages. |
| docs -> GitHub Pages actions | ok | `.github/workflows/docs.yml:55-111` pins checkout, setup, upload, configuration, and deployment actions by commit. |

## STE100 status

noncompliant

- `.cheese/issues/477-suggestions.md:46` uses the past tense.
- `.cheese/issues/553-suggestions.md:15` uses the past tense.
- `.cheese/notes/r014-megamerge/affinage.md:23-24` uses the past tense.
- `.cheese/notes/r014-megamerge/age.md:30-32` uses the past tense and one long sentence.
- `.cheese/notes/r014-megamerge/briesearch.md:8-9` uses the past tense.
- `.cheese/notes/r014-megamerge/build.md:4-5` uses the past tense.
- `.cheese/notes/r014-megamerge/cheese.md:5-14` uses subjectless past-tense bullets.
- `.cheese/notes/r014-megamerge/cook.md:9-10` uses the past tense.
- `.cheese/notes/r014-megamerge/cure.md:9-10` uses the past tense.
- `.cheese/notes/r014-megamerge/disagreements.md:7-13` uses the past tense.
- `.cheese/notes/r014-megamerge/docs.md:5-11` uses subjectless past-tense bullets.
- `.cheese/notes/r014-megamerge/hard-cheese.md:5-8` uses subjectless past-tense bullets.
- `.cheese/notes/r014-megamerge/holistic-review.md:12-15` uses the past tense.
- `.cheese/notes/r014-megamerge/melt.md:5-9` uses subjectless past-tense bullets.
- `.cheese/notes/r014-megamerge/mold.md:5-9` uses subjectless past-tense bullets.
- `.cheese/notes/r014-megamerge/pasteurize.md:3-5` uses subjectless past-tense bullets.
- `.cheese/notes/r014-megamerge/plate.md:27-33` uses the past tense.
- `.cheese/notes/r014-megamerge/press.md:3-6` uses subjectless past-tense bullets.
- `.cheese/notes/r014-megamerge/re-review.md:46-47` uses the past tense.
- `.cheese/notes/r014-megamerge/schemas.md:8-25` uses the past tense.
- `.cheese/notes/r014-megamerge/wheypoint.md:3-6` uses subjectless past-tense bullets.
- `.cheese/plans/release-0-14-decisions.md:14-36` uses the past tense.

All other prose files comply with the stated checks.

## Follow-ups

- Reconcile the re-review and release records with the final cure state.
- Update the contributor command contract, prerequisites, and test command.
- Complete the external dependency map.
- Rewrite the listed Markdown files with compliant prose.
- Correct the sidebar test title.
