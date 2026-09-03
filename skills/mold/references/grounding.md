# Grounding — hallouminate wiki probe

During a `/mold` dialogue, probe the consumer's wiki corpus at **Ground** phase entry if hallouminate is available. Also probe at decision points in any Dialogue mode before asking the next question (see § When to probe). Add matching rationale or ADR entries to the evidence base. If hallouminate is absent, record `hallouminate: absent` in the ledger once. Then continue with only diff and code evidence.

The `grounding-recorded` coherence gate checks that the first structured question does not fire until the ledger carries a probe result. The result contains citations or the explicit absence note. Keep the degrade path cheap but visible.

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
- State the absence once per run if the tool is missing. Write it to the ledger once. Do not repeat it for every question.

## When to probe

Probe at **Ground** phase entry. In other Modes (Shape/Sketch/Grill), probe at decision points before the next question when any condition applies:

- The dialogue is about to decide a consequential fork whose options could have prior rationale (e.g. "why not X").
- Probe when the wiki can possibly answer the next user question. Examples include a settled decision, an ADR, or a recorded convention.
- The dialogue is about to restate rationale for an existing system or module that may have ADRs.
- The spec being molded overlaps with a prior mold session in this repo.

Skip the probe in pure Explore mode when there is no named system. Also skip it in Diagnose mode. Diagnose evidence comes from code and logs, not rationale documents.

Cite hits in that round's decision ledger under `Decided / Asking / [AGENT-DECIDED]`. See `../SKILL.md` § Rules. Put a settled wiki decision under `Decided` and cite its wiki page. Do not reopen it as a new question.

## Prior-evidence fast path

A session can start with prior evidence. Sources include a `/culture` synthesis, a `/briesearch` report, or a `.cheese/notes/<slug>.md` wheypoint. Sources also include an earlier Mold draft or an ADR. Read this evidence once during the Bounds pass. Add each settled item to the ledger. Do not derive settled items again in the parent context.

An item is **covered** only when all three conditions apply:

- **Cited.** The item names evidence that a reader can check. Use a path and symbol, line range, wiki page, or dated URL.
- **Fresh.** The citation resolves at the current HEAD. Probe the evidence again when a referent moved, changed its name, or no longer exists.
- **Decisive.** The item names the decision that it settles. A topic alone does not settle a decision.

Put covered items under `Decided`. Include the source artifact and citation, such as `via: .cheese/notes/<slug>.md`. Run the normal pass for each uncovered item. The fast path skips work. It never skips a gate. It cannot skip the two-key handshake or fresh-context taste test. It also cannot skip a consequential fork that the user did not select.

Always record the intake result. Record `no prior evidence` when the session has no prior evidence. This record satisfies `grounding-recorded`.

## Confidence when absent

If hallouminate is absent and design rationale is central to the current question, cap the result at `speculating`. Note this limit inline. See [`../../cheese/references/optional-plugins.md`](../../cheese/references/optional-plugins.md) for the full degrade contract.
