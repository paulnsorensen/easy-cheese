# Grounding — hallouminate wiki probe

Throughout a `/mold` dialogue — at **Ground** phase entry and at decision points in any Dialogue mode (see § When to probe) — if hallouminate is available, probe the consumer's wiki corpus before asking the user the next question. Fold any matching rationale or ADR entries into the evidence base. If hallouminate is absent, record `hallouminate: absent` in the ledger once and continue with diff + code evidence only.

The record is what the `grounding-recorded` coherence gate checks: the first structured question does not fire until the ledger carries a probe result — citations, or that explicit absence note. The degrade path stays cheap; it may not stay invisible.

## Probe shape

Mirrors the wiki probe pattern from the detect-and-degrade contract in [`../../cheese/references/optional-plugins.md`](../../cheese/references/optional-plugins.md):

```pseudocode
ground_wiki(topic):
  # 1. Check hallouminate availability.
  if "mcp__hallouminate__list_corpora" not in available_tools:
    note once: "OPTIONAL MCP ABSENT: hallouminate not loaded. Falling back to diff + code evidence only."
    return []

  # 2. Find the consumer's wiki corpus (dynamic; their repo, not ours).
  corpora = mcp__hallouminate__list_corpora()
  wiki = first(c for c in corpora if c.startswith("repo:") and c.endswith(":wiki"))
  if not wiki:
    return []   # no wiki configured; skip silently

  # 3. Ground the topic.
  results = mcp__hallouminate__ground(query=topic, corpus=wiki, limit=5)
  return results
```

- The corpus name comes from `list_corpora`, never a literal string — that is the portability invariant (the consumer's repo, not easy-cheese's).
- If `list_corpora` is unreachable or returns no wiki corpus, fall back to code evidence. Never block the dialogue on the probe.
- State the absence once per run if the tool is missing, and write it to the ledger once; do not repeat it on every question.

## When to probe

Probe at **Ground** phase entry and, in the other Modes (Shape/Sketch/Grill), at any decision point — before generating the next question — when any of these are true:

- The dialogue is about to decide a consequential fork whose options could have prior rationale (e.g. "why not X").
- The next question to the user is one the wiki may already answer (a settled decision, an ADR, a recorded convention).
- The dialogue is about to restate rationale for an existing system or module that may have ADRs.
- The spec being molded overlaps with a prior mold session in this repo.

Skip the probe for pure Explore mode (no named system) and for Diagnose mode (evidence comes from code/logs, not rationale docs).

Cite hits in that round's decision ledger (`Decided / Asking / [AGENT-DECIDED]` — see `../SKILL.md` § Rules): a settled decision found in the wiki lands under `Decided` with its wiki page cited, not reopened as a fresh question.

## Prior-evidence fast path

A session can start with prior evidence. Sources include a `/culture` synthesis, a `/briesearch` report, or a `.cheese/notes/<slug>.md` wheypoint. Sources also include an earlier Mold draft or an ADR. Read this evidence once during the Bounds pass. Add each settled item to the ledger. Do not derive settled items again in the parent context.

An item is **covered** only when all three conditions apply:

- **Cited.** The item names evidence that a reader can check. Use a path and symbol, line range, wiki page, or dated URL.
- **Fresh.** The citation resolves at the current HEAD. Probe the evidence again when a referent moved, changed its name, or no longer exists.
- **Decisive.** The item names the decision that it settles. A topic alone does not settle a decision.

Put covered items under `Decided`. Include the source artifact and citation, such as `via: .cheese/notes/<slug>.md`. Run the normal pass for each uncovered item. The fast path skips work. It never skips a gate. It cannot skip the two-key handshake or fresh-context taste test. It also cannot skip a consequential fork that the user did not select.

Always record the intake result. Record `no prior evidence` when the session has no prior evidence. This record satisfies `grounding-recorded`.

## Confidence when absent

If hallouminate is absent and design rationale is central to the question at hand, cap at `speculating` and note it inline. See [`../../cheese/references/optional-plugins.md`](../../cheese/references/optional-plugins.md) for the full degrade contract.
