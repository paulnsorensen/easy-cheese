# Semantic backends — LSP and Serena

The cheez trio (`/cheez-read`, `/cheez-search`, `/cheez-write`) share the same framing for two source backends beyond the default: a harness-provided LSP and Serena. This document is the single source of truth for that framing; each skill's `references/routing.md` points here rather than restating it and keeps only its own routing tables, lead-ins, and fallbacks.

## LSP availability

**easy-cheese does not install LSP** — it is whatever language servers your harness already exposes (Claude Code LSP plugins, Zed / VS Code language servers, etc.).

## Serena

[Serena](https://github.com/oraios/serena) is an LSP-driven MCP that exposes the LSP queries as named tools. When Serena is configured for the codebase (`.serena/project.yml` present), the **calling workflow skill** should route directly to Serena rather than entering the relevant cheez-* skill.
