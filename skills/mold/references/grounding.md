# Grounding — hallouminate wiki probe

Throughout a `/mold` dialogue — at **Ground** phase entry and at decision points in any Dialogue mode (see § When to probe) — if hallouminate is available, probe the consumer's wiki corpus before asking the user the next question. Fold any matching rationale or ADR entries into the evidence base. If hallouminate is absent, skip silently and continue with diff + code evidence only.

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
- If `list_corpora` is unreachable or returns no wiki corpus, fall back silently. Never block the dialogue on the probe.
- State the absence once per run if the tool is missing; do not repeat on every question.

## When to probe

Probe at **Ground** phase entry and, in the other Dialogue modes, at any decision point — before generating the next question — when any of these are true:

- The dialogue is about to decide a consequential fork whose options could have prior rationale (e.g. "why not X").
- The next question to the user is one the wiki may already answer (a settled decision, an ADR, a recorded convention).
- The dialogue is about to restate rationale for an existing system or module that may have ADRs.
- The spec being molded overlaps with a prior mold session in this repo.

Skip the probe for pure Explore mode (no named system) and for Diagnose mode (evidence comes from code/logs, not rationale docs).

Cite hits in that round's decision ledger (`Decided / Asking / [AGENT-DECIDED]` — see `../SKILL.md` § Rules): a settled decision found in the wiki lands under `Decided` with its wiki page cited, not reopened as a fresh question.

## Confidence when absent

If hallouminate is absent and design rationale is central to the question at hand, cap at `speculating` and note it inline. See [`../../cheese/references/optional-plugins.md`](../../cheese/references/optional-plugins.md) for the full degrade contract.
