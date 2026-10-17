# ADR — question-transport-policy-001

### ADR-001: Freshness classifier for structured questions  [status: accepted]

- **Context:** #294 wants design decisions discussed, not popup'd; #287 wants mold forks routed *through* the popup primitive. A type-based split (mechanical vs design by decision category) cannot explain why the same design question is fine mid-dialogue but hostile on a cold resume.
- **Decision:** A structured question may only *confirm trade-offs already shown to the user in this session*; anything else is discussed in prose first. Mechanical items (intelligible without prior-session context) may popup directly.
- **Alternatives:** Type-based classification (rejected: wrong variable); hybrid type-default-with-freshness-override (rejected: two rules where one suffices).
- **Consequences:** Mold's structured forks stay legitimate (depth is contributed in-dialogue by contract); gated resumes must re-establish weighing — which the wheypoint decision dossier makes cheap. Buys one coherent rule across #287/#294/#299; costs a dossier-writing obligation at checkpoint time.
