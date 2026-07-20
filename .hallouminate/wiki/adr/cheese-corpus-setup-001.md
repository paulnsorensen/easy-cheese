# ADR-001: install.sh derives the durable root via the skill's bundled `.pyz`, not bash  [status: accepted]

- **Context:** `install.sh` is `curl|bash` with no local checkout, and skills ship self-contained `.pyz` bundles — there is no `shared/scripts/` tree on the user's machine at install time. The corpus block must point at `corpus_home()`, whose single source of truth is `paths.py:210`.
- **Decision:** Install the `easy-cheese-setup` skill first, then invoke its bundled `.pyz` (`global --apply`) for the global corpus leg. One config-mutation implementation shared by installer and skill.
- **Alternatives:** (A2) fetch `paths_cli.py`+`paths.py` over the gh API and do the TOML mutation in bash — rejected: reintroduces a second implementation of the path/TOML logic, the exact `~/.cheese` drift class this work kills. (A3) fetch the `.pyz` directly — rejected: the skill is already being installed, so re-fetching is redundant.
- **Consequences:** Buys one source of truth and no bash TOML logic. Costs an install-ordering constraint (skill before corpus step) and a per-harness installed-`.pyz`-path resolution ([TBD] in the spec).
