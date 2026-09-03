# Domain-model correction for Cure

Read this file before Flow step 6.

After Cook fixes land, correct domain terms that the Cook diff touches.
Do not rewrite terms outside that diff.

Resolve the store with `domain_model_target()` from `src/easy_cheese/shared/paths.py`.
The probe order is wiki, docs, then XDG.
An existing model always wins.
The function returns `(backend, location, wiki_reachable)`.
When `wiki_reachable` is false, the probe did not consult the wiki.
Report this fact before you correct a file-based model.
The wiki can contain the authoritative model.

Update a touched entry when its definition or `_Code_:` target no longer matches the code.
Write one change note for each edit.
Use this format:

```text
**Term** — definition.
_Avoid_: syn1, syn2
_Code_: file:line (or NEW ENTITY)
```

**Hard rule: Report a reversal, but do not apply it.**
Do not replace or contradict a canonical term that Mold made authoritative.
Report the term, the Mold decision, and the conflict.
Leave the entry unchanged.
Mold selects canonical terms during Curdle.
Cure applies only bounded corrections.
