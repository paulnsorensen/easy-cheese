"""`providers` ranks /briesearch provider routes: CLI first, then MCP, then native.

The skill must not hard-code one vendor (`references/providers.md`). These tests
build a fake machine — a PATH of stub binaries, a HOME with harness MCP
configs, and an environment — and check the ranked routes the agent receives.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.skills.briesearch import providers
from easy_cheese.skills.briesearch.providers import (
    DOCS,
    GIT_HOST,
    PAPERS,
    REGISTRY,
    WEB_EXTRACT,
    WEB_SEARCH,
    detect_providers,
)

SECRET = "tvly-secret-value-0123456789"


@pytest.fixture
def machine(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Empty bin dir, home, and project dir."""
    dirs = tuple(tmp_path / name for name in ("bin", "home", "project"))
    for directory in dirs:
        directory.mkdir()
    return cast(tuple[Path, Path, Path], dirs)


def _install(bin_dir: Path, *binaries: str) -> None:
    for binary in binaries:
        stub = bin_dir / binary
        _ = stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        stub.chmod(0o755)


def _routes(result: dict[str, object], capability: str) -> list[tuple[str, str]]:
    routes = cast(dict[str, list[dict[str, object]]], result["routes"])
    return [
        (cast(str, r["provider"]), cast(str, r["route"])) for r in routes[capability]
    ]


def _detect(
    machine: tuple[Path, Path, Path], env: dict[str, str] | None = None
) -> dict[str, object]:
    bin_dir, home, project = machine
    return detect_providers(
        env={"PATH": str(bin_dir), **(env or {})}, home=home, cwd=project
    )


def test_an_installed_cli_outranks_a_configured_mcp_for_the_same_provider(
    machine: tuple[Path, Path, Path],
) -> None:
    bin_dir, home, _ = machine
    _install(bin_dir, "tvly")
    _ = (home / ".claude.json").write_text(
        json.dumps({"mcpServers": {"tavily": {"url": "https://mcp.tavily.com/mcp/"}}}),
        encoding="utf-8",
    )
    result = _detect(machine, {"CLAUDECODE": "1"})
    assert _routes(result, WEB_SEARCH) == [
        ("tavily", "cli"),
        ("tavily", "mcp"),
        ("native", "native"),
    ]


def test_any_ready_cli_outranks_every_mcp_even_from_an_earlier_provider(
    machine: tuple[Path, Path, Path],
) -> None:
    """Parallel precedes Brave in the registry, but its MCP loses to the Brave CLI."""
    bin_dir, home, _ = machine
    _install(bin_dir, "bx")
    _ = (home / ".claude.json").write_text(
        json.dumps({"mcpServers": {"parallel-search": {}}}), encoding="utf-8"
    )
    result = _detect(machine, {"BRAVE_SEARCH_API_KEY": "k"})
    assert _routes(result, WEB_SEARCH) == [("brave", "cli"), ("parallel", "mcp")]


def test_ready_clis_follow_registry_order(machine: tuple[Path, Path, Path]) -> None:
    bin_dir, _, _ = machine
    _install(bin_dir, "bx", "parallel-cli", "linkup")
    env = {"BRAVE_SEARCH_API_KEY": "k", "PARALLEL_API_KEY": "k", "LINKUP_API_KEY": "k"}
    assert _routes(_detect(machine, env), WEB_SEARCH) == [
        ("parallel", "cli"),
        ("linkup", "cli"),
        ("brave", "cli"),
    ]


def test_a_stored_login_cli_ranks_after_ready_clis_but_before_mcp(
    machine: tuple[Path, Path, Path],
) -> None:
    bin_dir, home, _ = machine
    _install(bin_dir, "pplx", "bx")
    _ = (home / ".claude.json").write_text(
        json.dumps({"mcpServers": {"exa": {}}}), encoding="utf-8"
    )
    result = _detect(machine, {"BRAVE_SEARCH_API_KEY": "k"})
    assert _routes(result, WEB_SEARCH) == [
        ("brave", "cli"),
        ("perplexity", "cli"),
        ("exa", "mcp"),
    ]
    routes = cast(dict[str, list[dict[str, object]]], result["routes"])
    assert routes[WEB_SEARCH][1]["credentials"] == "unverified"


def test_a_cli_without_its_key_is_unusable_not_ranked(
    machine: tuple[Path, Path, Path],
) -> None:
    bin_dir, _, _ = machine
    _install(bin_dir, "parallel-cli")
    result = _detect(machine)
    assert _routes(result, WEB_SEARCH) == []
    unusable = cast(list[dict[str, object]], result["unusable"])
    assert {(u["provider"], u["capability"]) for u in unusable} == {
        ("parallel", WEB_SEARCH),
        ("parallel", WEB_EXTRACT),
    }
    assert all("PARALLEL_API_KEY" in cast(str, u["reason"]) for u in unusable)


def test_a_keyless_route_needs_only_its_binary(
    machine: tuple[Path, Path, Path],
) -> None:
    bin_dir, _, _ = machine
    _install(bin_dir, "curl")
    result = _detect(machine)
    assert _routes(result, WEB_EXTRACT) == [("jina", "cli")]
    assert _routes(result, PAPERS) == [
        ("openalex", "cli"),
        ("arxiv", "cli"),
        ("semantic-scholar", "cli"),
    ]


def test_no_credential_value_reaches_the_output(
    machine: tuple[Path, Path, Path],
) -> None:
    bin_dir, home, _ = machine
    _install(bin_dir, "tvly")
    _ = (home / ".claude.json").write_text(
        json.dumps({"mcpServers": {"tavily": {"env": {"TAVILY_API_KEY": SECRET}}}}),
        encoding="utf-8",
    )
    result = _detect(machine, {"TAVILY_API_KEY": SECRET})
    rendered = json.dumps(result)
    assert SECRET not in rendered
    assert "env:TAVILY_API_KEY" in rendered


def test_mcp_servers_are_read_from_every_harness_config(
    machine: tuple[Path, Path, Path],
) -> None:
    _, home, project = machine
    _ = (home / ".claude.json").write_text(
        json.dumps({"projects": {str(project): {"mcpServers": {"context7": {}}}}}),
        encoding="utf-8",
    )
    _ = (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"openalex": {}}}), encoding="utf-8"
    )
    (home / ".codex").mkdir()
    _ = (home / ".codex" / "config.toml").write_text(
        '[mcp_servers.exa]\nurl = "https://mcp.exa.ai/mcp"\n', encoding="utf-8"
    )
    (home / ".cursor").mkdir()
    _ = (home / ".cursor" / "mcp.json").write_text(
        json.dumps({"mcpServers": {"github": {}}}), encoding="utf-8"
    )
    result = _detect(machine)
    assert result["mcp_servers"] == ["context7", "exa", "github", "openalex"]
    assert _routes(result, DOCS) == [("context7", "mcp")]
    assert _routes(result, PAPERS) == [("openalex", "mcp")]
    assert _routes(result, GIT_HOST) == [("github", "mcp")]
    assert _routes(result, WEB_SEARCH) == [("exa", "mcp")]


def test_codex_home_overrides_the_default_codex_config(
    machine: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    _ = (codex_home / "config.toml").write_text(
        "[mcp_servers.linkup]\n", encoding="utf-8"
    )
    (machine[1] / ".codex").mkdir()
    _ = (machine[1] / ".codex" / "config.toml").write_text(
        "[mcp_servers.decoy]\n", encoding="utf-8"
    )
    result = _detect(machine, {"CODEX_HOME": str(codex_home)})
    assert result["mcp_servers"] == ["linkup"]


def test_codex_home_sets_the_web_search_mode(
    machine: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    _ = (codex_home / "config.toml").write_text(
        'web_search = "disabled"\n', encoding="utf-8"
    )
    result = _detect(
        machine, {"CODEX_HOME": str(codex_home), "CODEX_SANDBOX": "seatbelt"}
    )
    assert result["harness"] == "codex"
    assert _routes(result, WEB_SEARCH) == []


def test_codex_home_alone_does_not_make_the_harness_codex(
    machine: tuple[Path, Path, Path],
) -> None:
    assert _detect(machine, {"CODEX_HOME": "/somewhere"})["harness"] == "unknown"


def test_claude_code_wins_over_a_codex_sandbox_marker(
    machine: tuple[Path, Path, Path],
) -> None:
    result = _detect(machine, {"CLAUDECODE": "1", "CODEX_SANDBOX": "seatbelt"})
    assert result["harness"] == "claude-code"


def test_the_command_resolves_a_relative_cwd_and_routes_project_servers(
    machine: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bin_dir, home, project = machine
    _ = (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"openalex": {}}}), encoding="utf-8"
    )
    _ = (home / ".claude.json").write_text(
        json.dumps(
            {"projects": {str(project.resolve()): {"mcpServers": {"context7": {}}}}}
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.chdir(tmp_path)
    assert providers.main(["--cwd", "project"]) == 0
    result = cast(dict[str, object], json.loads(capsys.readouterr().out))
    assert _routes(result, PAPERS) == [("openalex", "mcp")]
    assert _routes(result, DOCS) == [("context7", "mcp")]


def _mcp_routes(result: dict[str, object], capability: str) -> list[dict[str, object]]:
    routes = cast(dict[str, list[dict[str, object]]], result["routes"])
    return [r for r in routes[capability] if r["route"] == "mcp"]


def test_a_user_config_wins_over_a_project_config_for_the_same_server(
    machine: tuple[Path, Path, Path],
) -> None:
    _, home, project = machine
    _ = (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"exa": {}}}), encoding="utf-8"
    )
    (home / ".cursor").mkdir()
    cursor = home / ".cursor" / "mcp.json"
    _ = cursor.write_text(json.dumps({"mcpServers": {"exa": {}}}), encoding="utf-8")
    (route,) = _mcp_routes(_detect(machine), WEB_SEARCH)
    assert route["config"] == str(cursor)
    assert route["scope"] == "user"


def test_mcp_routes_carry_the_scope_of_their_config(
    machine: tuple[Path, Path, Path],
) -> None:
    _, home, project = machine
    _ = (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"exa": {}}}), encoding="utf-8"
    )
    _ = (home / ".claude.json").write_text(
        json.dumps({"projects": {str(project): {"mcpServers": {"linkup": {}}}}}),
        encoding="utf-8",
    )
    (project / ".codex").mkdir()
    _ = (project / ".codex" / "config.toml").write_text(
        "[mcp_servers.serper]\n", encoding="utf-8"
    )
    scopes = {
        cast(str, r["server"]): r["scope"]
        for r in _mcp_routes(_detect(machine), WEB_SEARCH)
    }
    assert scopes == {"exa": "project", "linkup": "user", "serper": "project"}


def test_a_github_token_makes_the_gh_route_ready(
    machine: tuple[Path, Path, Path],
) -> None:
    bin_dir, _, _ = machine
    _install(bin_dir, "gh")
    result = _detect(machine, {"GITHUB_TOKEN": "t"})
    (route,) = cast(dict[str, list[dict[str, object]]], result["routes"])[GIT_HOST]
    assert route["credentials"] == "ready"
    assert route["auth"] == "env:GITHUB_TOKEN"


def test_a_login_provider_with_its_key_ranks_ready(
    machine: tuple[Path, Path, Path],
) -> None:
    bin_dir, _, _ = machine
    _install(bin_dir, "pplx")
    result = _detect(machine, {"PERPLEXITY_API_KEY": "k"})
    (route,) = cast(dict[str, list[dict[str, object]]], result["routes"])[WEB_SEARCH]
    assert route["credentials"] == "ready"
    assert route["auth"] == "env:PERPLEXITY_API_KEY"


@pytest.mark.parametrize(
    ("server", "provider"),
    [
        ("brave-search", "brave"),
        ("you.com", "you"),
        ("semantic_scholar", "semantic-scholar"),
    ],
)
def test_a_server_name_matches_its_provider_with_separators_removed(
    machine: tuple[Path, Path, Path], server: str, provider: str
) -> None:
    _, home, _ = machine
    _ = (home / ".claude.json").write_text(
        json.dumps({"mcpServers": {server: {}}}), encoding="utf-8"
    )
    result = _detect(machine)
    routes = cast(dict[str, list[dict[str, object]]], result["routes"])
    assert provider in {r["provider"] for rs in routes.values() for r in rs}


@pytest.mark.parametrize("server", ["example", "texas-tools", "exam"])
def test_a_provider_token_does_not_match_inside_another_word(
    machine: tuple[Path, Path, Path], server: str
) -> None:
    _, home, _ = machine
    _ = (home / ".claude.json").write_text(
        json.dumps({"mcpServers": {server: {}}}), encoding="utf-8"
    )
    assert _routes(_detect(machine), WEB_SEARCH) == []


def test_a_malformed_config_is_a_warning_not_a_crash(
    machine: tuple[Path, Path, Path],
) -> None:
    _, home, project = machine
    _ = (home / ".claude.json").write_text("{not json", encoding="utf-8")
    (project / ".codex").mkdir()
    _ = (project / ".codex" / "config.toml").write_text("= nope", encoding="utf-8")
    result = _detect(machine)
    warnings = cast(list[str], result["warnings"])
    assert len(warnings) == 2
    assert all("could not read" in warning for warning in warnings)


def test_claude_code_native_fetch_is_flagged_as_a_summary(
    machine: tuple[Path, Path, Path],
) -> None:
    result = _detect(machine, {"CLAUDECODE": "1"})
    assert result["harness"] == "claude-code"
    routes = cast(dict[str, list[dict[str, object]]], result["routes"])
    assert "do not quote" in cast(str, routes[WEB_EXTRACT][-1]["tool"])


def test_codex_with_web_search_disabled_has_no_native_route(
    machine: tuple[Path, Path, Path],
) -> None:
    _, home, _ = machine
    (home / ".codex").mkdir()
    _ = (home / ".codex" / "config.toml").write_text(
        'web_search = "disabled"\n', encoding="utf-8"
    )
    result = _detect(machine, {"CODEX_SANDBOX": "seatbelt"})
    assert result["harness"] == "codex"
    assert _routes(result, WEB_SEARCH) == []


def test_codex_native_search_is_offered_by_default(
    machine: tuple[Path, Path, Path],
) -> None:
    result = _detect(machine, {"CODEX_SANDBOX": "seatbelt"})
    assert _routes(result, WEB_SEARCH) == [("native", "native")]


def test_an_unknown_harness_offers_no_native_route(
    machine: tuple[Path, Path, Path],
) -> None:
    result = _detect(machine)
    assert result["harness"] == "unknown"
    assert all(
        not routes
        for routes in cast(dict[str, list[object]], result["routes"]).values()
    )


def test_every_registry_route_serves_a_capability_its_provider_declares() -> None:
    for provider in REGISTRY:
        for route in provider.cli:
            assert route.capability in provider.capabilities, provider.name
        assert provider.mcp, provider.name


def test_the_command_rejects_a_missing_directory(tmp_path: Path) -> None:
    assert providers.main(["--cwd", str(tmp_path / "absent")]) == 1


def _warnings(result: dict[str, object]) -> list[str]:
    return cast(list[str], result["warnings"])


def test_a_non_regular_config_is_skipped_with_a_warning(
    machine: tuple[Path, Path, Path],
) -> None:
    _, home, _ = machine
    (home / ".claude.json").symlink_to("/dev/zero")
    result = _detect(machine)
    assert result["mcp_servers"] == []
    assert any("not a regular file" in w for w in _warnings(result))


def test_an_oversized_config_is_skipped_with_a_warning(
    machine: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, home, _ = machine
    _ = (home / ".claude.json").write_text(
        json.dumps({"mcpServers": {"exa": {}}}), encoding="utf-8"
    )
    monkeypatch.setattr(providers, "MAX_CONFIG_BYTES", 8)
    result = _detect(machine)
    assert result["mcp_servers"] == []
    assert any("larger than" in w for w in _warnings(result))


def test_a_deeply_nested_config_is_a_warning_not_a_crash(
    machine: tuple[Path, Path, Path],
) -> None:
    _, home, _ = machine
    _ = (home / ".claude.json").write_text("[" * 200_000, encoding="utf-8")
    assert any("could not read" in w for w in _warnings(_detect(machine)))


def test_warnings_never_quote_config_content(machine: tuple[Path, Path, Path]) -> None:
    _, home, project = machine
    _ = (home / ".claude.json").write_text(
        f'{{"token": "{SECRET}" oops', encoding="utf-8"
    )
    (project / ".codex").mkdir()
    _ = (project / ".codex" / "config.toml").write_text(
        f'token = "{SECRET}" oops', encoding="utf-8"
    )
    assert SECRET not in json.dumps(_detect(machine))


def test_a_toml_config_that_is_not_utf8_is_a_warning_not_a_crash(
    machine: tuple[Path, Path, Path],
) -> None:
    _, home, _ = machine
    (home / ".codex").mkdir()
    _ = (home / ".codex" / "config.toml").write_bytes(b"\xff\xfe\x00bad")
    assert any("UnicodeDecodeError" in w for w in _warnings(_detect(machine)))


def test_a_config_with_a_non_table_shape_is_a_warning(
    machine: tuple[Path, Path, Path],
) -> None:
    _, home, project = machine
    _ = (home / ".claude.json").write_text("[1, 2]", encoding="utf-8")
    _ = (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": ["exa"]}), encoding="utf-8"
    )
    (project / ".codex").mkdir()
    _ = (project / ".codex" / "config.toml").write_text(
        'mcp_servers = "exa"\n', encoding="utf-8"
    )
    result = _detect(machine)
    assert result["mcp_servers"] == []
    warnings = _warnings(result)
    assert any("top level is list" in w for w in warnings)
    assert any("mcpServers" in w and "not a table" in w for w in warnings)
    assert any("mcp_servers" in w and "not a table" in w for w in warnings)


def test_every_registry_binary_and_key_is_documented() -> None:
    doc = (
        Path(__file__).resolve().parents[2]
        / "skills/briesearch/references/providers.md"
    ).read_text(encoding="utf-8")
    binaries = {route.binary for provider in REGISTRY for route in provider.cli}
    keys = {key for provider in REGISTRY for key in provider.keys}
    assert "curl" in binaries
    for token in sorted(binaries | keys):
        assert token in doc, token


def test_no_registry_command_double_quotes_a_substituted_value() -> None:
    for provider in REGISTRY:
        for route in provider.cli:
            assert '"' not in route.command, (provider.name, route.command)
