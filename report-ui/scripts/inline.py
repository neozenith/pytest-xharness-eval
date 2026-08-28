#!/usr/bin/env -S uv run
"""Populate a built report page with a cache's aggregated data, exactly as ``report.py --inline`` would.

    uv run report-ui/scripts/inline.py <cache dir> <built index.html> <out.html>

The cache must already hold ``report/index.json`` (run the evals or the replay);
a ``report/`` directory itself is also accepted.
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
    cache, template, out = (Path(a) for a in argv)
    report_dir = cache / report.REPORT_DIR if (cache / report.REPORT_DIR / report.INDEX_NAME).is_file() else cache
    index = json.loads((report_dir / report.INDEX_NAME).read_text(encoding="utf-8"))
    tokens_path = report_dir / report.TOKENS_NAME
    tokens = report.load_tokens(tokens_path if tokens_path.is_file() else None)
    out.write_text(report.inline_page(template.read_text(encoding="utf-8"), report_dir, index, tokens, inline=True), encoding="utf-8")
    print(f"{out} ({out.stat().st_size:,} bytes, {len(index['cells'])} sessions)")


if __name__ == "__main__":
    main(sys.argv[1:])
