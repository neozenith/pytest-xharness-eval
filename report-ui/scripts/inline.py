#!/usr/bin/env -S uv run
"""Populate a built report page with a captured directory, exactly as ``report.py --inline`` would.

    uv run report-ui/scripts/inline.py <captured dir> <built index.html> <out.html>

The captured directory must already hold an ``index.json`` (run the evals or the replay).
"""

from __future__ import annotations

# Standard Library
import json
import sys
from pathlib import Path

# Our Libraries
from pytest_xharness_eval import report


def main(argv: list[str]) -> None:
    if len(argv) != 3:
        raise SystemExit(__doc__)
    captured, template, out = (Path(a) for a in argv)
    index = json.loads((captured / report.INDEX_NAME).read_text(encoding="utf-8"))
    tokens_path = captured / report.TOKENS_NAME
    tokens = report.load_tokens(tokens_path if tokens_path.is_file() else None)
    out.write_text(report.inline_page(template.read_text(encoding="utf-8"), captured, index, tokens, inline=True), encoding="utf-8")
    print(f"{out} ({out.stat().st_size:,} bytes, {len(index['cells'])} sessions)")


if __name__ == "__main__":
    main(sys.argv[1:])
