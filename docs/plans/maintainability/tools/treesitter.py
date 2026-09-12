#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "tree-sitter>=0.25",
#   "tree-sitter-python>=0.25",
#   "tree-sitter-typescript>=0.23",
# ]
# ///
"""Extract a call graph with tree-sitter, carrying the full boundary nesting.

Why this exists alongside callgraph.py (which uses an LSP):

  LSP          precise cross-file resolution, one language server per language,
               slow, fragile, and it answers a position with a plausible empty
               result when the workspace is not fully open.
  tree-sitter  no server, one parser per grammar, fast, and it never lies about
               what the source says. It cannot RESOLVE: it sees `foo()`, not
               which `foo`. Resolution here is by name, and the ambiguity rate
               is reported so the reader can judge it.

The reason to prefer it for this work is not speed. It is that the syntax tree
carries the whole boundary hierarchy at once -- function inside class inside
file inside folder -- so conductance can be scored at every level rather than
only at the folder, which is the weakest of them.

Output: one node per callable, each carrying every boundary it sits inside.

    {"id","name","lang","folder","file","cls","line"}
    {"source","target","sites","resolution"}
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from tree_sitter import Language, Node, Parser, Query, QueryCursor

import tree_sitter_python as tsp
import tree_sitter_typescript as tst

REPO = Path(__file__).resolve().parents[4]

# Per grammar: which node types define a callable, which define a class, and
# which node types are a call site. Everything else is shared.
GRAMMARS: dict[str, dict[str, Any]] = {
    "python": {
        "language": lambda: Language(tsp.language()),
        "exts": {".py"},
        "defs": {"function_definition"},
        "classes": {"class_definition"},
        "calls": {"call"},
    },
    "typescript": {
        "language": lambda: Language(tst.language_typescript()),
        "exts": {".ts"},
        "defs": {"function_declaration", "method_definition", "arrow_function", "function_expression"},
        "classes": {"class_declaration"},
        "calls": {"call_expression", "jsx_opening_element", "jsx_self_closing_element"},
    },
    "tsx": {
        "language": lambda: Language(tst.language_tsx()),
        "exts": {".tsx"},
        "defs": {"function_declaration", "method_definition", "arrow_function", "function_expression"},
        "classes": {"class_declaration"},
        "calls": {"call_expression", "jsx_opening_element", "jsx_self_closing_element"},
    },
}


def node_name(node: Node, src: bytes) -> str | None:
    """The identifier a definition or call site is named by."""
    named = node.child_by_field_name("name")
    if named is not None:
        if named.type in ("identifier", "type_identifier", "property_identifier"):
            return src[named.start_byte : named.end_byte].decode("utf-8", "replace")
        # JSX <Foo.Bar /> and obj.method() both end in the rightmost identifier.
        last = named.children[-1] if named.children else None
        if last is not None:
            return src[last.start_byte : last.end_byte].decode("utf-8", "replace")
        return src[named.start_byte : named.end_byte].decode("utf-8", "replace")

    fn = node.child_by_field_name("function")
    if fn is not None:
        if fn.type == "identifier":
            return src[fn.start_byte : fn.end_byte].decode("utf-8", "replace")
        prop = fn.child_by_field_name("property") or fn.child_by_field_name("attribute")
        if prop is not None:
            return src[prop.start_byte : prop.end_byte].decode("utf-8", "replace")

    # `const Foo = () => ...`: the arrow function is anonymous, its name is the
    # variable it is bound to. Without this every React component is nameless.
    if node.type in ("arrow_function", "function_expression"):
        parent = node.parent
        if parent is not None and parent.type in ("variable_declarator", "assignment"):
            target = parent.child_by_field_name("name") or parent.child_by_field_name("left")
            if target is not None and target.type in ("identifier", "property_identifier"):
                return src[target.start_byte : target.end_byte].decode("utf-8", "replace")
    return None


def is_attribute_call(node: Node) -> bool:
    """Is this `x.foo()` rather than `foo()`?

    The distinction is what stops every `d.get(k)` on a dict resolving to a
    module-level function called `get`. A receiver means a method, so it may
    only match a definition that lives inside a class, and a bare call may only
    match one that does not.
    """
    fn = node.child_by_field_name("function")
    if fn is None:
        return False  # JSX elements have no receiver
    return fn.type in ("attribute", "member_expression")


def walk(node: Node, src: bytes, g: dict[str, Any], defs: list, calls: list, cls: str | None = None) -> None:
    """One pass, carrying the enclosing class down so nesting is recorded."""
    here_cls = cls
    if node.type in g["classes"]:
        here_cls = node_name(node, src) or cls

    if node.type in g["defs"]:
        name = node_name(node, src)
        if name:
            defs.append({"name": name, "cls": cls, "line": node.start_point[0] + 1,
                         "start": node.start_byte, "end": node.end_byte})
    elif node.type in g["calls"]:
        name = node_name(node, src)
        if name:
            calls.append({
                "name": name,
                "at": node.start_byte,
                "line": node.start_point[0] + 1,
                "attr": is_attribute_call(node),
            })

    for child in node.children:
        walk(child, src, g, defs, calls, here_cls)


def enclosing(defs: list[dict], offset: int) -> dict | None:
    """The innermost definition whose byte range contains this call site."""
    best = None
    for d in defs:
        if d["start"] <= offset < d["end"]:
            if best is None or (d["end"] - d["start"]) < (best["end"] - best["start"]):
                best = d
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sources", nargs="+", help="directories to walk, relative to the repo root")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--exclude", default="", help="comma-separated path fragments to skip")
    args = ap.parse_args()

    skip = [s.strip() for s in args.exclude.split(",") if s.strip()]
    parsers = {name: Parser(g["language"]()) for name, g in GRAMMARS.items()}

    nodes: dict[str, dict] = {}
    per_file: dict[str, tuple[str, list, list]] = {}

    for source in args.sources:
        root = (REPO / source).resolve()
        for f in sorted(root.rglob("*")):
            if not f.is_file() or any(s in str(f) for s in skip):
                continue
            lang = next((n for n, g in GRAMMARS.items() if f.suffix in g["exts"]), None)
            if lang is None:
                continue
            g = GRAMMARS[lang]
            src = f.read_bytes()
            tree = parsers[lang].parse(src)
            defs: list[dict] = []
            calls: list[dict] = []
            walk(tree.root_node, src, g, defs, calls)

            rel = str(f.relative_to(REPO))
            folder = str(f.parent.relative_to(REPO))
            per_file[rel] = (lang, defs, calls)
            for d in defs:
                nodes[f"{rel}:{d['line']}"] = {
                    "id": f"{rel}:{d['line']}",
                    "name": d["name"],
                    "lang": "typescript" if lang in ("typescript", "tsx") else lang,
                    "folder": folder,
                    "file": rel,
                    "cls": d["cls"],
                    "line": d["line"],
                }

    # Name-based resolution. Same file wins, then a globally unique name.
    # Anything else is ambiguous and counted rather than guessed at.
    # Indexed separately by kind: a method (defined in a class) can only be the
    # target of `x.foo()`, and a plain function only of `foo()`.
    by_name: dict[tuple[str, bool], list[str]] = defaultdict(list)
    for nid, n in nodes.items():
        by_name[(n["name"], n["cls"] is not None)].append(nid)

    edges: dict[tuple[str, str], int] = defaultdict(int)
    stats = {"resolved": 0, "ambiguous": 0, "unresolved": 0}

    for rel, (raw_lang, defs, calls) in per_file.items():
        file_lang = "typescript" if raw_lang in ("typescript", "tsx") else raw_lang
        local = {(d["name"], d["cls"] is not None): f"{rel}:{d['line']}" for d in defs}
        for c in calls:
            caller = enclosing(defs, c["at"])
            if caller is None:
                continue  # a top-level call has no calling function
            src_id = f"{rel}:{caller['line']}"
            key = (c["name"], c["attr"])
            if key in local:
                dst_id = local[key]
            else:
                # Resolution never crosses a language. A Python `of` and a
                # TypeScript `of` share a name and nothing else, and a name
                # match across languages would be pure invention. Real
                # cross-language edges are contracts, added separately.
                candidates = [c for c in by_name.get(key, []) if nodes[c]["lang"] == file_lang]
                if len(candidates) == 1:
                    dst_id = candidates[0]
                elif len(candidates) > 1:
                    stats["ambiguous"] += 1
                    continue
                else:
                    stats["unresolved"] += 1
                    continue
            if dst_id == src_id:
                continue
            edges[(src_id, dst_id)] += 1
            stats["resolved"] += 1

    out = {
        "source": ", ".join(args.sources),
        "extractor": "tree-sitter",
        "stats": stats,
        "nodes": list(nodes.values()),
        "edges": [{"source": a, "target": b, "sites": n} for (a, b), n in sorted(edges.items())],
    }
    dest = REPO / args.out
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")

    total = sum(stats.values()) or 1
    print(f"{len(nodes)} callables, {len(edges)} edges, {sum(edges.values())} call sites")
    print(f"resolved {stats['resolved']}  ambiguous {stats['ambiguous']} "
          f"({100 * stats['ambiguous'] / total:.0f}%)  unresolved {stats['unresolved']}")
    print(f"wrote {dest.relative_to(REPO)}", file=sys.stderr)


if __name__ == "__main__":
    main()
