from __future__ import annotations

from pathlib import Path

import pytest

from easy_cheese.shared import git_utils
from easy_cheese.skills.plate import pr_body
from easy_cheese.skills.plate.diagram_trigger import DiagramNeed

_SECTIONS = "\n".join(f"{heading}\nNone\n" for heading in pr_body.DEFAULT_HEADINGS)
_PLATED = "Plated as single: one cohesive change\n"
_DIAGRAM = "```mermaid\nflowchart TD\n  A --> B\n```\n"


def _body(*parts: str) -> str:
    return "\n".join((_PLATED, _SECTIONS, *parts))


def test_valid_body_has_no_errors() -> None:
    assert pr_body.check_body(_body()) == []


def test_body_over_the_line_cap_is_rejected() -> None:
    filler = "\n".join(f"line {n}" for n in range(pr_body.MAX_LINES))

    errors = pr_body.check_body(_body(filler))

    assert any("non-blank lines" in error for error in errors)


def test_diagram_and_checklist_do_not_count_toward_the_cap() -> None:
    room = pr_body.MAX_LINES - len([x for x in _body().splitlines() if x.strip()])
    padding = "\n".join(f"line {n}" for n in range(room))
    checklist = "\n".join(f"- [ ] item {n}" for n in range(10))

    assert pr_body.check_body(_body(padding, _DIAGRAM, checklist)) == []
    assert pr_body.check_body(_body(padding, "extra")) != []


def test_missing_heading_is_named() -> None:
    body = _body().replace("## Risk", "## Danger")

    assert pr_body.check_body(body) == ["missing heading: ## Risk"]


def test_template_headings_replace_the_defaults() -> None:
    template = "## Summary\n- [ ] done\n"

    assert pr_body.check_body(_PLATED + "## Summary\nx\n", template=template) == []
    assert pr_body.check_body(_body(), template=template) == ["missing heading: ## Summary"]


def test_plated_line_is_required_and_shape_checked() -> None:
    no_line = _body().replace(_PLATED, "")
    bad_shape = _body().replace("Plated as single", "Plated as sideways")

    assert pr_body.check_body(no_line) == ["missing topology line: Plated as <shape>: <reason>"]
    assert pr_body.check_body(bad_shape) == ["missing topology line: Plated as <shape>: <reason>"]


@pytest.mark.parametrize("word", ["comprehensive", "Robust", "seamlessly", "leverages", "significantly"])
def test_filler_words_are_rejected(word: str) -> None:
    errors = pr_body.check_body(_body(f"This is {word} done."))

    assert len(errors) == 1
    assert "filler word" in errors[0]


def test_stack_layer_needs_position_line_diagram_and_stacked_shape() -> None:
    errors = pr_body.check_body(_body(), stack_layer=True)

    assert errors == [
        "stack layer needs a stacked shape, got Plated as single",
        "stack layer needs a line: Stack: <n> of <total>",
        "stack layer needs a mermaid flowchart of the stack order",
    ]


def test_complete_stack_layer_passes() -> None:
    body = _body("Stack: 2 of 3", _DIAGRAM).replace("Plated as single", "Plated as stacked_linear")

    assert pr_body.check_body(body, stack_layer=True) == []


def test_cli_exits_one_and_lists_every_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "body.md"
    _ = path.write_text("## Why\nrobust\n")

    assert pr_body.main(["--body-file", str(path)]) == 2

    stderr = capsys.readouterr().err
    assert "missing heading: ## Risk" in stderr
    assert "filler word" in stderr


def test_cli_accepts_a_valid_body(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "body.md"
    _ = path.write_text(_body())

    assert pr_body.main(["--body-file", str(path)]) == 0
    assert '"valid": true' in capsys.readouterr().out


_FLOW = DiagramNeed("flowchart", "code modules: 3 changed, 3 added, removed, or renamed")


@pytest.mark.parametrize(
    ("extra", "need", "valid"),
    [
        ("", _FLOW, False),
        ("```mermaid\nsequenceDiagram\n  A->>B: ack\n```\n", _FLOW, False),
        (_DIAGRAM, _FLOW, True),
        ("Diagram: none, the three modules are one renamed package", _FLOW, True),
        ("", DiagramNeed(None, "docs-only change"), True),
    ],
)
def test_triggered_diagram_needs_the_named_kind_or_a_recorded_skip(
    extra: str, need: DiagramNeed, valid: bool
) -> None:
    missing = f"diff needs a mermaid flowchart ({_FLOW.reason}); add one, or a line: Diagram: none, <reason>"

    assert pr_body.check_body(_body(extra), need=need) == ([] if valid else [missing])


def _git(repo: Path, *args: str) -> None:
    result = git_utils.run_git(list(args), cwd=repo)
    assert result.returncode == 0, result.stderr


@pytest.fixture
def body_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Enter a repo whose `feature` branch adds three modules to `main`; return a body path outside it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=main", ".")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    _ = (repo / "app.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed")
    _git(repo, "switch", "-c", "feature")
    for name in ("router.py", "probe.py", "report.py"):
        _ = (repo / name).write_text(f"# {name}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "flow")
    monkeypatch.chdir(repo)
    return tmp_path / "body.md"


def test_cli_diagram_base_enforces_the_flowchart_on_a_cross_module_diff(
    body_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _ = body_path.write_text(_body())

    assert pr_body.main(["--body-file", str(body_path), "--diagram-base", "main"]) == 2
    assert "diff needs a mermaid flowchart (code modules: 3 changed, 3 added" in capsys.readouterr().err

    _ = body_path.write_text(_body(_DIAGRAM))
    assert pr_body.main(["--body-file", str(body_path), "--diagram-base", "main"]) == 0
    assert "diagram not required" not in capsys.readouterr().err


def test_cli_diagram_base_prints_one_skip_line_when_no_diagram_is_required(
    body_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _ = body_path.write_text(_body().replace("Plated as single", "Plated as orthogonal_flat"))

    assert pr_body.main(["--body-file", str(body_path), "--diagram-base", "main"]) == 0
    assert capsys.readouterr().err == "diagram not required: independent PR (Plated as orthogonal_flat)\n"


@pytest.mark.parametrize(("base", "message"), [("nope", "git diff nope...HEAD failed"), ("-x", "must name a ref")])
def test_cli_diagram_base_rejects_an_unusable_ref(
    body_path: Path, capsys: pytest.CaptureFixture[str], base: str, message: str
) -> None:
    _ = body_path.write_text(_body(_DIAGRAM))

    assert pr_body.main(["--body-file", str(body_path), f"--diagram-base={base}"]) == 2
    assert message in capsys.readouterr().err
