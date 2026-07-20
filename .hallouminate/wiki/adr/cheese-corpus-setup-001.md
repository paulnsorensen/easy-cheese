# ADR-001: install.sh derives the durable root via the skill's bundled `.pyz`, not bash  [status: accepted]

- **Context:** `install.sh` is `curl|bash` with no local checkout, and skills ship self-contained `.pyz` bundles — there is no `shared/scripts/` tree on the user's machine at install time. The corpus block must point at `corpus_home()`, whose single source of truth is `paths.py:210`.
- **Decision:** Install the `easy-cheese-setup` skill first, then invoke its bundled `.pyz` (`global --apply`) for the global corpus leg. One config-mutation implementation shared by installer and skill.
- **Alternatives:** (A2) fetch `paths_cli.py`+`paths.py` over the gh API and do the TOML mutation in bash — rejected: reintroduces a second implementation of the path/TOML logic, the exact `~/.cheese` drift class this work kills. (A3) fetch the `.pyz` directly — rejected: the skill is already being installed, so re-fetching is redundant.
- **Consequences:** Buys one source of truth and no bash TOML logic. Costs an install-ordering constraint (skill before corpus step) and a per-harness installed-`.pyz`-path resolution ([TBD] in the spec).

## Implementation notes (post-review)

The spec's per-harness `.pyz`-path `[TBD]` resolved to `gh skill list --agent <host> --scope user --json path,skillName --jq '.[] | select(.skillName=="…") | .path'` — portable, no hardcoded per-harness dirs.

Two review-caught gotchas worth remembering for any future work on this path:

- **`gh --json` field restriction interacts with `--jq`.** `--json <fields>` drops every field not listed, so a `--jq` filter that selects on an omitted field (`.skillName`) sees `null` and silently matches nothing — the whole step no-ops without error. Any field the jq expression references must be in `--json`. (First shipped as `--json path` while the filter selected on `.skillName`; the install-time corpus registration was dead-on-arrival until the field was added.)
- **Marked-block section parsing must bound at TOML table headers.** `hallouminate_setup._unmarked_corpus_sections` ends a `[[corpus]]` section at the next line starting with `[` (any table header) or the marked-block markers — NOT at EOF. Running to EOF let `migrate_legacy` delete a trailing `[[repository]]`/`[settings]` block that followed the last legacy corpus. The shared user config holds unrelated corpora and tenants; never assume a section runs to end-of-file.
