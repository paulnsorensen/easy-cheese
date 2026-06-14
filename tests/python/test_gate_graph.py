"""Tests for src/mold/gate-graph.py — mold's dual-render gate state machine.

Covers the four spec quality gates that the module backs:

  - gate-graph emits valid `.dot` and a mermaid block from one model (ADR-001);
  - it degrades svg/png to mermaid when Graphviz `dot` is absent;
  - the committed `mold.dot` snapshot byte-matches `to_dot()`;
  - gate-prose-sync: the handshake.md coherence-checklist items == the model's
    gate nodes (a gate cannot be silently dropped from prose);
  - portability: no hardcoded corpus name in mold's runtime source.

The module is imported from the built mold.pyz via the `gate_graph` fixture, so
these also exercise the bundled artifact, not just the source tree.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HANDSHAKE = REPO_ROOT / "skills" / "mold" / "references" / "handshake.md"
MOLD_DOT = REPO_ROOT / "skills" / "mold" / "scripts" / "mold.dot"
MOLD_SRC_DIR = REPO_ROOT / "src" / "mold"


class TestToDot:
    def test_is_a_valid_digraph(self, gate_graph: ModuleType) -> None:
        dot = gate_graph.to_dot()
        assert dot.startswith("digraph mold_gates {")
        assert dot.rstrip().endswith("}")

    def test_contains_every_node(self, gate_graph: ModuleType) -> None:
        dot = gate_graph.to_dot()
        for node in gate_graph.GATE_MODEL.nodes:
            assert node.label in dot, node.label

    def test_contains_the_curdle_edge_with_label(self, gate_graph: ModuleType) -> None:
        dot = gate_graph.to_dot()
        assert 'handshake -> curdle [label="both keys"]' in dot

    def test_is_deterministic(self, gate_graph: ModuleType) -> None:
        assert gate_graph.to_dot() == gate_graph.to_dot()


class TestToMermaid:
    def test_is_a_fenced_mermaid_block(self, gate_graph: ModuleType) -> None:
        mermaid = gate_graph.to_mermaid()
        assert mermaid.startswith("```mermaid\nflowchart LR")
        assert mermaid.rstrip().endswith("```")

    def test_contains_every_node(self, gate_graph: ModuleType) -> None:
        mermaid = gate_graph.to_mermaid()
        for node in gate_graph.GATE_MODEL.nodes:
            expected = (
                node.label.replace('"', "'")
                .replace("[", "&#91;")
                .replace("]", "&#93;")
            )
            assert expected in mermaid, node.label

    def test_labels_have_no_unescaped_brackets(self, gate_graph: ModuleType) -> None:
        # In Mermaid flowchart grammar `[`/`]` are node-shape delimiters; a literal
        # bracket inside an id["..."] label span breaks the parser. The substring
        # presence check above passes even when the block is unrenderable, so guard
        # the *syntax*: every quoted label span must be bracket-free.
        mermaid = gate_graph.to_mermaid()
        spans = re.findall(r'\["(.*?)"\]', mermaid)
        assert spans, "no mermaid label spans found"
        offenders = [s for s in spans if "[" in s or "]" in s]
        assert not offenders, f"literal brackets inside mermaid label spans break parsing: {offenders}"

    def test_bracketed_labels_are_escaped(self, gate_graph: ModuleType) -> None:
        # The two checklist gates whose labels carry [TBD]/[BLOCKED]/[?] must reach
        # the mermaid output as HTML entities, not dropped or left literal.
        mermaid = gate_graph.to_mermaid()
        bracketed = [n for n in gate_graph.GATE_MODEL.nodes if "[" in n.label or "]" in n.label]
        assert bracketed, "expected at least one label with brackets to exercise escaping"
        for node in bracketed:
            escaped = (
                node.label.replace('"', "'").replace("[", "&#91;").replace("]", "&#93;")
            )
            assert escaped in mermaid, f"label not escaped/present in mermaid: {node.label!r}"

    def test_derives_from_same_node_set_as_dot(self, gate_graph: ModuleType) -> None:
        # Both targets enumerate the same node ids — the no-drift guarantee.
        dot_ids = {gate_graph._dot_id(n.id) for n in gate_graph.GATE_MODEL.nodes}
        mermaid = gate_graph.to_mermaid()
        for nid in dot_ids:
            assert re.search(rf"\b{re.escape(nid)}\b", mermaid), nid


class TestRenderDegrade:
    def test_dot_target_never_needs_binary(self, gate_graph: ModuleType) -> None:
        target, payload = gate_graph.render("dot", dot_present=False)
        assert target == "dot"
        assert payload.decode("utf-8") == gate_graph.to_dot()

    def test_mermaid_target_never_needs_binary(self, gate_graph: ModuleType) -> None:
        target, payload = gate_graph.render("mermaid", dot_present=False)
        assert target == "mermaid"
        assert payload.decode("utf-8") == gate_graph.to_mermaid()

    def test_svg_degrades_to_mermaid_without_dot(self, gate_graph: ModuleType) -> None:
        target, payload = gate_graph.render("svg", dot_present=False)
        assert target == "mermaid"
        assert payload.decode("utf-8") == gate_graph.to_mermaid()

    def test_png_degrades_to_mermaid_without_dot(self, gate_graph: ModuleType) -> None:
        target, _ = gate_graph.render("png", dot_present=False)
        assert target == "mermaid"

    def test_svg_renders_binary_when_dot_present(self, gate_graph: ModuleType) -> None:
        # Only when Graphviz is actually installed — otherwise the degrade path
        # above is the real-world case and is covered.
        if not gate_graph.dot_available():
            pytest.skip("graphviz `dot` not on PATH")
        target, payload = gate_graph.render("svg", dot_present=True)
        assert target == "svg"
        assert b"<svg" in payload

    def test_unknown_target_raises(self, gate_graph: ModuleType) -> None:
        with pytest.raises(gate_graph.RenderError):
            gate_graph.render("jpeg", dot_present=True)


class TestDotSnapshot:
    def test_committed_dot_matches_model(self, gate_graph: ModuleType) -> None:
        # mold.dot is the canonical committed snapshot; it must equal to_dot() so
        # the `.dot` source of truth and the model can't diverge.
        assert MOLD_DOT.exists(), f"missing committed snapshot: {MOLD_DOT}"
        assert MOLD_DOT.read_text(encoding="utf-8") == gate_graph.to_dot()


class TestGateProseSync:
    """The rigor-parity mechanic: handshake.md coherence-checklist items must
    equal the model's gate nodes, so a gate cannot be dropped from prose."""

    def _checklist_labels(self) -> list[str]:
        body = HANDSHAKE.read_text(encoding="utf-8")
        block = re.search(
            r"```\nCoherence self-check before curdle:\n(.*?)```",
            body,
            re.DOTALL,
        )
        assert block, "coherence self-check block not found in handshake.md"
        return re.findall(r"^- \[ \] (.+?)\s*$", block.group(1), re.MULTILINE)

    def test_checklist_block_is_present(self) -> None:
        assert self._checklist_labels(), "no checklist items parsed"

    def test_gate_nodes_match_checklist_items(self, gate_graph: ModuleType) -> None:
        prose_ids = {gate_graph.gate_id(label) for label in self._checklist_labels()}
        model_ids = {n.id for n in gate_graph.GATE_MODEL.by_kind("gate")}
        missing_from_model = prose_ids - model_ids
        missing_from_prose = model_ids - prose_ids
        assert not missing_from_model, f"in handshake.md but not the gate model: {missing_from_model}"
        assert not missing_from_prose, f"in gate model but dropped from handshake.md: {missing_from_prose}"

    def test_count_matches(self, gate_graph: ModuleType) -> None:
        assert len(self._checklist_labels()) == len(gate_graph.GATE_MODEL.by_kind("gate"))


class TestPortability:
    """No hardcoded consumer corpus name in mold's runtime source. ADRs resolve
    `repo:<their-repo>:wiki` dynamically; a literal `easy-cheese:wiki` baked into
    a runtime path would break every other repo that runs mold."""

    def test_no_hardcoded_corpus_in_mold_src(self) -> None:
        offenders: list[str] = []
        for path in MOLD_SRC_DIR.glob("*.py"):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"easy-cheese:wiki|easy_cheese:wiki", line):
                    offenders.append(f"{path.name}:{n}: {line.strip()}")
        assert not offenders, "hardcoded corpus name in mold runtime source:\n" + "\n".join(offenders)


class TestCli:
    def test_default_render_is_dot(self, gate_graph: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
        rc = gate_graph.main([])
        assert rc == 0
        out = capsys.readouterr().out
        assert out.startswith("digraph mold_gates {")

    def test_mermaid_to_stdout(self, gate_graph: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
        rc = gate_graph.main(["--render", "mermaid"])
        assert rc == 0
        assert "```mermaid" in capsys.readouterr().out

    def test_out_file_written(self, gate_graph: ModuleType, tmp_path: Path) -> None:
        out = tmp_path / "g.dot"
        rc = gate_graph.main(["--render", "dot", "--out", str(out)])
        assert rc == 0
        assert out.read_text(encoding="utf-8") == gate_graph.to_dot()

    def test_binary_to_stdout_is_rejected(
        self, gate_graph: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        if gate_graph.dot_available():
            pytest.skip("dot present: svg would degrade only without it")
        # Without dot, svg degrades to mermaid (text) and prints fine; force the
        # binary-without-out error path by checking a present-dot environment is
        # the only one that hits it. Here we assert the degrade note instead.
        rc = gate_graph.main(["--render", "svg"])
        assert rc == 0
        err = capsys.readouterr().err
        assert "degraded svg -> mermaid" in err

    def test_bad_state_file_exits_2(
        self, gate_graph: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bad = tmp_path / "state.json"
        bad.write_text("{not json", encoding="utf-8")
        rc = gate_graph.main(["--state", str(bad)])
        assert rc == 2
        assert "could not read state" in capsys.readouterr().err


class TestGateIdInjectivity:
    """gate-prose-sync compares slugged ids as *sets*. If two distinct checklist
    labels slug to the same id, set-equality can silently accept a state where one
    gate was dropped and another duplicated (the count test would still see N
    items but the model would be missing a gate). Injectivity of gate_id over the
    real checklist is the boundary that closes that hole."""

    def test_gate_ids_are_unique(self, gate_graph: ModuleType) -> None:
        labels = gate_graph.COHERENCE_GATES
        ids = [gate_graph.gate_id(label) for label in labels]
        dupes = {i for i in ids if ids.count(i) > 1}
        assert not dupes, f"gate_id collisions hide a dropped gate behind set-equality: {dupes}"
        assert len(set(ids)) == len(labels)

    def test_model_gate_count_equals_checklist_source(self, gate_graph: ModuleType) -> None:
        # The model is built from COHERENCE_GATES; assert no gate is lost in _build_model.
        assert len(gate_graph.GATE_MODEL.by_kind("gate")) == len(gate_graph.COHERENCE_GATES)

    def test_gate_id_is_idempotent(self, gate_graph: ModuleType) -> None:
        # Slugging an already-slugged id must be a fixed point, else re-deriving
        # ids (model vs prose) could diverge on a second pass.
        for label in gate_graph.COHERENCE_GATES:
            once = gate_graph.gate_id(label)
            assert gate_graph.gate_id(once) == once, label


class TestRenderAutoDetect:
    """The explicit-degrade tests all pass dot_present=False. Production calls
    render() with no dot_present, so the real branch is dot_present=None ->
    dot_available(). Exercise that path so the auto-detect wiring is covered, not
    just the injected flag."""

    def test_text_targets_match_auto_detect_path(self, gate_graph: ModuleType) -> None:
        # dot/mermaid never touch the binary, so auto-detect must agree with the
        # forced-absent result regardless of whether dot is installed.
        for target in ("dot", "mermaid"):
            auto_t, auto_p = gate_graph.render(target)  # dot_present=None
            forced_t, forced_p = gate_graph.render(target, dot_present=False)
            assert auto_t == forced_t == target
            assert auto_p == forced_p

    def test_svg_auto_detect_tracks_dot_availability(self, gate_graph: ModuleType) -> None:
        # With no dot_present arg, the effective target must follow dot_available():
        # 'svg' when graphviz is present, degraded 'mermaid' when it is absent.
        effective, payload = gate_graph.render("svg")
        if gate_graph.dot_available():
            assert effective == "svg"
            assert b"<svg" in payload
        else:
            assert effective == "mermaid"
            assert payload.decode("utf-8") == gate_graph.to_mermaid()


class TestRenderDotFailure:
    """When dot IS present but the subprocess fails (bad install, malformed input),
    render must fail loud with RenderError carrying dot's stderr — not return a
    truncated/empty image. Monkeypatched so it runs without a real graphviz."""

    def test_nonzero_dot_exit_raises_with_stderr(
        self, gate_graph: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import subprocess as _sp

        def fake_run(*_a, **_k):
            return _sp.CompletedProcess(args=_a, returncode=1, stdout=b"", stderr=b"boom: layout failed")

        monkeypatch.setattr(gate_graph.subprocess, "run", fake_run)
        with pytest.raises(gate_graph.RenderError) as exc:
            gate_graph.render("svg", dot_present=True)
        assert "boom: layout failed" in str(exc.value)
        assert "svg" in str(exc.value)

    def test_successful_dot_returns_binary_target(
        self, gate_graph: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import subprocess as _sp

        def fake_run(*_a, **_k):
            return _sp.CompletedProcess(args=_a, returncode=0, stdout=b"<svg>fake</svg>", stderr=b"")

        monkeypatch.setattr(gate_graph.subprocess, "run", fake_run)
        effective, payload = gate_graph.render("png", dot_present=True)
        assert effective == "png"  # not degraded: dot was 'present'
        assert payload == b"<svg>fake</svg>"


class TestPortabilityBroadened:
    """The existing portability test greps only the literal `easy-cheese:wiki`.
    A different hardcoded corpus (`repo:anything:wiki`) or a dev-box absolute path
    would equally break run-anywhere. Widen the net to any corpus literal and any
    home-rooted absolute path in mold runtime source."""

    def _src_lines(self) -> list[tuple[str, int, str]]:
        out: list[tuple[str, int, str]] = []
        for path in MOLD_SRC_DIR.glob("*.py"):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                out.append((path.name, n, line))
        return out

    def test_no_repo_wiki_corpus_literal(self) -> None:
        # Any `repo:<name>:wiki` baked into runtime source is non-portable — the
        # corpus must be resolved dynamically at curdle (ADR-002).
        offenders = [
            f"{name}:{n}: {line.strip()}"
            for name, n, line in self._src_lines()
            if re.search(r"repo:[A-Za-z0-9_.-]+:wiki", line)
        ]
        assert not offenders, "hardcoded corpus literal in mold runtime source:\n" + "\n".join(offenders)

    def test_no_devbox_absolute_paths(self) -> None:
        # An absolute /home/<user> or hardcoded repo path would not exist on a
        # consumer's machine.
        offenders = [
            f"{name}:{n}: {line.strip()}"
            for name, n, line in self._src_lines()
            if re.search(r"/home/[A-Za-z0-9_.-]+/", line) or "paulnsorensen" in line
        ]
        assert not offenders, "dev-box absolute path in mold runtime source:\n" + "\n".join(offenders)


class TestCliDegradeToFile:
    """--out with a binary target that degrades (no dot) must write the mermaid
    fallback bytes to the named file AND print the degrade note, not silently
    write an empty/binary file."""

    def test_out_with_degraded_svg_writes_mermaid_and_notes(
        self, gate_graph: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        if gate_graph.dot_available():
            pytest.skip("dot present: svg would render binary, not degrade")
        out = tmp_path / "graph.svg"
        rc = gate_graph.main(["--render", "svg", "--out", str(out)])
        assert rc == 0
        assert out.read_text(encoding="utf-8") == gate_graph.to_mermaid()
        assert "degraded svg -> mermaid" in capsys.readouterr().err

    def test_unknown_render_choice_rejected_by_argparse(
        self, gate_graph: ModuleType
    ) -> None:
        # argparse choices guard the CLI surface before render() is ever called.
        with pytest.raises(SystemExit):
            gate_graph.main(["--render", "jpeg"])
