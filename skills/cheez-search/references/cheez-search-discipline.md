# cheez-search — Search Discipline

See [`../../../shared/skill-authoring.md`](../../../shared/skill-authoring.md) for the
Iron Law / Red Flags / Rationalization-table template that governs this section.

---

## Iron Law

**No code search via host shell tools when tilth is available.**

Every symbol lookup, caller query, or content search in tracked source files
goes through `tilth_search`. Host `grep`, `rg`, `ripgrep`, `ag`, `ack`,
`find`, `fd`, and `Glob` are not used for code search. `sg` (ast-grep) is
the only sanctioned shell escape, and only for structural metavariable
patterns tilth cannot express. If tilth is unavailable, stop and report;
do not silently fall back.

---

## Red Flags

Stop if you notice yourself thinking any of these:

- "I already know the path; I'll skip the search and read directly."
- "tilth search is slow; I'll grep for this one."
- "It's a simple string; `rg` is faster than tilth_search."
- "I'll use `find` to locate the file, then read it." (file discovery belongs to `cheez-read` / `tilth_list`, not `find`.)
- Reaching for Bash `grep`/`rg` without first checking whether tilth can answer.

Each of these is a rationalization. Name it and stop.

---

## Rationalization table

| Rationalization | Why it fails | Required action |
| --- | --- | --- |
| "I already know the path; I'll skip the search." | Knowing a path is not the same as knowing the current symbol location. Functions move, files are renamed. A skipped search leads to a stale read. | Run `tilth_search` to confirm the current definition location before reading or editing. |
| "It's a simple string match; `grep`/`rg` is equivalent." | `grep`/`rg` return raw line matches with no semantic context (definition vs. usage, caller vs. string literal). tilth_search's `kind` parameter filters these correctly. | Use `tilth_search` with `kind: "content"` for literal matches, `kind: "callers"` for call sites. |
| "tilth is unavailable; I'll fall back to `rg`." | The fallback produces no semantic tags and breaks the tool contract that callers depend on. | Stop and report the tilth unavailability. Do not fall back. |
| "I'll use `find` to locate the file, then read it." | `find` bypasses `.gitignore` filtering and emits no token estimates. `cheez-read`'s `tilth_list` does both correctly. | Route file discovery to `cheez-read` (its `tilth_list`); `cheez-search` does not own listing or reading. |
| "The result set will be huge; I'll scope with `grep` first, then tilth." | Scoping with grep before tilth breaks the semantic kind system and can miss definition-tagged results. | Pass a tighter `scope` or `glob` parameter to `tilth_search` instead. |
