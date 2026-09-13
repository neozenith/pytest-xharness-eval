#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "tree-sitter>=0.25",
#   "tree-sitter-python>=0.25",
#   "tree-sitter-typescript>=0.23",
# ]
# ///
"""What tree-sitter actually sees, rendered as graphs and measured as vocabulary.

Three things this answers.

  grammar surface   how many node kinds and fields a grammar defines, and how
                    many of them a given codebase actually uses. That ratio is
                    vocabulary coverage: how much of the language this code
                    speaks.
  containment       folder > file > class > function, which tree-sitter hands
                    over for free in one parse and an LSP does not.
  calls             the edges, aggregated to file level so the picture is
                    readable rather than complete.

Writes tmp/richdocs/data/ts-*.json for the richdocs page.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import tree_sitter_python as tsp
import tree_sitter_typescript as tst
from tree_sitter import Language, Node, Parser

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "tmp" / "richdocs" / "data"

GRAMMARS = {
    ".py": ("python", tsp.language),
    ".ts": ("typescript", tst.language_typescript),
    ".tsx": ("tsx", tst.language_tsx),
}

# Data-encoding colours, fixed across themes.
PALETTE = ["#7c3aed", "#06a87c", "#e85080", "#02a0b9", "#d57004",
           "#7180fe", "#a86bec", "#858585", "#b45309", "#047857"]


def walk_kinds(node: Node, counter: Counter, depth: int, depths: list[int]) -> None:
    if node.is_named:
        counter[node.type] += 1
        depths.append(depth)
    for c in node.children:
        walk_kinds(c, counter, depth + 1, depths)


def defs_and_calls(node: Node, src: bytes, lang: str, out: dict, cls: str | None = None) -> None:
    """Definitions with their enclosing class, and call-site names."""
    is_py = lang == "python"
    def_types = {"function_definition"} if is_py else {
        "function_declaration", "method_definition", "arrow_function", "function_expression"}
    cls_types = {"class_definition"} if is_py else {"class_declaration"}
    call_types = {"call"} if is_py else {"call_expression", "jsx_opening_element", "jsx_self_closing_element"}

    here = cls
    if node.type in cls_types:
        nm = node.child_by_field_name("name")
        if nm is not None:
            here = src[nm.start_byte:nm.end_byte].decode("utf-8", "replace")
    if node.type in def_types:
        nm = node.child_by_field_name("name")
        name = src[nm.start_byte:nm.end_byte].decode("utf-8", "replace") if nm is not None else None
        if name is None and node.parent is not None and node.parent.type == "variable_declarator":
            t = node.parent.child_by_field_name("name")
            name = src[t.start_byte:t.end_byte].decode("utf-8", "replace") if t is not None else None
        if name and "callback" not in name:
            out["defs"].append({"name": name, "cls": cls, "line": node.start_point[0] + 1,
                                "start": node.start_byte, "end": node.end_byte})
    elif node.type in call_types:
        fn = node.child_by_field_name("function") or node.child_by_field_name("name")
        if fn is not None:
            txt = fn.children[-1] if fn.children else fn
            out["calls"].append({"name": src[txt.start_byte:txt.end_byte].decode("utf-8", "replace"),
                                 "at": node.start_byte})
    for c in node.children:
        defs_and_calls(c, src, lang, out, here)


def scan(root: Path, exts: tuple[str, ...], skip: list[str]) -> dict:
    parsers = {e: (GRAMMARS[e][0], Parser(Language(GRAMMARS[e][1]()))) for e in exts}
    kinds: Counter = Counter()
    depths: list[int] = []
    files: dict[str, dict] = {}

    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.suffix not in parsers or any(s in str(f) for s in skip):
            continue
        lang, parser = parsers[f.suffix]
        src = f.read_bytes()
        tree = parser.parse(src)
        walk_kinds(tree.root_node, kinds, 0, depths)
        bag: dict = {"defs": [], "calls": []}
        defs_and_calls(tree.root_node, src, lang, bag)
        rel = str(f.relative_to(REPO))
        files[rel] = {"folder": str(f.parent.relative_to(root)) or ".", "lang": lang,
                      "lines": len(src.splitlines()), **bag}

    available = 0
    for e in exts:
        L = Language(GRAMMARS[e][1]())
        available = max(available, sum(1 for i in range(L.node_kind_count) if L.node_kind_is_named(i)))

    return {"kinds": kinds, "depths": depths, "files": files, "available": available}


def build(name: str, root: Path, exts: tuple[str, ...], skip: list[str], min_weight: int = 2) -> dict:
    s = scan(root, exts, skip)
    files, kinds = s["files"], s["kinds"]

    # Resolve calls by name, same-file first, to aggregate file-to-file edges.
    by_name: dict[str, list[str]] = defaultdict(list)
    for rel, blob in files.items():
        for d in blob["defs"]:
            by_name[d["name"]].append(rel)

    edges: Counter = Counter()
    for rel, blob in files.items():
        local = {d["name"] for d in blob["defs"]}
        for c in blob["calls"]:
            if c["name"] in local:
                continue
            targets = by_name.get(c["name"], [])
            if len(targets) == 1 and targets[0] != rel:
                edges[(rel, targets[0])] += 1

    folders = sorted({b["folder"] for b in files.values()})
    colour = {f: PALETTE[i % len(PALETTE)] for i, f in enumerate(folders)}

    els: list[dict] = []
    for f in folders:
        els.append({"data": {"id": f"F::{f}", "label": f"{f}/", "category": f}})
    for rel, blob in files.items():
        els.append({"data": {
            "id": rel, "parent": f"F::{blob['folder']}",
            "label": f"{Path(rel).name}\n{len(blob['defs'])} fn, {blob['lines']} ln",
            **({"variant": "alt"} if len(blob["defs"]) == 0 else {}),
        }})
    # Only edges carrying real traffic. At weight 1 the picture is 88 hairlines
    # and no architecture; the threshold is a legibility choice, stated here so
    # nobody reads the drawing as the whole graph.
    shown = 0
    for (a, b), w in edges.items():
        if w < min_weight:
            continue
        shown += 1
        els.append({"data": {"source": a, "target": b, "label": str(w), "weight": w}})

    (OUT).mkdir(parents=True, exist_ok=True)
    (OUT / f"tsv-{name}-files.json").write_text(json.dumps(
        {"elements": els,
         "layout": {"name": "dagre", "rankDir": "LR", "nodeSep": 18, "rankSep": 110},
         "height": 900},
        indent=2), encoding="utf-8")

    used = len(kinds)
    depths = s["depths"]
    stats = {
        "name": name, "files": len(files),
        "defs": sum(len(b["defs"]) for b in files.values()),
        "calls": sum(len(b["calls"]) for b in files.values()),
        "file_edges": len(edges), "edges_drawn": shown,
        "kinds_used": used, "kinds_available": s["available"],
        "coverage": round(100 * used / s["available"], 1),
        "max_depth": max(depths), "mean_depth": round(sum(depths) / len(depths), 2),
        "total_nodes": sum(kinds.values()),
        "top_kinds": kinds.most_common(18),
        "colour": colour,
    }
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    args = ap.parse_args()

    py = build("py", REPO / "src" / "pytest_xharness_eval", (".py",), [])
    ts = build("ts", REPO / "report-ui" / "src", (".ts", ".tsx"), ["__tests__", ".test."])

    # Vocabulary coverage and the shape of what each grammar is used for.
    names = [k for k, _ in py["top_kinds"]][:14]
    pt = dict(py["top_kinds"])
    tt = dict(ts["top_kinds"])
    (OUT / "tsv-kinds.json").write_text(json.dumps({
        "data": [
            {"type": "bar", "name": "Python library",
             "x": names, "y": [round(100 * pt.get(k, 0) / py["total_nodes"], 2) for k in names]},
            {"type": "bar", "name": "TypeScript webapp",
             "x": names, "y": [round(100 * tt.get(k, 0) / ts["total_nodes"], 2) for k in names]},
        ],
        "layout": {"barmode": "group", "yaxis": {"title": "percent of all named AST nodes"},
                   "xaxis": {"tickangle": -35}, "legend": {"orientation": "h", "y": -0.45}},
        "height": 500,
    }, indent=2), encoding="utf-8")

    (REPO / "tmp" / "conductance" / "tsview.json").write_text(
        json.dumps({"py": {k: v for k, v in py.items() if k != "colour"},
                    "ts": {k: v for k, v in ts.items() if k != "colour"}}, indent=2), encoding="utf-8")

    hdr = f"{'':<22}{'Python':>12}{'TypeScript':>12}"
    print(f"\n{hdr}\n" + "-" * len(hdr))
    for label, key in [("files", "files"), ("definitions", "defs"), ("call sites", "calls"),
                       ("file-to-file edges", "file_edges"), ("AST nodes", "total_nodes"),
                       ("node kinds used", "kinds_used"), ("kinds available", "kinds_available"),
                       ("vocabulary coverage", "coverage"), ("max nesting depth", "max_depth"),
                       ("mean nesting depth", "mean_depth")]:
        print(f"{label:<22}{str(py[key]):>12}{str(ts[key]):>12}")
    print("\nwrote 3 payloads to tmp/richdocs/data/")


if __name__ == "__main__":
    main()
