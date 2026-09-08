#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyYAML>=6.0"]
# ///
"""Check the generated ADR bundle against the okf-yaml verification gate (ADR 0048).

`make adrs` already refuses to render a record that fails `record.schema.json` or
names a relation target that does not exist. This checks the *output*: the
conditions under which the bundle conforms to the Open Knowledge Format, which the
generator cannot check because it is the thing producing them.

    [x] every non-reserved .md parses as YAML frontmatter with a non-empty `type`
    [x] index.md and graph.md carry no frontmatter (reserved / companion files)
    [x] every generated file carries a regenerate banner naming its generator
    [x] graph.json ids are unique and every edge endpoint resolves to a node

Run through `make adrs-check`, which also fails on a stale or hand-edited file.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

#: Files the bundle generates that are not records. `index.md` is OKF-reserved and
#: must carry no frontmatter; `graph.md` is a companion doc under the same rule.
RESERVED = {"index.md", "graph.md"}

BANNER = "okf_render.py"


def frontmatter(text: str) -> dict[str, object] | None:
    """The file's YAML frontmatter, or None when it has none."""
    if not text.startswith("---\n"):
        return None
    _, _, rest = text.partition("---\n")
    block, sep, _ = rest.partition("\n---\n")
    if not sep:
        return None
    loaded = yaml.safe_load(block)
    return loaded if isinstance(loaded, dict) else {}


def check(bundle: Path) -> list[str]:
    """Every gate failure as a flat string. Empty means the bundle conforms."""
    problems: list[str] = []

    for path in sorted(bundle.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if BANNER not in text:
            problems.append(f"{path.name}: no regenerate banner naming {BANNER}")
        if path.name in RESERVED:
            if text.startswith("---\n"):
                problems.append(f"{path.name}: reserved file must carry no frontmatter")
            continue
        try:
            front = frontmatter(text)
        except yaml.YAMLError as exc:
            problems.append(f"{path.name}: frontmatter does not parse: {exc}")
            continue
        if front is None:
            problems.append(f"{path.name}: no YAML frontmatter")
        elif not front.get("type"):
            problems.append(f"{path.name}: frontmatter carries no non-empty `type`")

    graph = json.loads((bundle / "graph.json").read_text(encoding="utf-8"))
    nodes = [e["data"]["id"] for e in graph["elements"] if "source" not in e["data"]]
    if len(nodes) != len(set(nodes)):
        problems.append("graph.json: node ids are not unique")
    known = set(nodes)
    for element in graph["elements"]:
        data = element["data"]
        if "source" not in data:
            continue
        for end in ("source", "target"):
            if data[end] not in known:
                problems.append(f"graph.json: edge {data['id']} {end} {data[end]} is not a node")

    return problems


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    args = argv if argv is not None else sys.argv[1:]
    bundle = Path(args[0]) if args else Path(__file__).parent
    problems = check(bundle)
    for problem in problems:
        log.error("  %s", problem)
    if problems:
        log.error("%s: %d gate failures", bundle, len(problems))
        return 1
    log.info("%s: OKF conformance gate passed", bundle)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
