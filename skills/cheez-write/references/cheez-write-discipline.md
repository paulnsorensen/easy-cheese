# cheez-write — Write Discipline

See [`../../../shared/skill-authoring.md`](../../../shared/skill-authoring.md) for the
Iron Law / Red Flags / Rationalization-table template that governs this section.

---

## Iron Law

**No code edit without reading for hash anchors first.**

Every edit to a tracked source file goes through `tilth_write` with anchors
obtained from a preceding `tilth_read`. Host `Edit`, `Write`, `sed`, `awk`,
`perl -i`, `patch`, `tee`, and shell redirects are not used on code paths.
If tilth is unavailable, stop and report; do not silently fall back.

---

## Red Flags

Stop if you notice yourself thinking any of these:

- "The file is small; I'll just use the host Edit tool."
- "I already read this file earlier; I can skip the re-read."
- "tilth is unavailable; I'll fall back to sed."
- "It's a one-line fix; I'll guess the anchor."
- "The host Write tool is simpler for this new file."
- Reaching for `sed -i`, `awk -i`, or `patch` without first checking tilth availability.

Each of these is a rationalization. Name it and stop.

---

## Rationalization table

| Rationalization | Why it fails | Required action |
| --- | --- | --- |
| "The file is small; host Edit is equivalent." | Host Edit bypasses hash anchors, so a concurrent change or an earlier stale read produces a silently incorrect edit. | Use `tilth_write` with anchors from `tilth_read`. |
| "I read this file earlier; the anchors are still valid." | Any edit — by any agent or tool — since the last read invalidates anchors. Stale anchors silently corrupt a different line. | Re-read the target range immediately before writing. |
| "tilth is unavailable; I'll fall back to `sed`/`awk`/`perl -i`." | These tools have no mismatch detection. A file changed between read and write produces a corrupted result with no error. | Stop and report the tilth unavailability. Do not fall back. |
| "It's a one-line fix; I can guess the line number." | Line numbers shift with every edit. A guessed line number edits the wrong content without warning. | Read the range with `tilth_read` to confirm the current anchor before writing. |
| "This is a new file; I'll use host Write to create it." | Host Write bypasses tilth's write path. Even new files should go through `tilth_write` (overwrite mode) to stay on the safe path. | Use `tilth_write` with `mode: "overwrite"` for new files. |
| "The edit is mechanical; I don't need to verify the diff." | Mechanical edits fail anchor checks at the same rate as complex ones. "Mechanical" describes the intent, not the risk. | Read the target, confirm the anchor, then write. |
