# ADR: No tokenizer dependency in the skill-size gate

Token estimation is `body_bytes // 4` in pure stdlib. The gate adds no tokenizer library, no model artifact, and no network call.

## Decision record

### ADR-002: Arithmetic estimate over a real tokenizer [status: accepted]

- **Context:** The obvious implementation reaches for `tiktoken`. But `tiktoken` is OpenAI's BPE (`cl100k`/`o200k`), and Claude's tokenizer is not public — so it would deliver a wrong-tokenizer approximation. The accurate option, Anthropic's `count_tokens` endpoint, needs an API key secret, which fails on fork PRs, plus network access in a lint job. Both cost real complexity to sharpen a number whose threshold is itself soft — Anthropic's published figure is a round 5,000, and this repo's tighter 3,600 is a density conversion of a round 150-line figure. Precision on top of an imprecise target is noise on noise.
- **Decision:** Estimate as `len(body_bytes) // 4` using only stdlib. Document the estimate as an estimate wherever the number is reported. Accept that the gate is directionally correct rather than exact.
- **Alternatives:** Vendor `tiktoken` and accept cross-tokenizer error; call Anthropic's `count_tokens` with a CI secret; ship a pinned local tokenizer artifact the way `tools/skill-overlap/` pins its embedding model.
- **Consequences:** The gate stays dependency-free, offline, and fast, and runs identically on fork PRs. It cannot detect a skill that sits within a few percent of its budget, which the ratchet in [[skill-size-ratchet-003]] makes tolerable — budgets only tighten. If Anthropic ever publishes a tokenizer, revisiting this is a contained change to one function.

Related: [[skill-size-ratchet-001]], [[skill-size-ratchet-003]].
