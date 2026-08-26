# Enforceable skill boundaries glossary

**HandoffPointer** — canonical JSON commit record revealed last; binds operation, request, source, destination, payload reference, and optional normalization receipt.

**NormalizationReceipt** — typed evidence emitted only when accepted input required bounded normalization or an exact legacy adapter.

**PublishedArtifact** — producer result containing the canonical payload, pointer, and optional receipt.

**AcceptedArtifact** — consumer result exposed only after validating pointer, route, referenced bytes, optional receipt, and canonical payload.

**Agent writer view** — slim agent-authored input accepted through syntax-generous but semantics-strict normalization.

**Canonical artifact** — strict schema-valid persistence and execution form; it receives no fuzzy or semantic coercion.

**Legacy adapter** — deterministic conversion for one exact schema and version, introduced with sunset metadata and removal gates.

**`@bundle_command`** — decorator declaration compiled at build time into a skill's dispatcher and generated command guidance.

**Bundle ownership** — layout-derived ownership from `src/easy_cheese/skills/<skill>` to `skills/<skill>/scripts/<skill>.pyz`; shared runtime code lives under `src/easy_cheese/shared`.
