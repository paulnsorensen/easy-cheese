# Migrate Wheypoint as a separate boundary slice

## Outcome

Move Wheypoint onto doctrine-compliant packaging and typed boundary contracts while preserving the useful projection and reference behavior explored in PR #430.

## Constraints

- Wheypoint continuity remains separate from phase handoff authority.
- Preserve canonical JSON continuity records and generated Markdown projections.
- Do not create a second schema authority under a Wheypoint-owned schema package.
- Reuse the shared `ArtifactRef` and canonical contract gateway where the route is a phase handoff.
- Ship only `skills/wheypoint/scripts/wheypoint.pyz` for Wheypoint Python execution.

## Dependency

Starts after the shared bundle builder, closure gates, and Mold → Cook gateway establish the target seam.
