# Sub-agent model selection across harnesses

Research pass, 2026-09-10. Question: can a skill or agent definition pick a cheaper or faster model for a sub-agent, and can one field do it for Claude Code, Codex CLI, Cursor, GitHub Copilot, and oh-my-pi? Grounds the tier rows in `skills/cheese/references/agent-resolution.md` and `routing-policy.md`, and the dotfiles agent-definition work in paulnsorensen/dotfiles#952.

## Answer

Every harness supports per-agent or per-role model selection. No two agree on the key, the location, or the value vocabulary. The open Agent Skills spec (agentskills.io) defines **no** model, tier, or effort field. Two secondary blogs claim it does; the primary spec page contradicts them. Trust the spec.

Consequence for easy-cheese: keep the harness-neutral `minimum_power: cheap | default | powerful` + `effort` vocabulary in skill tables, and bind it to a concrete model per harness in one place (`routing-policy.md` § Roles x tiers). Do not put `model:` in a shared `SKILL.md` and expect it to route anywhere except Claude Code.

## Per-harness binding

| Harness | Where | Values | Granularity | Source |
|---|---|---|---|---|
| Claude Code — agent definition | `model:` in `.claude/agents/*.md` frontmatter; `effort:` too | `haiku` / `sonnet` / `opus` / `fable` / full ID / `inherit` | per agent | code.claude.com/docs/en/sub-agents |
| Claude Code — Agent tool | `model` parameter at spawn | same aliases | per call; overrides the definition | same |
| Claude Code — precedence | — | call param → definition `model:` → `CLAUDE_CODE_SUBAGENT_MODEL` → parent model | — | same |
| Claude Code — SKILL.md | `model:` / `effort:` frontmatter (skill's own turn); `context: fork` + `agent:` to run the body as a sub-agent | same aliases; effort `low`…`max` | per skill | code.claude.com/docs/en/skills |
| Cursor | `model:` in `.cursor/agents/*.md` | `inherit` or a model ID | per agent | cursor.com/docs/subagents |
| GitHub Copilot (VS Code, CLI) | `model:` in `.github/agents/*.agent.md`; CLI user override `~/.copilot/settings.json` → `subagents.agents.<name>.model` | model ID; VS Code accepts a fallback array, CLI a single string | per agent | learn.microsoft.com copilot-specialized-agents; github.blog custom-agents-in-copilot-cli |
| Codex CLI | `config.toml` `agents.default_subagent_model` and `agents.default_subagent_reasoning_effort`; `[profiles.*]` blocks | model string | global default; per-spawn override exists but is documented only in a community post | learn.chatgpt.com config-reference |
| oh-my-pi | `modelRoles` in `~/.omp/agent/config.yml` (`default`, `plan`, `tiny`/`smol`, `slow`, `vision`) with a thinking-level suffix | provider/model ID per role | per role; an agent requests a role, not a model | github.com/can1357/oh-my-pi README, docs/models.md |
| Agent Skills spec | none | — | — | agentskills.io/specification (frontmatter: `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`) |

## Unconfirmed claims (single secondary source each)

- Codex per-spawn model/effort override syntax ("subagents v2").
- Copilot "a sub-agent cannot exceed the parent's cost tier".
- Cursor `fast` shorthand as a frontmatter value.
- Any runtime reading `SKILL.md` `metadata:` as a tier hint.

## Recommendation

1. One semantic tier per role in the harness-neutral tables (`cheap | default | powerful`). Bind to `haiku | sonnet | opus` (Claude), `luna | terra | sol` (Codex), `tiny | task | slow` (OMP) in `routing-policy.md` only.
2. Dotfiles emits each harness's native key from that one tier at render time. Never hand-maintain five copies.
3. Where dispatch happens from a Claude skill, pass the `Agent` tool `model` parameter explicitly; measured 2026-09, 91% of dispatches used `inherit`, which silently resolves to the agent definition's `model:` and hides the intent from analytics.

Full evidence with fetch bodies: `.cheese/research/subagent-model-selection-portability/` (gitignored, this checkout).
