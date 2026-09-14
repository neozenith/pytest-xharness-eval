#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "tree-sitter>=0.25",
#   "tree-sitter-python>=0.25",
#   "tree-sitter-typescript>=0.23",
# ]
# ///
"""Per-function screen load: symbols held, charged BIC-style, scaled by screens overflowed.

    load = k ln(N) x max(1, s / H)

    s  visual source lines: non-blank, non-comment, wrapped at the line-length limit W
    N  tokens in the function (leaves, comments excluded)
    k  distinct identifier spellings in the function
    H  screen height in lines

Usage: uv run docs/plans/maintainability/tools/screenload.py --out tmp/screenload.json
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import tree_sitter_python as tsp
import tree_sitter_typescript as tst
from tree_sitter import Language, Node, Parser

GRAMMARS = {
    ".py": tsp.language,
    ".ts": tst.language_typescript,
    ".tsx": tst.language_tsx,
}
DEF_TYPES = {"function_definition", "function_declaration", "method_definition", "arrow_function", "function_expression"}
IDENT_TYPES = {"identifier", "property_identifier", "type_identifier", "shorthand_property_identifier"}
COMMENT_TYPES = {"comment"}
SOURCES = [("src/pytest_xharness_eval", ()), ("report-ui/src", ("__tests__", ".test."))]


def name_of(node: Node, src: bytes) -> str | None:
    nm = node.child_by_field_name("name")
    if nm is None and node.parent is not None and node.parent.type in ("variable_declarator", "assignment"):
        nm = node.parent.child_by_field_name("name") or node.parent.child_by_field_name("left")
    return src[nm.start_byte : nm.end_byte].decode() if nm is not None else None


def leaves(node: Node):
    if node.type in COMMENT_TYPES:
        return
    if node.child_count == 0:
        yield node
    for c in node.children:
        yield from leaves(c)


def measure(node: Node, src: bytes, width: int) -> dict:
    toks = list(leaves(node))
    code_rows = {t.start_point[0] for t in toks} | {t.end_point[0] for t in toks}
    lines = src.decode("utf-8", "replace").splitlines()
    visual = sum(max(1, math.ceil(len(lines[r].rstrip()) / width)) for r in code_rows if r < len(lines))
    idents = {src[t.start_byte : t.end_byte] for t in toks if t.type in IDENT_TYPES}
    return {"s": visual, "N": len(toks), "k": len(idents)}


def defs(node: Node, src: bytes):
    if node.type in DEF_TYPES:
        nm = name_of(node, src)
        if nm:
            yield nm, node
    for c in node.children:
        yield from defs(c, src)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--height", type=int, default=50)
    ap.add_argument("--width", type=int, default=120)
    args = ap.parse_args()

    rows = []
    for root, skip in SOURCES:
        for path in sorted(Path(root).rglob("*")):
            lang = GRAMMARS.get(path.suffix)
            if lang is None or any(s in str(path) for s in skip):
                continue
            src = path.read_bytes()
            tree = Parser(Language(lang())).parse(src)
            for nm, node in defs(tree.root_node, src):
                m = measure(node, src, args.width)
                screens = max(1.0, m["s"] / args.height)
                symbols = m["k"] * math.log(max(m["N"], 2))
                rows.append({"file": str(path), "name": nm, "line": node.start_point[0] + 1, **m,
                             "symbols": round(symbols, 1), "screens": round(screens, 2),
                             "load": round(symbols * screens, 1)})

    rows.sort(key=lambda r: -r["load"])
    total = sum(r["load"] for r in rows)
    over = [r for r in rows if r["s"] > args.height]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"height": args.height, "width": args.width, "functions": len(rows),
                                    "total_load": round(total, 1), "over_one_screen": len(over),
                                    "rows": rows}, indent=2), encoding="utf-8")
    print(f"functions={len(rows)} over_one_screen={len(over)} total_load={total:.0f}")
    for root, _ in SOURCES:
        mine = [r for r in rows if r["file"].startswith(root)]
        big = [r for r in mine if r["s"] > args.height]
        share = sum(r["load"] for r in big) / max(1e-9, sum(r["load"] for r in mine))
        print(f"{root}: functions={len(mine)} over={len(big)} load_share_over={share:.1%} top={mine[0]['name'] if mine else None}")
        for r in mine[:4]:
            print(f"   {r['load']:8.1f}  s={r['s']} N={r['N']} k={r['k']} {r['file']}:{r['line']} {r['name']}")
    for r in rows[:12]:
        print(f"{r['load']:8.1f}  s={r['s']:3d} N={r['N']:4d} k={r['k']:3d} sym={r['symbols']:6.1f} "
              f"scr={r['screens']:.2f}  {r['file']}:{r['line']} {r['name']}")


if __name__ == "__main__":
    main()
