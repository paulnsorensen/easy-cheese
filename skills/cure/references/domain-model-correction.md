# Domain-model correction (cure)

Read this before Flow step 6 (domain-model correction).

After the cook's fixes land, correct the project domain model (ubiquitous language) for terms **touched by the cook's diff** (bounded — diff-touched terms only, never a free rewrite).

Resolve the store with `domain_model_target()` (`shared/scripts/paths.py`, read-probe cascade wiki → docs → XDG; an existing model always wins).

For a diff-touched entry whose definition or `_Code_:` referent no longer matches the code, update it and write a one-line change note per edit. Entry format:

```
**Term** — definition.
_Avoid_: syn1, syn2
_Code_: file:line (or NEW ENTITY)
```

**HARD rule — flag, don't reverse:** if a correction would REVERSE a mold-decided canonical term (replace the term mold made authoritative, or contradict its definition), do not rewrite — flag it to the user (the term, mold's decision, the conflict) and leave the entry unchanged. mold DECIDES canonical terms at curdle; cure only APPLIES BOUNDED corrections and never overrules the authoritative writer.
