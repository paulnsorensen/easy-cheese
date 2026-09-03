#!/usr/bin/env python3
"""Print the slug-aware `research/<slug>/` layout as JSON.

`artifact-path research <slug>` returns the durable corpus root and leaves every
caller to re-derive `research/<slug>/<slug>.md`, `research/<slug>/raw/`, and the
capture manifest by hand. This command returns them, so the layout convention
lives in one place (`paths.research_layout`) instead of in each caller's prose.

JSON is the only output format: the consumer is an agent reading the result, and
a second serialization would be a knob nothing asked for.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import cast

from easy_cheese.shared import paths


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    _ = parser.add_argument("slug", help="Kebab-case research slug (4-6 words).")
    args = parser.parse_args(argv)
    try:
        layout = paths.research_layout(cast(str, args.slug))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(layout, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
