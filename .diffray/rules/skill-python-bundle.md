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

1. Add Python source (`.py`) anywhere under `skills/`. Runtime Python must live
   under `src/`; `skills/` may contain only generated `.pyz` artifacts.
2. Make a skill invoke anything other than its own
   `skills/<skill>/scripts/<skill>.pyz` — never loose source, `common.pyz`,
   repository automation, or another skill's bundle.
3. Ship a skill with more than one `.pyz`, or ship a `.pyz` for a skill that
   executes no Python.
4. Introduce bundle dependencies that are not pure-Python and zip-importable:
   native extensions, platform-specific libraries, required external
   executables, runtime installation/downloads, or caller-managed extraction.

Only report actual violations present in the diff. Do NOT report positive
observations or "no issues found" messages.
