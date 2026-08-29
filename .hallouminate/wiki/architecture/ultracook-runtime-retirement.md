# Ultracook runtime retirement

The `/ultracook` skill remains a redirect stub for muscle-memory invocations, but its published Python runtime is retired. Release builds discover bundles only from `src/easy_cheese/skills/*/commands.py`, so they build neither an Ultracook application distribution nor `ultracook.pyz`; consequently no ephemeral Ultracook requirements closure is generated. Fan-out runtime commands are owned by `/cook`; retained files under `skills/ultracook/references/` are compatibility templates consumed by Cook's fan pathway. This keeps redirect documentation stable while preventing stale archives from entering releases.[^1]

[^1]: scripts/build_pyz.py:37-42; skills/ultracook/SKILL.md:16-21
