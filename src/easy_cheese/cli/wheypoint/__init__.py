"""The fourteen commands the bundle exposes: checkpoint, validate, schema, resolve, show, lint, list, log, turns, fork, link, unlink, shape, backlinks.

This package is a mouth, not a brain. Every decision it reports was made by
`commit`, `resolve`, or `lint`; nothing here parses a projection, compares a
revision, or decides what is dispatchable, because a second implementation of
any of those would be a second answer to a question the kernel already answers.

The contract with a caller is the fromargs contract: a success reply is one
indented JSON document on stdout, exit 0. A refusal is one JSON line on
stderr, ``{"error": "<code>: <message>", "exit_code": <n>}``.

| exit | meaning                                                          |
|------|------------------------------------------------------------------|
| 0    | the command answered                                            |
| 1    | the command refused, or an unexpected crash occurred            |
| 2    | the invocation itself was wrong (unknown command, bad arguments) |
| 3    | a contract or schema violation                                  |

A resolution that is gated, ambiguous, or not found is an *answer* about the
corpus, so it prints with ``ok: true`` and the outcome in the payload; only a
reference that could not be interpreted at all is a refusal. Lint findings are
answers by the same rule.
"""

from __future__ import annotations

import sys
from typing import Annotated, Literal, TextIO

import fromargs

from easy_cheese.cli.wheypoint.checkpoint import (
    IntentFlags,
    request_identity_for as request_identity_for,
    run_checkpoint,
)
from easy_cheese.cli.wheypoint import graph as graph_mod
from easy_cheese.cli.wheypoint import queries as queries_mod

COMMANDS = (
    "checkpoint",
    "validate",
    "schema",
    "resolve",
    "show",
    "lint",
    "list",
    "log",
    "turns",
    "fork",
    "link",
    "unlink",
    "shape",
    "backlinks",
)


def _ok(command: str, payload: dict[str, object]) -> dict[str, object]:
    return {"ok": True, "command": command, **payload}


def build_app(stdin: TextIO) -> fromargs.App:
    app = fromargs.App(
        "wheypoint",
        help="Checkpoint, resolve, and inspect durable Wheypoint records.",
        help_formatter="plain",
    )

    def checkpoint(
        intent: Annotated[
            str | None, fromargs.Parameter(allow_leading_hyphen=True)
        ] = None,
        *,
        compacted: str | None = None,
        note_dir: str | None = None,
        no_note: bool = False,
        work_id: str | None = None,
        question: list[str] | None = None,
        blocker: list[str] | None = None,
        gates: bool = False,
        decision: list[str] | None = None,
        rationale: list[str] | None = None,
        directive: list[str] | None = None,
        quote: list[str] | None = None,
        resolve: list[str] | None = None,
        withdraw: list[str] | None = None,
        orientation: str | None = None,
        next: str | None = None,
        artifact: str | None = None,
        context: list[str] | None = None,
        notes_file: str | None = None,
        link: list[str] | None = None,
        kind: list[str] | None = None,
        covers: list[str] | None = None,
    ) -> dict[str, object]:
        """Checkpoint a semantic intent onto the current record.

        Parameters
        ----------
        intent
            path to a JSON intent file, or - for stdin (default: stdin, or an
            empty intent when flags are given)
        compacted
            path to a caller-authored CompactionRecord proving the session
            rehydrated from the current revision before writing
        note_dir
            directory the readable projection is mirrored into (default:
            <git toplevel>/.cheese/notes)
        no_note
            write no mirror; the checkpoint stays canonical-local
        work_id
            the work id the flags write to (default: the intent's work_id)
        question
            add an open question (repeatable)
        blocker
            add a blocker (repeatable)
        gates
            the added questions and blockers block continuation
        decision
            add a decision; pair each with a --rationale (repeatable)
        rationale
            the rationale for each --decision, then each --resolve, then each
            --withdraw, in that order (repeatable)
        directive
            add a user directive; pair each with a --quote (repeatable)
        quote
            the user's own words for each --directive (repeatable)
        resolve
            resolve an entry id; pair each with a --rationale (repeatable)
        withdraw
            withdraw an entry id; pair each with a --rationale (repeatable)
        orientation
            the orientation; its first line is the record title
        next
            the next move
        artifact
            the artifact the next move works on
        context
            add a working-context path (repeatable)
        notes_file
            a file whose text becomes the record notes
        link
            add an edge to a typed ref; pair each with a --kind (repeatable)
        kind
            the edge kind for each --link (repeatable)
        covers
            entry ids the pinnable --link covers (repeatable)
        """
        flags = IntentFlags(
            work_id=work_id,
            question=question or (),
            blocker=blocker or (),
            gates=gates,
            decision=decision or (),
            rationale=rationale or (),
            directive=directive or (),
            quote=quote or (),
            resolve=resolve or (),
            withdraw=withdraw or (),
            orientation=orientation,
            next=next,
            artifact=artifact,
            context=context or (),
            notes_file=notes_file,
            link=link or (),
            kind=kind or (),
            covers=covers or (),
        )
        return _ok(
            "checkpoint",
            run_checkpoint(
                intent,
                stdin,
                compacted=compacted,
                note_dir=note_dir,
                no_note=no_note,
                flags=flags,
            ),
        )

    def validate(
        intent: Annotated[
            str | None, fromargs.Parameter(allow_leading_hyphen=True)
        ] = None,
        *,
        work_id: str | None = None,
        question: list[str] | None = None,
        blocker: list[str] | None = None,
        gates: bool = False,
        decision: list[str] | None = None,
        rationale: list[str] | None = None,
        directive: list[str] | None = None,
        quote: list[str] | None = None,
        resolve: list[str] | None = None,
        withdraw: list[str] | None = None,
        orientation: str | None = None,
        next: str | None = None,
        artifact: str | None = None,
        context: list[str] | None = None,
        notes_file: str | None = None,
        link: list[str] | None = None,
        kind: list[str] | None = None,
        covers: list[str] | None = None,
    ) -> dict[str, object]:
        """Validate an intent against its schema without opening the store.

        Parameters
        ----------
        intent
            path to a JSON intent file, or - for stdin (default: stdin, or an
            empty intent when flags are given)
        work_id
            the work id the flags write to (default: the intent's work_id)
        question
            add an open question (repeatable)
        blocker
            add a blocker (repeatable)
        gates
            the added questions and blockers block continuation
        decision
            add a decision; pair each with a --rationale (repeatable)
        rationale
            the rationale for each --decision, then each --resolve, then each
            --withdraw, in that order (repeatable)
        directive
            add a user directive; pair each with a --quote (repeatable)
        quote
            the user's own words for each --directive (repeatable)
        resolve
            resolve an entry id; pair each with a --rationale (repeatable)
        withdraw
            withdraw an entry id; pair each with a --rationale (repeatable)
        orientation
            the orientation; its first line is the record title
        next
            the next move
        artifact
            the artifact the next move works on
        context
            add a working-context path (repeatable)
        notes_file
            a file whose text becomes the record notes
        link
            add an edge to a typed ref; pair each with a --kind (repeatable)
        kind
            the edge kind for each --link (repeatable)
        covers
            entry ids the pinnable --link covers (repeatable)
        """
        flags = IntentFlags(
            work_id=work_id,
            question=question or (),
            blocker=blocker or (),
            gates=gates,
            decision=decision or (),
            rationale=rationale or (),
            directive=directive or (),
            quote=quote or (),
            resolve=resolve or (),
            withdraw=withdraw or (),
            orientation=orientation,
            next=next,
            artifact=artifact,
            context=context or (),
            notes_file=notes_file,
            link=link or (),
            kind=kind or (),
            covers=covers or (),
        )
        return _ok("validate", queries_mod.run_validate(intent, stdin, flags))

    def schema(slug: str) -> dict[str, object]:
        """Print the JSON Schema for a registered contract slug.

        Parameters
        ----------
        slug
            a registered contract slug, e.g. checkpoint-intent
        """
        return _ok("schema", queries_mod.run_schema(slug))

    def resolve(
        ref: str,
        *,
        legacy: bool = False,
        corpus_root: str | None = None,
        project: str | None = None,
        workspace_root: str | None = None,
    ) -> dict[str, object]:
        """Resolve a slug, work id, or path to the current record.

        Parameters
        ----------
        ref
            an absolute projection path, a work id, or a slug
        legacy
            resolve a pre-kernel .cheese/notes/<slug>.md instead
        corpus_root
            the corpus to resolve in; defaults to this project's XDG corpus
        project
            resolve in another project's corpus (corpus_home()/KEY)
        workspace_root
            the owning repository checkout for cross-project continuation
        """
        return _ok(
            "resolve",
            queries_mod.run_resolve(
                ref,
                legacy=legacy,
                corpus_root=corpus_root,
                project=project,
                workspace_root=workspace_root,
            ),
        )

    def show(work_id: str, *, project: str | None = None) -> dict[str, object]:
        """Print the current record for a work id.

        Parameters
        ----------
        work_id
            the work id
        project
            read another project's corpus (corpus_home()/KEY)
        """
        return _ok("show", queries_mod.run_show(work_id, project=project))

    def lint(path: str) -> dict[str, object]:
        """Lint a generated projection against the record.

        Parameters
        ----------
        path
            path to a rendered projection document
        """
        return _ok("lint", queries_mod.run_lint(path))

    def list_(
        *,
        corpus_root: str | None = None,
        scope: Literal["project", "machine"] = "project",
        project: list[str] | None = None,
        root: list[str] | None = None,
        grep: list[str] | None = None,
        status: list[str] | None = None,
        next: list[str] | None = None,
        source: Literal["store", "note"] | None = None,
        since: str | None = None,
        limit: int | None = None,
        mirrors: bool = False,
        entry_kind: list[str] | None = None,
        entry_state: list[str] | None = None,
        gated: bool | None = None,
        edge_kind: list[str] | None = None,
        linked_to: list[str] | None = None,
        forked_from: list[str] | None = None,
    ) -> dict[str, object]:
        """List and search work items and notes across worktrees.

        Parameters
        ----------
        corpus_root
            the per-project corpus root (default: the project's own corpus)
        scope
            this project's worktrees (default), or the whole machine
        project
            limit hits to this project key (repeatable; implies --scope machine)
        root
            an extra machine search root (repeatable)
        grep
            case-insensitive substring filter (repeatable; matches any term)
        status
            filter by status (repeatable; matches any)
        next
            filter by next move (repeatable; matches any)
        source
            filter by hit source (store or note)
        since
            filter to YYYY-MM-DD or later
        limit
            cap the hit count
        mirrors
            show notes that mirror a store hit
        entry_kind
            keep records with an entry of this kind (repeatable; matches any)
        entry_state
            keep records with an entry in this state (repeatable; matches any;
            one entry must match --entry-kind too)
        gated
            keep only gated records (--gated) or only ungated ones (--no-gated)
        edge_kind
            keep records that hold an edge of this kind (repeatable)
        linked_to
            keep records whose edges or links name this ref (repeatable)
        forked_from
            keep records forked from this parent work id (repeatable)
        """
        return _ok(
            "list",
            queries_mod.run_list(
                corpus_root=corpus_root,
                scope=scope,
                project=project,
                root=root,
                grep=grep,
                status=status,
                next=next,
                source=source,
                since=since,
                limit=limit,
                mirrors=mirrors,
                entry_kind=entry_kind,
                entry_state=entry_state,
                gated=gated,
                edge_kind=edge_kind,
                linked_to=linked_to,
                forked_from=forked_from,
            ),
        )

    def log(
        work_id: str, *, corpus_root: str | None = None, project: str | None = None
    ) -> dict[str, object]:
        """Walk the revisions of one work id, oldest first.

        Parameters
        ----------
        work_id
            the work id
        corpus_root
            the per-project corpus root (default: the project's own corpus)
        project
            read another project's corpus (corpus_home()/KEY)
        """
        return _ok(
            "log",
            queries_mod.run_log(work_id, corpus_root=corpus_root, project=project),
        )

    def turns(
        *, transcript: str | None = None, session: str | None = None
    ) -> dict[str, object]:
        """Print the user's own turns from a session transcript.

        Parameters
        ----------
        transcript
            path to a session .jsonl transcript
        session
            session id under the derived projects directory
        """
        return _ok(
            "turns", queries_mod.run_turns(transcript=transcript, session=session)
        )

    def fork(
        parent: str,
        child: str,
        *,
        orientation: str,
        move: list[str] | None = None,
        copy: list[str] | None = None,
        dossier: list[str] | None = None,
        link: list[str] | None = None,
        context: list[str] | None = None,
        notes_file: str | None = None,
        next: str | None = None,
        project: str | None = None,
    ) -> dict[str, object]:
        """Fork a child record from a parent; only the child is written.

        Parameters
        ----------
        parent
            the parent work id
        child
            the new child work id
        orientation
            the child orientation; its first line is the child title
        move
            a parent entry id the child takes over (repeatable; default:
            active questions and blockers)
        copy
            a parent entry id the child copies (repeatable; default: active
            decisions and directives)
        dossier
            a parent decision-dossier fork title the child takes (repeatable)
        link
            a parent artifact-link ref the child takes (repeatable)
        context
            a working-context path for the child (repeatable)
        notes_file
            a file whose text becomes the child notes
        next
            the child's next move
        project
            fork within another project's corpus (corpus_home()/KEY)
        """
        return _ok(
            "fork",
            graph_mod.run_fork(
                parent,
                child,
                orientation=orientation,
                move=move or (),
                copy=copy or (),
                dossier=dossier or (),
                links=link or (),
                context=context or (),
                notes_file=notes_file,
                next=next,
                project=project,
            ),
        )

    def link(
        work_id: str,
        ref: str,
        *,
        kind: str,
        covers: list[str] | None = None,
        rationale: str | None = None,
    ) -> dict[str, object]:
        """Add one typed edge from a record to a work item or document.

        Parameters
        ----------
        work_id
            the work id that holds the edge
        ref
            the typed target ref, e.g. wheypoint:<project>/<work_id>
        kind
            the edge kind, e.g. relates_to, informs, or checkpoints
        covers
            an entry id the pinned link covers (repeatable)
        rationale
            why the edge exists
        """
        return _ok(
            "link",
            graph_mod.run_link(
                work_id, ref, kind=kind, covers=covers or (), rationale=rationale
            ),
        )

    def unlink(work_id: str, ref: str, *, kind: str) -> dict[str, object]:
        """Remove the edge a record holds to a ref under one kind.

        Parameters
        ----------
        work_id
            the work id that holds the edge
        ref
            the edge target ref
        kind
            the edge kind
        """
        return _ok("unlink", graph_mod.run_unlink(work_id, ref, kind=kind))

    def shape(
        work_id: str | None = None,
        *,
        scope: Literal["project", "machine"] = "project",
        project: list[str] | None = None,
        depth: int | None = None,
        kind: list[str] | None = None,
    ) -> dict[str, object]:
        """Print the work graph as JSON, with a Graphviz string in dot.

        Parameters
        ----------
        work_id
            keep only the component around this work id
        scope
            this project's corpus (default), or every project on the machine
        project
            read this project key (repeatable)
        depth
            keep records within this many hops of work_id
        kind
            keep only edges of this kind (repeatable)
        """
        return _ok(
            "shape",
            graph_mod.run_shape(
                work_id,
                scope=scope,
                project=project or (),
                depth=depth,
                kind=kind or (),
            ),
        )

    def backlinks(
        ref: str,
        *,
        corpus_root: str | None = None,
        scope: Literal["project", "machine"] = "project",
        project: list[str] | None = None,
    ) -> dict[str, object]:
        """List every record whose edges or links name a ref.

        Parameters
        ----------
        ref
            the typed ref, e.g. wheypoint:<project>/<work_id>
        corpus_root
            the per-project corpus root (default: the project's own corpus)
        scope
            this project's worktrees (default), or the whole machine
        project
            limit hits to this project key (repeatable; implies --scope machine)
        """
        return _ok(
            "backlinks",
            graph_mod.run_backlinks(
                ref, scope=scope, project=project or (), corpus_root=corpus_root
            ),
        )

    _ = app.command(checkpoint, name="checkpoint")
    _ = app.command(validate, name="validate")
    _ = app.command(schema, name="schema")
    _ = app.command(resolve, name="resolve")
    _ = app.command(show, name="show")
    _ = app.command(lint, name="lint")
    _ = app.command(list_, name="list")
    _ = app.command(log, name="log")
    _ = app.command(turns, name="turns")
    _ = app.command(fork, name="fork")
    _ = app.command(link, name="link")
    _ = app.command(unlink, name="unlink")
    _ = app.command(shape, name="shape")
    _ = app.command(backlinks, name="backlinks")
    return app


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    stdin2: TextIO = sys.stdin if stdin is None else stdin
    return build_app(stdin2).run(argv, stdout=stdout)


if __name__ == "__main__":
    sys.exit(main())