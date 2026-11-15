---
name: skill-python-bundle
description: Enforce the easy-cheese skill Python bundle doctrine
patterns:
  - "skills/**"
agent: general
---

Enforce the skill Python bundle doctrine (see `AGENTS.md` and
`.hallouminate/wiki/architecture/skill-python-bundle-doctrine.md`).

Flag changes that:

1. Add hand-written Python (`.py`) anywhere under `skills/`. Runtime Python
   must live under `src/`; `skills/<skill>/scripts/` may contain the
   generated executable archive `<skill>.pyz` and ordinary immutable resources.
2. Edit a committed archive by hand, or change archive contents without
   rebuilding it through `just wedge-build`.
3. Make a skill invoke anything other than its own
   `skills/<skill>/scripts/<skill>.pyz` archive: never loose source,
   repository automation, or another skill's archive.
4. Ship a skill with more than one archive, or ship an archive for a skill
   that executes no Python.
5. Introduce archive dependencies that are not pure-Python and zip-importable:
   native extensions, platform-specific libraries, required external
   executables, runtime package installation, or caller-managed extraction.

Only report actual violations present in the diff. Do NOT report positive
observations or "no issues found" messages.
