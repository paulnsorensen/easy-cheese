# ADR: Own the Snowflake overlap analyzer in easy-cheese

The skill-overlap job is one standalone Rust binary under `tools/skill-overlap/`, reproducing Hallouminate's Snowflake embedding path without depending on Hallouminate's index or storage schema.

## Decision record

### ADR-001: Repository-owned analyzer with Hallouminate parity [status: accepted]

- **Context:** The job needs raw normalized vectors and calibrated cosine scores. Hallouminate's `ground` contract returns rank-fusion retrieval scores, while direct LanceDB reads would couple easy-cheese to private storage. A Python orchestrator plus Rust embedding worker would add a vector transport protocol even though tokenization, embedding, normalization, and cosine must already remain in Rust for exact parity.[^1]
- **Decision:** Build one Rust binary pinned to FastEmbed 5.17.3 and `snowflake/snowflake-arctic-embed-s`. Pin the immutable model revision and checksum every required model artifact. Verify output against Hallouminate golden vectors before analysis.[^2]
- **Alternatives:** Extend Hallouminate with a raw-similarity export; invoke the same model independently from Python; read LanceDB directly; split orchestration between Python and Rust.
- **Consequences:** easy-cheese owns duplicate configuration and a Rust build surface, but gains a stable repository-local CLI and avoids release coordination or storage coupling. Any Hallouminate embedding change must be deliberately mirrored and rebaselined.

Related: [[skill-overlap-ratchet-002]], [[skill-overlap-ratchet-004]].

[^1]: `.github/instructions/python.instructions.md:11-24`
[^2]: https://github.com/paulnsorensen/hallouminate/blob/v0.5.0/crates/hallouminate-adapters/src/embedder.rs#L99-L180
