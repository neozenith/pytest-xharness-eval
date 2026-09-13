#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "tree-sitter>=0.25",
#   "tree-sitter-python>=0.25",
#   "tree-sitter-typescript>=0.23",
# ]
# ///
"""Halstead vocabulary from the tree-sitter token stream, as compressibility.

Halstead counts the DISTINCT operators and operands in a program, `n`, and their
TOTAL occurrences, `N`. From those:

    volume V = N * log2(n)

which is the bits needed to write the program down once you have been handed its
vocabulary. That is a description length, published in 1977, a year before
Rissanen named MDL, and it maps onto the two-part code directly:

    L(H)      the vocabulary, n distinct tokens someone has to learn
    L(D|H)    V = N log2(n), the program spelled out using them

The ratio that matters here is not the volume, it is

    reuse = N / n

how many times the average vocabulary item is used. That is leverage measured at
the token level rather than at the call site. A program where every name appears
once has reuse near 1 and compresses badly. One where a small vocabulary is
worked hard has high reuse and compresses well.

Empirically this is not a fringe metric. In the Peitek fMRI study Halstead
volume correlated -0.45 with measured comprehension, against -0.46 for lines of
code and -0.09 for McCabe.

WHY NOT `radon hal`: radon's Halstead counts a narrow arithmetic operator set
only. On this repository it reports 2,158 total tokens where lizard counts
22,792, and returns all zeros for a module built from calls and attribute
access. It is not usable for this question.

Usage: halstead.py <dir> [<dir> ...] [--ext .py]
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import tree_sitter_python as tsp
import tree_sitter_typescript as tst
from tree_sitter import Language, Node, Parser

REPO = Path(__file__).resolve().parents[4]

GRAMMARS = {
    ".py": lambda: Language(tsp.language()),
    ".ts": lambda: Language(tst.language_typescript()),
    ".tsx": lambda: Language(tst.language_tsx()),
}

# An operand is a thing the program talks ABOUT: a name or a literal. Everything
# else a leaf can be -- punctuation, an operator, a keyword -- is an operator,
# the thing the program DOES. That is Halstead's split.
OPERAND_TYPES = {
    "identifier", "type_identifier", "property_identifier", "field_identifier",
    "shorthand_property_identifier", "shorthand_property_identifier_pattern",
    "string_content", "integer", "float", "number", "true", "false", "none",
    "null", "undefined", "string_fragment",
}


def tokens(node: Node, src: bytes, ops: Counter, opnds: Counter) -> None:
    if node.child_count == 0:
        text = src[node.start_byte : node.end_byte].decode("utf-8", "replace")
        if not text.strip():
            return
        if node.type in OPERAND_TYPES:
            opnds[text] += 1
        else:
            ops[node.type] += 1
        return
    for c in node.children:
        tokens(c, src, ops, opnds)


def measure(root: Path, exts: tuple[str, ...], skip: list[str]) -> dict:
    parsers = {e: Parser(GRAMMARS[e]()) for e in exts if e in GRAMMARS}
    ops: Counter = Counter()
    opnds: Counter = Counter()
    files = 0
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.suffix not in parsers:
            continue
        if any(s in str(f) for s in skip):
            continue
        files += 1
        src = f.read_bytes()
        tokens(parsers[f.suffix].parse(src).root_node, src, ops, opnds)

    h1, h2 = len(ops), len(opnds)
    n1, n2 = sum(ops.values()), sum(opnds.values())
    vocab, length = h1 + h2, n1 + n2
    return {
        "files": files,
        "h1_distinct_operators": h1,
        "h2_distinct_operands": h2,
        "N1_total_operators": n1,
        "N2_total_operands": n2,
        "vocabulary": vocab,
        "length": length,
        "reuse": round(length / vocab, 2) if vocab else None,
        "operand_reuse": round(n2 / h2, 2) if h2 else None,
        "volume": round(length * math.log2(vocab)) if vocab > 1 else 0,
        # Volume per distinct name: the bits you pay for each thing you learn.
        "volume_per_name": round(length * math.log2(vocab) / vocab, 1) if vocab > 1 else 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--ext", default=".py")
    ap.add_argument("--skip", default="")
    ap.add_argument("--out", default="halstead.json")
    args = ap.parse_args()

    exts = tuple(e.strip() for e in args.ext.split(","))
    skip = [s.strip() for s in args.skip.split(",") if s.strip()]

    rows = []
    for d in args.dirs:
        p = REPO / d
        if not p.exists():
            continue
        meta = p / "_experiment.json"
        m = json.loads(meta.read_text()) if meta.exists() else {}
        rows.append({"dir": d, "transform": m.get("transform", "source"),
                     "k": m.get("k", ""), **measure(p, exts, skip)})

    dest = REPO / "tmp" / "conductance" / args.out
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    base = rows[0] if rows else {}
    hdr = (f"{'variant':<18} {'vocab n':>8} {'length N':>9} {'reuse':>7} "
           f"{'operand':>8} {'volume':>9} {'V/name':>7} {'d reuse':>9} {'d V':>8}")
    print(f"\n{hdr}\n" + "-" * len(hdr))
    for r in rows:
        dr = f"{100 * (r['reuse'] - base['reuse']) / base['reuse']:+.1f}%" if base.get("reuse") else "-"
        dv = f"{100 * (r['volume'] - base['volume']) / base['volume']:+.1f}%" if base.get("volume") else "-"
        label = f"{r['transform']}{(' ' + str(r['k'])) if r['k'] not in ('', None) else ''}"
        print(f"{label:<18} {r['vocabulary']:>8} {r['length']:>9} {r['reuse']:>7} "
              f"{r['operand_reuse']:>8} {r['volume']:>9} {r['volume_per_name']:>7} {dr:>9} {dv:>8}")
    print(f"\nwrote {dest.relative_to(REPO)}")


if __name__ == "__main__":
    main()
