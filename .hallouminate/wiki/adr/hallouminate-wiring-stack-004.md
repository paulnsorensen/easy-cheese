# ADR: validate_wiki.py hardcodes .hallouminate/wiki/ discovery, ignoring config.toml corpus_paths

**Status:** accepted (2026-07-16)

- **Context:** `.hallouminate/config.toml` declares `corpus_paths = ["skills"]` while its own comment says the wiki under `.hallouminate/wiki/` is the searchable corpus — the value and comment disagree, and whether the daemon indexes the wiki dir implicitly is unverified. The CI validator (#205) needs a file-discovery root.
- **Decision:** The validator discovers `.hallouminate/wiki/**/*.md` directly — the conventions it lints (`wiki-conventions.md`) are defined for that directory, independent of what the daemon indexes.
- **Alternatives:** Parse `corpus_paths` from config.toml — rejected: as written it points at `skills/`, which would lint the wrong tree, and coupling CI to daemon config semantics we haven't verified makes the check fragile.
- **Consequences:** The validator stays correct even if config.toml is wrong or changes; the config discrepancy is tracked separately (side-channel issue `hallouminate-wiring-stack-001`) instead of silently shaping CI behavior.
