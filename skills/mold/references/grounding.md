# Grounding — hallouminate wiki probe

Probe the current repository's wiki corpus at **Ground** phase entry. Probe only when hallouminate is available. Also probe at decision points in any Dialogue mode before you ask the next question. See § When to probe. Add each matching rationale entry or ADR entry to the evidence base.

Record one named probe outcome in the ledger for every probe. The outcome is `hit`, `miss`, or `unavailable`. Record `hallouminate: absent` once when the tool is missing. Then continue with diff evidence and code evidence only.

The `grounding-recorded` coherence gate blocks the first structured question until the ledger carries a probe outcome. The outcome carries citations, or it names the reason for the absence. Keep the degrade path cheap and visible.

## Probe shape

The probe mirrors the wiki probe pattern in the detect-and-degrade contract. See [`../../cheese/references/optional-plugins.md`](../../cheese/references/optional-plugins.md).

```pseudocode
ground_wiki(topic, repo_name, session_corpus):
  # 1. Check hallouminate availability.
  if "mcp__hallouminate__list_corpora" not in available_tools:
    record once: "hallouminate: absent (tool not loaded)"
    return unavailable

  # 2. Select the corpus for THIS repository. Reuse the session selection.
  if session_corpus is None:
    corpora = mcp__hallouminate__list_corpora()
    matches = [c for c in corpora if c == "repo:" + repo_name + ":wiki"]
    if len(matches) != 1:
      record once: "hallouminate: unavailable (no wiki for " + repo_name + ")"
      return unavailable
    session_corpus = matches[0]

  # 3. Ground the topic.
  results = mcp__hallouminate__ground(query=topic, corpus=session_corpus, limit=5)
  record: "hallouminate: hit" with citations, or "hallouminate: miss"
  return results
```

- Derive `repo_name` from the current checkout. Use the repository directory name that the host reports.
- Match the corpus name exactly. Never select the first `repo:*:wiki` entry. A different repository's wiki carries another project's private rationale.
- Record `unavailable` when zero corpora match. Record `unavailable` when more than one corpus matches. Never guess between two candidates.
- Never block the dialogue on the probe. An `unavailable` outcome satisfies the gate.
- Retain `session_corpus` for one Mold episode. Repeat discovery only after an `unavailable` outcome or a registry change.
- State the absence once for each run. Write it to the ledger once. Do not repeat it for each question.

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

An item **covers** a decision only when all three conditions apply:

- **Cited.** The item names evidence that a reader can check. Use a path and symbol, line range, wiki page, or dated URL.
- **Fresh.** The citation resolves at the current HEAD. Probe the evidence again when a referent moved, changed its name, or no longer exists.
- **Decisive.** The item names the decision that it settles. A topic alone does not settle a decision.

Put covered items under `Decided`. Include the source artifact and citation, such as `via: .cheese/notes/<slug>.md`. Run the normal pass for each uncovered item. The fast path skips work. It never skips a gate. It cannot skip the two-key handshake or fresh-context taste test. It also cannot skip a consequential fork that the user did not select.

Record the intake result for each session. Record `prior evidence: none` when the session starts with no prior evidence. This intake record is not a probe outcome. It does not satisfy `grounding-recorded`. Run the wiki probe and record its outcome separately.

## Confidence when absent

If hallouminate is absent and design rationale is central to the current question, cap the result at `speculating`. Note this limit inline. See [`../../cheese/references/optional-plugins.md`](../../cheese/references/optional-plugins.md) for the full degrade contract.
