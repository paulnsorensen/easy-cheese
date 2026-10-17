# Formatting

Use this reference for every artifact that a skill writes to `.cheese/`.
It defines the shared style and citation rules.
It also lists each canonical shape and its owner.

The citation primitive is the standard markdown `[^name]` footnote, which renders natively in GitHub and the easy-cheese Starlight docs site.

## Reader model

Write for an engineer who reads the report without prior context.
The engineer knows the major skills and can open the diff or specification.
The engineer does not know each function location.
Write each claim so this reader can follow it in order.

Consequences for prose:

- In-scope code addresses (`path/to/file.ts:42`, `path/to/file.ts:42-50`) stay inline. They are locations, not citations.
- Out-of-scope evidence (external docs, RFCs, blog posts, vendor pages, commits, PRs, prior `.cheese/` reports, GitHub blob URLs that justify a claim) goes in footnotes. See [Citations](#citations).
- Expand internal shorthand on first use.
  Add a Glossary entry when a long report needs the term again.
- People are referenced as "a review comment on [PR 42](https://github.com/example/repo/pull/42)," not as bare first names.

Test: hand the report to a teammate who has never opened the diff. They can follow every claim and click through to the code when they want to verify. If a sentence reads only to someone who has memorised the diff, it is not finished.

## Open with the answer

Each section starts with its strongest claim.
Do not describe a previous draft or announce later content.
The first sentence gives the section's conclusion.
The remaining sentences give evidence.

During the succinctness pass, read each section's first sentence in isolation. If it does not state a claim, a decision, or a concrete problem, rewrite it.

## House style rules

These rules bind every section, every artifact. The succinctness pass catches violations.

- **No em-dashes.** Use periods, colons, commas, parentheses, or rewrite the sentence. An em-dash usually signals one sentence doing two things.
- **Complete sentences in body prose.** Fragments are fine inside table cells, bullet labels, image captions, and code comments, but not in paragraphs.
- **No filler.** Remove hype, soft openings, and sign-off text.
  The report ends when its content ends.
- **No throat-clearing.** Skip "In this section," "It is important to note," "We will now discuss." Section headers are the transition.
- **No hedging.** "It might be worth considering" becomes a clear position or moves to Open questions.
- **No restated context.** The reader has the diff or the spec. Do not re-state what they can see.
- **No AI vernacular.** These phrases have become tics. They either hedge, inflate, or substitute a cliché for a precise word. Three or more in a report means it is not ready.

  | Phrase | Say instead |
  | --- | --- |
  | load-bearing | critical, essential, required |
  | footgun | dangerous, unsafe by default, easy to misuse |
  | belt-and-suspenders | doubly validated, redundant safety |
  | non-trivial | hard, complex, involved |
  | deep dive | analysis, investigation, reading |
  | leverage (as a verb) | use, apply, build on |
  | let me… (opener) | *(just say the thing; no announcement)* |
  | surface (as a verb) | mention, flag, call out, show |
  | ergonomic / ergonomics | readable, clean, easy to use |
  | guardrails (abstract) | constraints, checks, limits |
  | blast radius (outside incident context) | affected scope, reach, impact |

- **Put calibrated tags on the claim.** Use `` `<certain>` ``, `` `<speculating>` ``, or `` `<don't know>` `` beside the assertion.
  Do not use a blanket disclaimer or place a tag before a fragment.
  Split adjacent claims when their calibrations differ.
  Use the three exact label values.
- **Diagrams over prose.** Prefer Mermaid flowcharts and sequence diagrams for control-flow, data-flow, and integration shapes. Mermaid renders in GitHub and in the Starlight docs site.
- **No semicolons in Mermaid.** Newlines are the convention and render more reliably. One statement per line, no trailing `;`. This includes node definitions, edges, and class assignments.
- **Use pseudocode for algorithms and signatures for data shapes.** Use one form for each idea.
  Do not repeat the same content in both forms.
- **Cite, don't restate.** Link prior `.cheese/` reports, specs, and PRs rather than summarising them, unless the summary is genuinely shorter than the link target. Use the footnote form below.
- **One voice.** When two skills compose into one artifact (e.g. `/age` then `/cure`), the second skill edits toward a single voice rather than appending a second author's tone.

## Citations

Use standard Markdown footnotes for citations.
Use `[^1]` or a kebab-case name such as `[^retry-rfc]`.
Put each definition under the artifact's `## References` heading.

GitHub, the Starlight docs site, and pandoc all render this form as a superscript marker with a back-link to the reference list.

### When to use a footnote vs inline

| Reference | Form | Example |
| --- | --- | --- |
| In-scope code address (file the report is about) | Inline | `src/auth.ts:42-50` |
| In-scope test or fixture | Inline | `tests/auth.test.ts::handles missing token` |
| Out-of-scope code (upstream library, vendor SDK, GitHub blob URL) | Footnote | `Stripe retries idempotent POSTs up to 24 hours.[^stripe-retry]` |
| External docs, RFCs, blog posts, vendor pages | Footnote | ``OIDC `sub` is the durable trust key.[^oidc-core]`` |
| Prior `.cheese/` report, spec, or commit/PR | Footnote | `The press report flagged this gap.[^press-2026-05-12]` |

### Body form

> ✅ "The retry path drops the idempotency key on the second attempt.[^stripe-retry]"
>
> ❌ "The retry path drops the idempotency key on the second attempt ([see Stripe docs](https://stripe.com/...))." (parenthetical hyperlink — fine for inline glossary-style links where the link text carries information, wrong for audit-trail citations)
>
> ❌ "The retry path drops the idempotency key on the second attempt at `src/billing.ts:108`." (file pin **inside** prose — fine here only because the file is in-scope; out-of-scope GitHub blob URLs do not belong inline)

### References section

At the bottom of the artifact, under `## References`:

```markdown
## References

[^stripe-retry]: Stripe API reference, "Idempotent Requests". https://docs.stripe.com/api/idempotent_requests (fetched 2026-05-18).
[^oidc-core]: OpenID Connect Core 1.0, § 2 ID Token. https://openid.net/specs/openid-connect-core-1_0.html#IDToken
[^press-2026-05-12]: `.cheese/press/auth-retry.md` (commit `f9f2973`).
```

Write one footnote per line.
Use absolute URLs.
Add a fetch date when source freshness matters.
For internal artifacts, add a commit or path that remains reproducible after moves.

Use plain parenthetical links only when the link text gives required inline information.
Use footnotes for audit evidence.

## Canonical shapes

Three shapes are written often enough to deserve a single owner each. The owner skill holds the authoritative shape; this file lists the entry point and the cross-cutting rules.

**Corpus location.** Two roots hold artifacts.
Durable specifications and research reports use `$XDG_DATA_HOME/cheese/<project>/`.
The default is `~/.local/share/cheese/<project>/`.
The sanitized project key uses the Git origin or top-level directory name.
Transient pipeline reports and notes stay under `.cheese/`.
This location keeps them with the branch and pull request.
Override the base with `EASY_CHEESE_HOME`.
Override the project key with `EASY_CHEESE_PROJECT`.
`src/easy_cheese/shared/paths.py` owns the path logic.
`artifact_path` builds flat phase paths.
`project_corpus_root` gives `/briesearch` its nested research report root.
This is the target layout.
Some older skill documents still use `.cheese/specs/<slug>.md`.

**External specification contract.** External skills must store specifications through this contract.
Use `artifact-path specs <slug>`.
When the resolver is unavailable, use `.cheese/specs/<slug>.md`.
Private locations such as `.claude/specs/` are invisible to `/cook`, `/mold`, and `/ultracook`.

Portable host-capability wording for helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions lives in [`harness-portability.md`](harness-portability.md).

### Spec

A spec captures a design decision and its rationale before code is written.

- **Owner:** `/mold` → curdle stage.
- **Path:** `$XDG_DATA_HOME/cheese/<project>/specs/<slug>.md` (durable corpus; see **Corpus location** above).
- **Shape:** see `skills/mold/references/curdle.md` § Spec template.
- **Required sections, in order:** frontmatter, title, Problem, Goals, Non-goals, Approach, Decisions, Interface sketches, Risks, Open questions, and Quality gates.
  Add Reproduction only for Diagnose.
  Add References when the document uses external citations.
- **Length budget:** 50–200 lines. Past 300 lines means a decision is buried; split or cut.

Specs that touch existing systems open Approach with one diagram (flowchart or sequence) of the end state before any subsections.

### Findings report

A review skill produces a findings report.
The review skills are `/age`, `/cure`, `/press`, and `/cook` taste-test.
Each skill owns its variant.
The following rules apply to all variants.

- **Owners and paths:**
  - `/age` → `.cheese/age/<slug>.md` (review findings, severity-grouped). See `skills/age/SKILL.md` § Output.
  - `/cure` → `.cheese/cure/<slug>.md` (applied fixes + gate results). See `skills/cure/SKILL.md` § Output.
  - `/press` → `.cheese/press/<slug>.md` (test-hardening report). See `skills/press/SKILL.md` § Output.
  - `/cook` → `.cheese/cook/<slug>.md` (implementation report). See `skills/cook/SKILL.md` § Output.
- **Required preamble.** Every findings report opens with the handoff slug block so downstream skills (`/ultracook`, `/cheese --continue`) can chain without re-parsing. Use the canonical `status:` grammar from the [handback contract](handback-contract.md):

  ```
  status: <canonical status field>
  next: <skill-name> | done
  artifact: <path-to-prior-report-if-any>
  <one-line orientation: what changed or what was reviewed>
  ```

- **Section shape:** each skill's `## Output` section owns its shape.
  Every shape starts with the same handoff slug.
  Add `## References` at the end when the report uses footnotes.
- **Findings format.** Each finding is one bullet:

  ```markdown
  - **[<dimension>]** `path/to/file.ext:42-50` — <what is wrong in plain terms>. <recommendation>.
  ```

  Out-of-scope evidence for the finding goes in a footnote on the recommendation, not inline in the bullet.

- **Length budget:** 50–150 lines. A findings report past 200 lines is doing review and triage at the same time; split the triage into a selection table per `../../cure/references/selection.md`.

### Research report

A research report is the output of `/briesearch` when the question warranted a deep look.

- **Owner:** `/briesearch` synthesis stage.
- **Paths:** return the short form to the caller.
  Write the long form to `$XDG_DATA_HOME/cheese/<project>/research/<slug>/<slug>.md`.
  Store raw bodies under `…/research/<slug>/raw/`.
- **Shape:** see `skills/briesearch/references/synthesis.md` § Output shape.
- **Required sections (long form):** `## Research: <Question>`, Finding, Evidence (claim-level table), Open questions, Confidence, Next step, References.
- **Claim-level evidence table.** One row per material claim, not per source:

  ```markdown
  | Claim | Evidence | Source type | Freshness | Confidence | Caveat |
  | --- | --- | --- | --- | --- | --- |
  | <one-line claim> | <quote, file:line, or URL>[^source-1] | vendor docs / paper / changelog / repo / GitHub / blog | <date checked or "live"> | `certain` / `speculating` / `don't know` | <if any> |
  ```

  The Evidence column uses footnote markers; the URLs and fetch dates live in `## References`. Versioned claims include the version (`Next.js 15.3`, not `Next.js latest`). "Latest as of" claims include an absolute date.

- **Citation verification.** Every URL in the evidence column resolves (HTTP 200 or matched-host redirect) at write time. Mark unreachable links `[unverified]` in the table rather than dropping them. Every quoted line traces back to its source (one-click verifiable for the reader).
- **Length budget:** short form 20–40 lines (returned to caller); long form 100–300 lines including the table and References.

## Succinctness pass

Run the succinctness pass before writing an artifact.
Remove each sentence without useful content.
Add the mechanism for each claim that a reader must verify.

Cut:

- Restated context.
- Hedging language.
- Throat-clearing intros and section preambles.
- Prose duplicating a diagram, code block, or finding bullet.
- Bullets that should be a table, or vice versa.
- Sentence fragments in body prose (rewrite as complete sentences).
- Filler in Open questions, including rhetorical questions the author already answered.
- Em-dashes (target: zero in user-visible text).

Add:

- Add the mechanism behind each architectural or causal claim.
  A reader who has not read the diff must reproduce the conclusion.

### Rewrite examples

Hedge → claim:

> ❌ "It might be worth considering whether the retry path drops the idempotency key."
> ✅ "The retry path drops the idempotency key on the second attempt.[^stripe-retry]"

Throat-clearing → header:

> ❌ "In this section, we'll discuss the trade-offs between approach A and approach B."
> ✅ *(Section header alone. First sentence states the decision.)*

Restated context → cut:

> ❌ "As you can see from the diff, the new `validate()` function is called from three places."
> ✅ *(Delete. The reader has the diff.)*

Prose duplicating a code block → keep one:

> ❌ A paragraph describing the signature, immediately followed by the signature itself.
> ✅ The signature, with a one-line caption only if the caption adds something the signature does not.

Per-shape length budgets live in each shape's `**Length budget:**` bullet under [Canonical shapes](#canonical-shapes). A draft past its budget means the cut is not done.
