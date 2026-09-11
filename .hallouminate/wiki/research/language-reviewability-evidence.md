# Language readability and reviewability evidence (AI-review era)

Promoted research report. It answers "which languages are easiest to read
and review when a model writes most of the code", and it grounds the
easy-cheese review pipeline's stance on diff size, formatting, typing, and
naming in replicated studies rather than folklore.

## TL;DR

- **No language is decisively "easier to read" across the board.** Python, Ruby, and Quorum win on novice syntax intuitiveness; Go wins on uniform industrial reviewability; compiler-carried languages (Elm, Gleam, Rust, OCaml/F#, strict TypeScript) win on bug prevention per diff by moving whole defect classes off the reviewer.
- **Diff size dwarfs language choice.** Reviewers find 70–90% of defects in 200–400-line reviews; effectiveness collapses past 400–500 LOC/hour. This is the single largest, most robust lever.
- **"Language choice strongly determines defect rate" is folklore.** Ray et al. (FSE 2014) was substantially overturned by Berger et al. (TOPLAS 2019): eleven significant languages shrank to four with an "exceedingly small" effect size.
- **For a Python + TypeScript stack with AI-generated code reviewed by humans**, the Pareto move is strict typed Python (mypy/pyright strict) + Black/Ruff + exhaustiveness linting, and TypeScript strict mode. Not a language switch.

## Key findings

1. **Diff size dwarfs language choice.** SmartBear/Cisco (2,500 reviews, 3.2M LOC): 200–400 LOC over 60–90 minutes yields 70–90% defect discovery. Modern data: ~87% detection for sub-100-line PRs vs ~28% for 1,000+ lines. Google's median change is ~24 lines. Bacchelli & Bird: the reviewer's dominant challenge is comprehension, not defect-spotting.
2. **The headline language-to-quality study was overturned.** Berger, Hollenbeck, Maj, Vitek & Vitek (TOPLAS 2019) reproduced Ray et al. and concluded the results "undermine the conclusions of the original study". Treat any "language X has fewer bugs" claim with deep skepticism.
3. **Static typing's benefit is real but modest and specific.** Gao, Bird & Barr (ICSE 2017): TypeScript and Flow each detect ~15% of already-shipped JavaScript bugs (CI 11.5%–18.5%). Hanenberg's controlled experiments: types help with undocumented APIs, type errors, and maintainability tasks, not semantic errors.
4. **Memory safety is the one place a language change slashes a whole defect class.** ~70% of severe vulnerabilities at Microsoft and Chromium are memory-safety bugs. Google Android (Sept 2024, Nov 2025): memory-safety share fell from 76% (2019) to under 20%; Rust changes had a 4× lower rollback rate and spent 25% less time in code review. Strongest "language improves reviewability" evidence that exists, with selection-bias caveats.
5. **Syntax intuitiveness is measurable and Python is near the top.** Stefik & Siebert (TOCE 2013): Perl and Java were no more accurate than a randomly-keyworded language; Quorum, Python, and Ruby were significantly better. Novice study; do not over-extrapolate to expert review.

## Comprehension research that transfers to review

- **Working memory is the bottleneck.** fMRI studies (Siegmund et al. ICSE 2014; Peitek et al. TSE 2020; Floyd et al. ICSE 2017) show comprehension leans on working memory and language centers. Local reasoning, meaningful identifiers, and low working-memory load make code reviewable, largely independent of language.
- **Readability metrics.** Buse & Weimer (TSE 2010): biggest negative drivers are identifier count, line length, and punctuation density. Scalabrino et al. (TSE 2019): none of 121 metrics individually captures understandability.
- **Identifiers.** Hofmeister, Siegmund & Holt (SANER 2017 / EMSE 2019; 72 professional developers): full-word identifiers gave a **19% increase in defect-finding speed** over single letters or abbreviations. Binkley/Sharif eye-tracking: snake_case recognized faster than camelCase.
- **Indentation.** Miara et al. (CACM 1983): 2–4 spaces maximized comprehension and explained ~36% of quiz-score variance. Python enforces this as syntax.

## Language features that aid or harm review

- **Aid:** exhaustive pattern matching over sum types; no-null/Option types; immutability by default; explicit error values (Go `if err != nil`, Rust `Result`) over exceptions' action-at-a-distance; canonical formatting (gofmt, Black, Prettier, rustfmt) that removes formatting noise from every diff.
- **Harm:** macros/metaprogramming, Ruby DSLs, Scala implicits, operator overloading. Each breaks local reasoning and forces the reviewer to reason non-locally. Go was designed to exclude these; Pike's stated goal was comprehensibility for large teams who "read, debug, modify, review, and deploy code written by everyone else".
- **Density:** Java boilerplate dilutes signal; APL-style density overloads working memory; Python's moderate density sits near the Buse/Weimer sweet spot.

## The AI-era twist

Compiler-checked languages shift review burden onto the type checker: "the type checker reviews the AI". AI-generated code fails differently (plausible-looking, subtly wrong), so compiler guarantees are worth more when the author is a model. Counter-argument, well supported: **reviewer familiarity dominates**, and LLMs generate high-resource languages (Python, JS/TS, Java) far more accurately than Rust, Elm, or Gleam (MultiPL-E gaps; "LLMs Love Python", 2025). Optimal AI-era language = high human reviewability × high LLM accuracy, which points back at typed Python and strict TypeScript, Go for uniform tooling, Rust where memory safety is the point.

Vendor signals (not peer-reviewed): LinearB 2026 reported ~32.7% acceptance for AI PRs vs 84.4% human; Faros AI reported 98% more merged PRs but 91% longer review time on high-AI teams; Greptile reported median PR size up 33% in 2025; CodeRabbit reported ~1.7× more issues per AI PR; GitHub Octoverse 2025 reported 32% faster merges and 28% fewer post-merge defects with AI-assisted review.

## Tiering relative to a Python baseline (backend and tooling, human-reviewed)

| Tier | Languages | Why |
|---|---|---|
| 1 | Typed Python (strict mypy/pyright), TypeScript strict, Go | Match or beat Python on reviewability; keep top LLM accuracy |
| 2 | Kotlin, C#, modern Java, Rust, F#/OCaml | Superior bug prevention by construction; lower familiarity or LLM accuracy |
| 3 | Elm, Gleam | Compiler carries the review; small ecosystems, low LLM accuracy |
| 4 | Untyped JavaScript, DSL-heavy Ruby, Scala, C/C++ | Worse than Python for review |

## Recommendations from the report

1. Cap diffs at 200–400 changed lines and reviews at 60 minutes. Enforce with PR-size bots and stacked PRs for AI-generated code. Highest ROI of anything here.
2. Make canonical formatting non-negotiable (Black + Ruff, Prettier, gofmt).
3. Require the human author of record to annotate non-obvious AI-generated changes before review. Cisco data showed author-prepared reviews had markedly lower defect densities.
4. Strict typed Python and TypeScript strict (`strict: true`, `noUncheckedIndexedAccess`) as deterministic CI gates.
5. Exhaustiveness enforcement: discriminated unions + `assertNever` in TS; exhaustive `match` plus mypy in Python; ban silent fallthrough.
6. Disallow metaprogramming and action-at-a-distance in reviewed code: no monkey-patching, minimal side-effecting decorators, no clever `__getattr__`.
7. Go for standalone tooling where uniformity dominates; Rust only where memory safety or performance is the requirement; Elm/Gleam niche.

## Where this touches easy-cheese

- Diff-size ceiling and author annotation land in `/plate`: `skills/plate/references/topology.md` step 2 (size gates the layout question), `ordinary-pr.md` § Body contract and `.github/PULL_REQUEST_TEMPLATE.md` (non-obvious changes section).
- The comprehension ceiling for reviewers lands in `/age`: `skills/age/SKILL.md` § Output (coverage flag) and `references/fan-out.md` (the router sizes by weighted review surface, which is line-derived but not a raw line count).
- Identifier and exhaustiveness evidence lands in `/age` deslop: `references/dimensions.md` § deslop, `deslop-python.md` § 15, `deslop-typescript.md` § 16.
- Build-for-the-reviewer rules land in `/cook`: `skills/cook/references/tdd-loop.md` § Reviewable by construction and the taste-test Readability lens.
- The language tiering lands in `/mold` Sketch: `skills/mold/references/modes.md` § Language default.

## Caveats

- Evidence quality is uneven. Replicated: diff-size effects, memory-safety class elimination, static typing's ~15% JS-bug catch. Folklore: "functional/typed languages have fewer bugs overall".
- Novice syntax studies are not expert review. Familiarity is a massive confound. No controlled study measures review throughput across languages holding all else equal.
- Vendor AI-era numbers are directional, not authoritative.

_Source: uploaded research artifact "Most Readable and Reviewable Languages in the AI-Review Era: An Evidence-Based Analysis" (ingest hash bef0ae510984cffd), promoted for repository review on 2026-09-05 · Updated: 2026-09-05 · Supersedes: none._
