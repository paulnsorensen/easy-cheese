# ADR-003: delete the `spec_match` scoring engine rather than refactor it  [status: accepted]

- **Context:** PR #284 added `spec_match.py` / `spec_match_cli.py`: an untested difflib scoring engine (slug/title/first_heading, 0.60 threshold) wired into no SKILL.md, globbing a hardcoded repo-local `.cheese/specs` — the wrong dir, since specs land in XDG. `paths.py` already has `resolve_slug` (difflib, XDG-correct) 20 lines away.
- **Decision:** Delete both scripts. Route spec-discovery through hallouminate `ground` (present) or `resolve_slug` (absent, ADR-002).
- **Alternatives:** Refactor `spec_match` to source candidates from `paths.list_artifacts("specs")` and keep its title/heading scoring — rejected: once hallouminate is the semantic path, maintaining a separate deterministic scoring engine (plus its tokenize/threshold fixes) is NIH the design no longer needs.
- **Consequences:** Buys less code to maintain and removes a wrong-directory bug. Costs the title/heading scoring increment over stem-only matching on the headless path — judged not worth its maintenance once semantic grounding exists.
