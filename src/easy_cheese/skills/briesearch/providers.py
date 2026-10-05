#!/usr/bin/env python3
"""Detect usable /briesearch provider routes: CLI first, then MCP, then native.

`references/providers.md` lists the providers this registry knows. A provider is
an implementation detail of a research capability (`routing.md`), so the skill
must not hard-code one vendor. This command tells the agent which routes the
current machine can actually run, in preference order:

  1. ``cli`` with credentials ready — an installed vendor CLI whose API key is
     in the environment, or a keyless CLI route. CLI output can be trimmed and
     written to disk before it reaches the context window.
  2. ``cli`` with credentials unverified — an installed CLI that keeps its own
     login (for example ``gh auth login``). It may still fail on auth.
  3. ``mcp`` — a server named in a harness MCP config file. A configured server
     can still fail to connect, so the agent confirms the tools in its own tool
     list before it selects the route.
  4. ``native`` — the harness web tool, when the harness is known.

The command never runs a provider, never touches the network, and never prints
a credential value: it reports only whether a named variable is set.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import fromargs

from easy_cheese.shared.bounded_read import (
    BoundedReadOverflow,
    NotRegularFileError,
    read_bounded_descriptor,
)

WEB_SEARCH = "web-search"
WEB_EXTRACT = "web-extract"
DOCS = "docs"
PAPERS = "papers"
GIT_HOST = "git-host"
CAPABILITIES = (WEB_SEARCH, WEB_EXTRACT, DOCS, PAPERS, GIT_HOST)

READY = "ready"
UNVERIFIED = "unverified"

Scope = Literal["user", "project"]

USER: Scope = "user"
PROJECT: Scope = "project"

# A real ~/.claude.json is about 100 KB; the cap only stops absurd files.
MAX_CONFIG_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class CliRoute:
    """One documented command that serves one capability."""

    capability: str
    binary: str
    command: str
    keyless: bool = False


@dataclass(frozen=True)
class Provider:
    """One provider: its CLI routes, credentials, and MCP server names.

    `keys` are alternative environment variables; any one authenticates.
    `login` means the CLI can keep its own stored credentials. `mcp` holds
    server-name tokens that identify the provider in a harness MCP config.
    """

    name: str
    capabilities: tuple[str, ...]
    cli: tuple[CliRoute, ...] = ()
    keys: tuple[str, ...] = ()
    login: bool = False
    mcp: tuple[str, ...] = ()
    cheap_mode: str = ""


# Registry order is the default preference inside one route rank. Cheap,
# agent-oriented providers come first; `references/providers.md` gives the
# cost evidence. Commands are templates: `<q>` is a query, URL-encoded only inside a URL, and `<url>` is a URL.
# Single quotes wrap each substituted value; `references/safety.md` has the rule.
# A provider lists only the CLI routes that are a sensible default for it:
# Jina search bills a 10k-token minimum, so Jina registers extraction only.
REGISTRY: tuple[Provider, ...] = (
    Provider(
        "jina",
        (WEB_EXTRACT,),
        cli=(
            CliRoute(WEB_EXTRACT, "jina", "jina read '<url>' --json"),
            CliRoute(
                WEB_EXTRACT,
                "curl",
                "curl -gsS 'https://r.jina.ai/<url>' -H 'x-respond-with: markdown'",
                keyless=True,
            ),
        ),
        keys=("JINA_API_KEY",),
        mcp=("jina",),
        cheap_mode="keyless r.jina.ai allows about 20 requests per minute",
    ),
    Provider(
        "parallel",
        (WEB_SEARCH, WEB_EXTRACT),
        cli=(
            CliRoute(
                WEB_SEARCH,
                "parallel-cli",
                "parallel-cli search '<q>' --mode fast --max-results 5 --json",
            ),
            CliRoute(
                WEB_EXTRACT,
                "parallel-cli",
                "parallel-cli extract '<url>' --objective '<claim>' --json",
            ),
        ),
        keys=("PARALLEL_API_KEY",),
        mcp=("parallel",),
        cheap_mode="--mode turbo or fast; the API default (advanced) costs 5x",
    ),
    Provider(
        "tavily",
        (WEB_SEARCH, WEB_EXTRACT),
        cli=(
            CliRoute(
                WEB_SEARCH,
                "tvly",
                "tvly search '<q>' --depth basic --max-results 5 --json",
                keyless=True,
            ),
            CliRoute(WEB_EXTRACT, "tvly", "tvly extract '<url>' --json", keyless=True),
        ),
        keys=("TAVILY_API_KEY",),
        mcp=("tavily",),
        cheap_mode="--depth basic or faster; advanced costs 2 credits",
    ),
    Provider(
        "linkup",
        (WEB_SEARCH, WEB_EXTRACT),
        cli=(
            CliRoute(WEB_SEARCH, "linkup", "linkup search '<q>' --depth fast --json"),
            CliRoute(WEB_EXTRACT, "linkup", "linkup fetch '<url>' --json"),
        ),
        keys=("LINKUP_API_KEY",),
        mcp=("linkup",),
        cheap_mode="--depth fast; the CLI default (standard) costs more",
    ),
    Provider(
        "brave",
        (WEB_SEARCH,),
        cli=(CliRoute(WEB_SEARCH, "bx", "bx web '<q>' --count 5"),),
        keys=("BRAVE_SEARCH_API_KEY",),
        mcp=("brave", "bravesearch"),
        cheap_mode="--count 5; prefer bx web over bx context",
    ),
    Provider(
        "perplexity",
        (WEB_SEARCH,),
        cli=(CliRoute(WEB_SEARCH, "pplx", "pplx search web '<q>' -n 5"),),
        keys=("PERPLEXITY_API_KEY",),
        login=True,
        mcp=("perplexity", "pplx"),
        cheap_mode="search only; ask and research tools add model cost",
    ),
    Provider(
        "exa",
        (WEB_SEARCH, WEB_EXTRACT),
        keys=("EXA_API_KEY",),
        mcp=("exa",),
        cheap_mode="type fast or instant, 10 results, highlights not full text",
    ),
    Provider(
        "serpapi",
        (WEB_SEARCH,),
        cli=(CliRoute(WEB_SEARCH, "serpapi", "serpapi search engine=google q='<q>'"),),
        keys=("SERPAPI_KEY",),
        login=True,
        mcp=("serpapi",),
        cheap_mode="trim the JSON with --fields or --jq before it reaches context",
    ),
    Provider(
        "firecrawl",
        (WEB_SEARCH, WEB_EXTRACT),
        cli=(
            CliRoute(
                WEB_EXTRACT,
                "firecrawl",
                "firecrawl scrape '<url>' --format markdown --only-main-content",
            ),
        ),
        keys=("FIRECRAWL_API_KEY",),
        login=True,
        mcp=("firecrawl",),
        cheap_mode="scrape only main content; use it for JS-heavy or blocked pages",
    ),
    Provider(
        "kagi",
        (WEB_SEARCH, WEB_EXTRACT),
        keys=("KAGI_API_KEY",),
        mcp=("kagi", "kagimcp"),
        cheap_mode="high list price; use for a low-spam index only",
    ),
    Provider(
        "you",
        (WEB_SEARCH,),
        keys=("YDC_API_KEY",),
        mcp=("youdotcom", "ydc", "you.com", "youcom"),
        cheap_mode="omit live extraction",
    ),
    Provider(
        "serper",
        (WEB_SEARCH,),
        keys=("SERPER_API_KEY",),
        mcp=("serper",),
        cheap_mode="snippets only; pair with an extract route",
    ),
    Provider(
        "context7",
        (DOCS,),
        cli=(
            CliRoute(
                DOCS,
                "ctx7",
                "ctx7 library '<name>' '<question>' --json, then "
                + "ctx7 docs '<library-id>' '<question>' --json",
            ),
        ),
        keys=("CONTEXT7_API_KEY",),
        login=True,
        mcp=("context7",),
        cheap_mode="one version-scoped question per call",
    ),
    Provider(
        "openalex",
        (PAPERS,),
        cli=(
            CliRoute(
                PAPERS,
                "curl",
                "curl -gsS 'https://api.openalex.org/works?search=<q>&per_page=10'",
                keyless=True,
            ),
        ),
        mcp=("openalex",),
        cheap_mode="singleton lookups by DOI or ID are free",
    ),
    Provider(
        "arxiv",
        (PAPERS,),
        cli=(
            CliRoute(
                PAPERS,
                "curl",
                "curl -gsS 'https://export.arxiv.org/api/query?search_query=all:<q>&max_results=10'",
                keyless=True,
            ),
        ),
        mcp=("arxiv",),
        cheap_mode="wait 3 seconds between requests; output is Atom XML",
    ),
    Provider(
        "semantic-scholar",
        (PAPERS,),
        cli=(
            CliRoute(
                PAPERS,
                "curl",
                "curl -gsS 'https://api.semanticscholar.org/graph/v1/paper/search"
                + "?query=<q>&fields=title,year,externalIds,url&limit=10'",
                keyless=True,
            ),
        ),
        mcp=("asta", "semanticscholar"),
        cheap_mode="use batch endpoints; the keyless pool throttles under load",
    ),
    Provider(
        "github",
        (GIT_HOST,),
        cli=(
            CliRoute(
                GIT_HOST,
                "gh",
                "gh search repos|code|issues '<q>' --json '<fields>' -L 10",
            ),
        ),
        keys=("GH_TOKEN", "GITHUB_TOKEN"),
        login=True,
        mcp=("github",),
        cheap_mode="name only the --json fields the claim needs",
    ),
    Provider(
        "playwright",
        (WEB_EXTRACT,),
        cli=(
            CliRoute(
                WEB_EXTRACT,
                "playwright-cli",
                "playwright-cli open '<url>', then playwright-cli snapshot",
                keyless=True,
            ),
        ),
        mcp=("playwright",),
        cheap_mode="last resort for interactive or logged-in pages",
    ),
)


@dataclass(frozen=True)
class McpServer:
    """Where a configured MCP server name came from.

    `scope` is `project` when the repository controls the config file, so the
    server name is untrusted. Other configs are `user`.
    """

    config: str
    scope: Scope


@dataclass(frozen=True)
class Harness:
    name: str
    native: Mapping[str, str]


_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


def _tokens(server: str) -> set[str]:
    lowered = server.casefold()
    parts = {token for token in _TOKEN_SPLIT.split(lowered) if token}
    return {lowered, _TOKEN_SPLIT.sub("", lowered), *parts}


def _parse_json(raw: bytes) -> object:
    return cast(object, json.loads(raw.decode("utf-8")))


def _parse_toml(raw: bytes) -> object:
    return cast(object, tomllib.loads(raw.decode("utf-8")))


def _load(
    path: Path, warnings: list[str], parse: Callable[[bytes], object]
) -> dict[str, object] | None:
    """Parse one config file that is a regular file under the size cap.

    Warnings name the path and the exception type only: parser messages can
    quote file content, and file content can hold credentials.
    """
    try:
        fd = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0),
        )
        try:
            raw = read_bounded_descriptor(fd, path, limit=MAX_CONFIG_BYTES)
        finally:
            os.close(fd)
        data = parse(raw)
    except FileNotFoundError:
        return None
    except NotRegularFileError:
        warnings.append(f"could not read {path}: not a regular file")
        return None
    except BoundedReadOverflow:
        warnings.append(f"could not read {path}: larger than {MAX_CONFIG_BYTES} bytes")
        return None
    except (OSError, ValueError, RecursionError) as exc:
        warnings.append(f"could not read {path}: {type(exc).__name__}")
        return None
    if not isinstance(data, dict):
        warnings.append(
            f"ignored {path}: top level is {type(data).__name__}, not a table"
        )
        return None
    return cast(dict[str, object], data)


def _server_names(
    config: Mapping[str, object], key: str, source: Path, warnings: list[str]
) -> list[str]:
    table = config.get(key)
    if table is None:
        return []
    if not isinstance(table, dict):
        warnings.append(f"ignored {key} in {source}: not a table")
        return []
    return [name for name in cast(dict[object, object], table) if isinstance(name, str)]


ConfigFile = tuple[Scope, Path, dict[str, object]]


def codex_configs(
    home: Path, cwd: Path, env: Mapping[str, str], warnings: list[str]
) -> list[ConfigFile]:
    """Parse the user and project Codex configs once: (scope, path, table)."""
    codex_home = Path(env["CODEX_HOME"]) if env.get("CODEX_HOME") else home / ".codex"
    configs: list[ConfigFile] = []
    candidates: tuple[tuple[Scope, Path], ...] = (
        (USER, codex_home / "config.toml"),
        (PROJECT, cwd / ".codex" / "config.toml"),
    )
    for scope, path in candidates:
        data = _load(path, warnings, _parse_toml)
        if data is not None:
            configs.append((scope, path, data))
    return configs


def configured_mcp_servers(
    home: Path, cwd: Path, codex: list[ConfigFile], warnings: list[str]
) -> dict[str, McpServer]:
    """Map each MCP server name in a known harness config to its config file.

    Reads only server names. Values such as `env` and `headers` can hold
    credentials, so they are never read into the result. User-scope configs
    list first. A name in any project-scope config reports
    `project` scope, because the harness may run the repository's server.
    """
    user: list[tuple[Scope, Path, str, Mapping[str, object]]] = []
    project: list[tuple[Scope, Path, str, Mapping[str, object]]] = []
    claude_user = home / ".claude.json"
    data = _load(claude_user, warnings, _parse_json)
    if data is not None:
        user.append((USER, claude_user, "mcpServers", data))
        projects = data.get("projects")
        if isinstance(projects, dict):
            local = cast(dict[str, object], projects).get(str(cwd))
            if isinstance(local, dict):
                user.append(
                    (USER, claude_user, "mcpServers", cast(dict[str, object], local))
                )
    json_configs: tuple[tuple[Scope, Path], ...] = (
        (USER, home / ".cursor" / "mcp.json"),
        (PROJECT, cwd / ".mcp.json"),
        (PROJECT, cwd / ".cursor" / "mcp.json"),
    )
    for scope, path in json_configs:
        data = _load(path, warnings, _parse_json)
        if data is not None:
            (user if scope == USER else project).append(
                (scope, path, "mcpServers", data)
            )
    for scope, path, table in codex:
        (user if scope == USER else project).append((scope, path, "mcp_servers", table))

    sources: dict[str, list[tuple[Scope, Path]]] = {}
    for scope, path, key, table in (*user, *project):
        for name in _server_names(table, key, path, warnings):
            sources.setdefault(name, []).append((scope, path))
    return {
        name: McpServer(
            str(next((p for s, p in found if s == USER), found[0][1])),
            PROJECT if any(s == PROJECT for s, _ in found) else USER,
        )
        for name, found in sources.items()
    }


def _codex_web_search(codex: list[ConfigFile]) -> str | None:
    """The Codex `web_search` mode from the nearest config, if set."""
    mode: str | None = None
    for _, _, data in codex:
        value = data.get("web_search")
        if isinstance(value, str):
            mode = value
    return mode


def detect_harness(env: Mapping[str, str], codex: list[ConfigFile]) -> Harness:
    """Name the running harness and its native web tools.

    `CLAUDECODE=1` is the documented Claude Code subprocess marker. Codex
    documents its sandbox markers (`CODEX_SANDBOX*`), and injects
    `CODEX_THREAD_ID` into every shell environment, including `--yolo` runs.
    Other `CODEX_` variables, such as a user-exported `CODEX_HOME`, do not
    prove that Codex is running.
    """
    if env.get("CLAUDECODE") == "1":
        return Harness(
            "claude-code",
            {
                WEB_SEARCH: "WebSearch (titles and URLs only)",
                WEB_EXTRACT: "WebFetch (model summary, not raw text: do not quote it)",
            },
        )
    if "CODEX_THREAD_ID" in env or any(
        name.startswith("CODEX_SANDBOX") for name in env
    ):
        if _codex_web_search(codex) == "disabled":
            return Harness("codex", {})
        return Harness(
            "codex",
            {
                WEB_SEARCH: "web_search",
                WEB_EXTRACT: "web_search open_page (not verified as raw text)",
            },
        )
    return Harness("unknown", {})


def _cli_auth(
    provider: Provider, route: CliRoute, env: Mapping[str, str]
) -> str | None:
    """How the route authenticates, or None when it cannot.

    A set key wins even on a keyless route: a keyed account has higher limits,
    and the agent can pass the variable to a raw `curl` route.
    """
    for key in provider.keys:
        if env.get(key):
            return f"env:{key}"
    if route.keyless:
        return "none-needed"
    return "stored-login" if provider.login else None


def detect_providers(
    *,
    env: Mapping[str, str],
    home: Path,
    cwd: Path,
    registry: tuple[Provider, ...] = REGISTRY,
) -> dict[str, object]:
    """Rank every usable route per capability: ready CLI, unverified CLI, MCP, native."""
    warnings: list[str] = []
    codex = codex_configs(home, cwd, env, warnings)
    servers = configured_mcp_servers(home, cwd, codex, warnings)
    harness = detect_harness(env, codex)
    search_path = env.get("PATH", "")

    tiers: dict[str, dict[str, list[dict[str, object]]]] = {
        capability: {"ready": [], "unverified": [], "mcp": []}
        for capability in CAPABILITIES
    }
    unusable: list[dict[str, object]] = []
    for provider in registry:
        for route in provider.cli:
            if shutil.which(route.binary, path=search_path) is None:
                continue
            auth = _cli_auth(provider, route, env)
            if auth is None:
                unusable.append(
                    {
                        "provider": provider.name,
                        "capability": route.capability,
                        "route": "cli",
                        "binary": route.binary,
                        "reason": "no credential: set one of "
                        + ", ".join(provider.keys),
                    }
                )
                continue
            tier = UNVERIFIED if auth == "stored-login" else READY
            tiers[route.capability][tier].append(
                {
                    "provider": provider.name,
                    "route": "cli",
                    "credentials": tier,
                    "auth": auth,
                    "binary": route.binary,
                    "command": route.command,
                    "cheap_mode": provider.cheap_mode,
                }
            )
        matches = sorted(
            name for name in servers if _tokens(name).intersection(provider.mcp)
        )
        for name in matches:
            for capability in provider.capabilities:
                tiers[capability]["mcp"].append(
                    {
                        "provider": provider.name,
                        "route": "mcp",
                        "server": name,
                        "config": servers[name].config,
                        "scope": servers[name].scope,
                        "cheap_mode": provider.cheap_mode,
                    }
                )

    routes: dict[str, list[dict[str, object]]] = {}
    for capability in CAPABILITIES:
        ranked = [
            *tiers[capability]["ready"],
            *tiers[capability]["unverified"],
            *sorted(tiers[capability]["mcp"], key=lambda route: route["scope"] != USER),
        ]
        native = harness.native.get(capability)
        if native is not None:
            ranked.append({"provider": "native", "route": "native", "tool": native})
        routes[capability] = ranked

    return {
        "harness": harness.name,
        "routes": routes,
        "unusable": unusable,
        "mcp_servers": {name: servers[name].scope for name in sorted(servers)},
        "warnings": warnings,
    }


def providers_cmd(*, cwd: str = ".") -> dict[str, object]:
    """Detect usable /briesearch provider routes: CLI first, then MCP, then native.

    Parameters
    ----------
    cwd
        Project directory for project-scoped MCP configs (default: cwd).
    """
    path = Path(cwd)
    if not path.is_dir():
        raise fromargs.CliError(f"not a directory: {path}", exit_code=1)
    return detect_providers(env=os.environ, home=Path.home(), cwd=path.resolve())


def build_app() -> fromargs.App:
    return fromargs.App(
        "providers",
        help="Detect usable /briesearch provider routes: CLI first, then MCP, then native.",
        help_formatter="plain",
        default_command=providers_cmd,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
