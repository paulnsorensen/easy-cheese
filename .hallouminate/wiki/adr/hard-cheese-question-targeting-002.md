# ADR: ranked regions appear before the first attempt; targeted questions appear only after a FAIL

**Status:** accepted (2026-09-16). Spec: `specs/hard-cheese-question-targeting.md` in the durable corpus. Fork F-2.

- **Context:** The paper reports that the Relational breakthrough usually follows the first Socratic round (mean 2.4 attempts). Front-loading targeted questions could cut attempts, but it costs a `powerful` judge call on every gate run and risks coaching before the author's first explanation, which is the artifact the judge grades.
- **Decision:** The gate shows the ranked hunks as `path:start-end — reasons` next to the diff summary before attempt one and makes no model call before that attempt. On FAIL the judge must anchor at least one Socratic question to a ranked hunk and return `targets_addressed`.
- **Alternatives:** Targeted questions before attempt one (strongest expected effect, one extra judge call per run, coaching risk). Nothing new before attempt one (smallest change, first attempt gains nothing).
- **Consequences:** Targeting at zero extra cost. The "do not coach" rule stays intact because the regions are part of the diff the author already sees. Whether pre-seeded questions would cut attempts further is unmeasured.
