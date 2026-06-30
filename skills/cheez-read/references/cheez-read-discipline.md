# cheez-read — Read Discipline

See [`../../../shared/skill-authoring.md`](../../../shared/skill-authoring.md) for the
Iron Law / Red Flags / Rationalization-table template that governs this section.

---

## Iron Law

**No file read via host tools when tilth is available.**

Every read of a tracked source file goes through `tilth_read` or `tilth_list`.
Host `Read`, `Glob`, `cat`, `head`, `tail`, `ls`, and `find` are not used on
code paths. If tilth is unavailable, stop and report; do not silently fall back.

---

## Red Flags

Stop if you notice yourself thinking any of these:

- "The file is small; host Read is faster than tilth."
- "I already know the path and line range; I don't need tilth_read."
- "tilth is slow right now; I'll just cat the file."
- "The host Read tool is already open in my context; I'll use it this once."
- "I only need one line; `sed -n` is simpler."

Each of these is a rationalization. Name it and stop.

---

## Rationalization table

| Rationalization | Why it fails | Required action |
| --- | --- | --- |
| "The file is small; I'll use host Read — it's equivalent." | Host Read emits no hash anchors, bypasses session deduplication, and cannot outline large files. Any subsequent edit will lack a safe anchor. | Use `tilth_read`. Small files are exactly the case where the cost is lowest. |
| "I already know the line range; I'll skip the read." | Hash anchors are required by cheez-write. Without a read, the write step has no anchor and either guesses (unsafe) or fails. | Read the range first with `tilth_read` to capture current anchors. |
| "tilth is unavailable; I'll fall back to `cat`/`sed -n`." | The fallback produces no anchors and silently breaks the read-edit protocol for every downstream edit. | Stop and report the tilth unavailability. Do not fall back. |
| "I only need the directory listing; `ls` is fine." | `ls` lacks token estimates and `.gitignore` filtering. A tilth_list result informs budget decisions that `ls` cannot. | Use `tilth_list`. |
| "I just read this file; I'll reuse the content from memory." | In-context content may have drifted if any edit occurred since the read. Anchors in memory are stale if the file changed. | Re-read if any edit occurred since the last read of that file. |
