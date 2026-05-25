# Formatting

Use this reference for any artifact a skill writes to `.cheese/` — specs, findings reports (`/age`, `/cure`, `/press`, `/cook`), and research reports (`/briesearch`). The house style and citation rules are shared; the three canonical shapes are listed at the bottom and cross-referenced to the skill that owns each one.

The citation primitive is the standard markdown `[^name]` footnote, which renders natively in GitHub and the easy-cheese mkdocs site (the `footnotes` extension is enabled in `mkdocs.yml`).

## Reader model

Write for an engineer who picks the report up cold. They know the major skills exist, they have the diff or the spec open in another tab, and they have not memorised which function lives in which file. Every claim must read top-to-bottom for that reader.

Consequences for prose:

- In-scope code addresses (`path/to/file.ts:42`, `path/to/file.ts:42-50`) stay inline. They are locations, not citations.
- Out-of-scope evidence (external docs, RFCs, blog posts, vendor pages, commits, PRs, prior `.cheese/` reports, GitHub blob URLs that justify a claim) goes in footnotes. See [Citations](#citations).
- Internal shorthand (a skill name, a cheese term, an acronym) gets expanded on first use or earns a Glossary entry when the report is long enough to need one.
- People are referenced as "a review comment on [PR 42](URL)," not as bare first names.

Test: hand the report to a teammate who has never opened the diff. They can follow every claim and click through to the code when they want to verify. If a sentence reads only to someone who has memorised the diff, it is not finished.

## Open with the answer

Each section starts with its strongest claim. No "the previous draft did X." No "this section will do Y." No "we'll explore the trade-offs below." The first sentence of a section is the section's conclusion in compressed form; the rest is evidence.

During the succinctness pass, read each section's first sentence in isolation. If it does not state a claim, a decision, or a concrete problem, rewrite it.

## House style rules

These rules bind every section, every artifact. The succinctness pass catches violations.

- **No em-dashes.** Use periods, colons, commas, parentheses, or rewrite the sentence. An em-dash usually signals one sentence doing two things.
- **Complete sentences in body prose.** Fragments are fine inside table cells, bullet labels, image captions, and code comments, but not in paragraphs.
- **No filler.** Cut hype, soft openings, and sign-off appendixes such as "hope this helps" or "let me know if you need anything else." The report ends when the content ends.
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

- **Calibrated tags sit on the claim, not at sentence boundaries.** Use `` `<certain>` ``, `` `<speculating>` ``, or `` `<don't know>` `` inline next to the specific assertion. Never as a blanket disclaimer at the top of a section. Never in front of a fragment. Adjacent claims with different calibrations split into two sentences, each carrying its own tag. The three tokens are exact label values: write them verbatim, never as synonyms.
- **Diagrams over prose.** Prefer Mermaid flowcharts and sequence diagrams for control-flow, data-flow, and integration shapes. Mermaid renders in GitHub and in the mkdocs site.
- **No semicolons in Mermaid.** Newlines are the convention and render more reliably. One statement per line, no trailing `;`. This includes node definitions, edges, and class assignments.
- **Pseudocode for algorithms, signatures for data shapes.** Pseudocode is clearest when the point is the algorithm; real signatures (typed function declarations, schemas) are clearest when the point is the data shape. One form per idea; the same content does not appear in two.
- **Cite, don't restate.** Link prior `.cheese/` reports, specs, and PRs rather than summarising them, unless the summary is genuinely shorter than the link target. Use the footnote form below.
- **One voice.** When two skills compose into one artifact (e.g. `/age` then `/cure`), the second skill edits toward a single voice rather than appending a second author's tone.

## Citations

The citation primitive is the standard markdown footnote: `[^1]` (or any kebab-case name like `[^retry-rfc]`), with the definition at the bottom of the artifact under a `## References` heading.

GitHub, the mkdocs site, and pandoc all render this form as a superscript marker with a back-link to the reference list.

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

One line per footnote. URLs absolute. For external sources, include a fetch date when freshness matters ("as of 2026-05-18"). For internal artifacts, include the commit hash or the path so the citation is reproducible even after the artifact moves.

Reserve plain parenthetical hyperlinks (`see [name](URL)`) for cases where the link text itself carries information the reader needs inline — glossary terms, named proposals, vendor doc titles. Audit-trail evidence uses footnotes.

## Canonical shapes

Three shapes are written often enough to deserve a single owner each. The owner skill holds the authoritative shape; this file lists the entry point and the cross-cutting rules.

**Corpus location.** Two roots hold artifacts. Durable, project-scoped knowledge — specs and research reports — anchors at a stable XDG path so it survives branch switches and clones and stays out of git: `$XDG_DATA_HOME/cheese/<project>/` (default `~/.local/share/cheese/<project>/`), where `<project>` matches the git repository (origin `owner/repo`, sanitized; falls back to the toplevel dir name). Transient pipeline handoffs — `cook`/`press`/`age`/`cure` reports, `notes`, `hard` — stay repo-local under `.cheese/` so they travel with the branch and surface in the PR. Override the base with `EASY_CHEESE_HOME` and the project key with `EASY_CHEESE_PROJECT`. The path math is owned by `shared/scripts/paths.py`: `artifact_path` builds flat-phase paths (specs, transient reports), and `project_corpus_root` gives the durable root that `/briesearch` composes the nested `research/<slug>/<slug>.md` report path under. This is the target layout: skills are being migrated onto these helpers, and per-skill docs that still name `.cheese/specs/<slug>.md` predate the durable/transient split and have not yet been updated.

### Spec

A spec captures a design decision and its rationale before code is written.

- **Owner:** `/mold` → curdle stage.
- **Path:** `$XDG_DATA_HOME/cheese/<project>/specs/<slug>.md` (durable corpus; see **Corpus location** above).
- **Shape:** see `skills/mold/references/curdle.md` § Spec template.
- **Sections (required, in order):** frontmatter, `# <Title>`, Problem, Goals, Non-goals, Approach, Decisions, Interface sketches, Risks, Open questions, Quality gates, Reproduction (Diagnose only), References (when out-of-scope citations are used).
- **Length budget:** 50–200 lines. Past 300 lines means a decision is buried; split or cut.

Specs that touch existing systems open Approach with one diagram (flowchart or sequence) of the end state before any subsections.

### Findings report

A findings report is the output of a review skill — `/age`, `/cure`, `/press`, or `/cook` taste-test. Each skill owns its own variant; the cross-cutting rules below apply to all of them.

- **Owners and paths:**
  - `/age` → `.cheese/age/<slug>.md` (review findings, severity-grouped). See `skills/age/SKILL.md` § Output.
  - `/cure` → `.cheese/cure/<slug>.md` (applied fixes + gate results). See `skills/cure/SKILL.md` § Output.
  - `/press` → `.cheese/press/<slug>.md` (test-hardening report). See `skills/press/SKILL.md` § Output.
  - `/cook` → `.cheese/cook/<slug>.md` (implementation report). See `skills/cook/SKILL.md` § Output.
- **Required preamble.** Every findings report opens with the handoff slug block so downstream skills (`/ultracook`, `/cheese --continue`) can chain without re-parsing:

  ```
  status: ok | halt: <one-line reason>
  next: <skill-name> | done
  artifact: <path-to-prior-report-if-any>
  <one-line orientation: what changed or what was reviewed>
  ```

- **Section shape:** owned by each skill's `## Output` section (see the per-owner paths above). The cross-cutting rule is that whatever sections an owner template defines, the same handoff slug sits at the top and a `## References` block sits at the bottom whenever footnotes are used.
- **Findings format.** Each finding is one bullet:

  ```markdown
  - **[<dimension>]** `path/to/file.ext:42-50` — <what is wrong in plain terms>. <recommendation>.
  ```

  Out-of-scope evidence for the finding goes in a footnote on the recommendation, not inline in the bullet.

- **Length budget:** 50–150 lines. A findings report past 200 lines is doing review and triage at the same time; split the triage into a selection table per `skills/cure/references/selection.md`.

### Research report

A research report is the output of `/briesearch` when the question warranted a deep look.

- **Owner:** `/briesearch` synthesis stage.
- **Paths:** short form returned inline to the caller; long form written to the durable corpus (see **Corpus location** above) at `$XDG_DATA_HOME/cheese/<project>/research/<slug>/<slug>.md` with raw bodies under `…/research/<slug>/raw/`.
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

Every artifact runs the pass before it is written to disk. The pass runs in two directions: every sentence carries weight or it goes, and every reader-required claim names its mechanism or one gets added.

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

- The mechanism behind any architectural or causal claim where the prose leaves the reader to guess. A reader who has not read the diff should be able to reproduce the conclusion from the report.

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
