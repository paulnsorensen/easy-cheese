"""The nine commands the bundle exposes: checkpoint, validate, schema, resolve, show, lint, list, log, turns.

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
    request_identity_for as request_identity_for,
    run_checkpoint,
)
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
    ) -> dict[str, object]:
        """Checkpoint a semantic intent onto the current record.

        Parameters
        ----------
        intent
            path to a JSON intent file, or - for stdin (default: stdin)
        compacted
            path to a caller-authored CompactionRecord proving the session
            rehydrated from the current revision before writing
        note_dir
            directory the readable projection is mirrored into (default:
            <git toplevel>/.cheese/notes)
        no_note
            write no mirror; the checkpoint stays canonical-local
        """
        return _ok(
            "checkpoint",
            run_checkpoint(
                intent,
                stdin,
                compacted=compacted,
                note_dir=note_dir,
                no_note=no_note,
            ),
        )

    def validate(
        intent: Annotated[
            str | None, fromargs.Parameter(allow_leading_hyphen=True)
        ] = None,
    ) -> dict[str, object]:
        """Validate an intent against its schema without opening the store.

        Parameters
        ----------
        intent
            path to a JSON intent file, or - for stdin (default: stdin)
        """
        return _ok("validate", queries_mod.run_validate(intent, stdin))

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

    _ = app.command(checkpoint, name="checkpoint")
    _ = app.command(validate, name="validate")
    _ = app.command(schema, name="schema")
    _ = app.command(resolve, name="resolve")
    _ = app.command(show, name="show")
    _ = app.command(lint, name="lint")
    _ = app.command(list_, name="list")
    _ = app.command(log, name="log")
    _ = app.command(turns, name="turns")
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