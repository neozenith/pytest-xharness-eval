#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# ///
"""Compare two extractions of the same codebase, edge by edge.

The LSP resolves types and tree-sitter resolves names, so they fail in opposite
directions. The LSP loses edges it cannot see with the workspace half-open;
tree-sitter invents edges when two definitions share a name. Neither is ground
truth, so the useful number is the overlap and the shape of each disagreement.

Usage: compare.py <lsp.json> <treesitter.json>
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def load(path: Path) -> tuple[dict, set[tuple[str, str]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in raw["nodes"]}
    edges = {(e["source"], e["target"]) for e in raw["edges"]}
    return nodes, edges


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("lsp", type=Path)
    ap.add_argument("treesitter", type=Path)
    ap.add_argument("--examples", type=int, default=5)
    args = ap.parse_args()

    ln, le = load(args.lsp)
    tn, te = load(args.treesitter)

    both = le & te
    lsp_only = le - te
    ts_only = te - le

    print(f"nodes   lsp {len(ln):>5}   tree-sitter {len(tn):>5}   shared ids {len(set(ln) & set(tn)):>5}")
    print(f"edges   lsp {len(le):>5}   tree-sitter {len(te):>5}")
    print()
    print(f"  agreed          {len(both):>5}  ({100 * len(both) / max(len(le | te), 1):.0f}% of the union)")
    print(f"  lsp only        {len(lsp_only):>5}  (tree-sitter could not resolve, or dropped as ambiguous)")
    print(f"  tree-sitter only{len(ts_only):>5}  (the LSP missed it, or the name match is wrong)")
    print()
    print(f"  recall of lsp by tree-sitter  {100 * len(both) / max(len(le), 1):.0f}%")
    print(f"  recall of tree-sitter by lsp  {100 * len(both) / max(len(te), 1):.0f}%")

    names = {**tn, **ln}

    def show(label: str, edges: set[tuple[str, str]]) -> None:
        if not edges:
            return
        print(f"\n{label}, {args.examples} examples:")
        for a, b in sorted(edges)[: args.examples]:
            na = names.get(a, {}).get("name", "?")
            nb = names.get(b, {}).get("name", "?")
            fa = Path(names.get(a, {}).get("file", a)).name
            fb = Path(names.get(b, {}).get("file", b)).name
            print(f"  {na} ({fa})  ->  {nb} ({fb})")

    show("LSP only", lsp_only)
    show("tree-sitter only", ts_only)

    # A name shared by many definitions is where name-based resolution guesses.
    dupes = Counter(n["name"] for n in tn.values())
    worst = [(k, v) for k, v in dupes.most_common(8) if v > 1]
    if worst:
        print("\nnames defined more than once (where tree-sitter must guess):")
        for name, count in worst:
            print(f"  {count:>3}  {name}")


if __name__ == "__main__":
    main()
