# References

Long-form architectural and engineering references that ship alongside easy-cheese. Source-of-truth documents that the workflow skills can cite or load on demand. Workflow skills (`/mold`, `/cook`, `/age`, `/cure`, `/culture`) reference these directly when slice boundaries, dependency direction, or growth decisions come up.

## Sliced Bread Architecture

| Document | When to load |
|---|---|
| [sliced-bread.md](./sliced-bread.md) | **Always.** Language-agnostic rationale, growth pattern, anti-patterns, boundary decisions, dependency-direction quick-check, review checklist. Start here. |
| [sb/practice.md](./sb/practice.md) | When the task is a *judgement call*, not a build. Load if the prompt involves: extracting or keeping near-duplicate models across slices, deciding on read/write asymmetry (CQRS), integrating with an external API or legacy system (anti-corruption layer), choosing a per-slice testing approach, or graduating a slice to a workspace package, library, or service. Skip for routine feature work inside an existing slice — `sliced-bread.md` is enough. |
| [sb/attribution.md](./sb/attribution.md) | When reviewers question the architectural choices. Predecessor lineage (VSA, Hexagonal, Screaming, Clean, Onion, DDD), what's inherited, what's deliberately dropped, terminology distinctions (especially "shared kernel" vs "common leaf"). |
| [sb/rust.md](./sb/rust.md) | When the codebase is Rust. Module privacy, the `foo.rs` + `foo/` facade convention, `pub use` re-exports, workspaces. |
| [sb/go.md](./sb/go.md) | When the codebase is Go. The `internal/` directory as compile-time enforcement, package = directory, `go.work` workspaces. |
| [sb/ts.md](./sb/ts.md) | When the codebase is TypeScript. `package.json` `"exports"` maps as the modern facade, why barrel files are now anti-pattern, project references, monorepo workspaces. |
