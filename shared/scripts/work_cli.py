"""Small JSON CLI for WorkRecord operations."""
from __future__ import annotations

import argparse
import json

from work import ensure_work, migrate_legacy, resolve_continue


def main() -> int:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    create = subcommands.add_parser("ensure")
    create.add_argument("--work-id")
    create.add_argument("--subject")
    create.add_argument("--worktree")
    create.add_argument("--project")
    resume = subcommands.add_parser("continue")
    resume.add_argument("--worktree")
    resume.add_argument("--project")
    migrate = subcommands.add_parser("migrate")
    migrate.add_argument("paths", nargs="+")
    migrate.add_argument("--project")
    args = parser.parse_args()

    if args.command == "ensure":
        result = ensure_work(args.work_id, args.subject, args.worktree, project=args.project)
        value = result.to_mapping() if result else None
    elif args.command == "continue":
        value = resolve_continue(args.project, args.worktree)
    else:
        value = migrate_legacy(args.paths, args.project)
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
