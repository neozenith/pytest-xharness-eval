#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "tree-sitter>=0.25",
#   "tree-sitter-python>=0.25",
#   "tree-sitter-typescript>=0.23",
# ]
# ///
"""Emit the graph reviewable-ui renders: every boundary, every per-node metric.

One JSON, because the app should not have to compute anything a parser already
knows. The shape is mirrored in reviewable-ui/src/lib/types.ts; change one and
change the other.

Per node it carries all four boundary levels at once (language, folder, file,
class) so the app can re-cluster without a round trip, plus the metrics that were
free in the same walk: nesting depth, source lines, call-site count and leverage.

Per cluster it carries conductance and modularity at each level, since those need
the whole graph and cannot be derived from one node.

Usage:
    graphdata.py --out reviewable-ui/public/graph.json \
        --source src/pytest_xharness_eval:python \
        --source report-ui/src:typescript --skip "__tests__,.test."
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import tree_sitter_python as tsp
import tree_sitter_typescript as tst
from tree_sitter import Language, Node, Parser

REPO = Path(__file__).resolve().parents[4]

GRAMMARS = {
    ".py": ("python", tsp.language),
    ".ts": ("typescript", tst.language_typescript),
    ".tsx": ("typescript", tst.language_tsx),
}
EXT_FOR = {"python": (".py",), "typescript": (".ts", ".tsx")}

DEF_TYPES = {
    "python": {"function_definition"},
    "typescript": {"function_declaration", "method_definition", "arrow_function", "function_expression"},
}
CLS_TYPES = {"python": {"class_definition"}, "typescript": {"class_declaration"}}
CALL_TYPES = {
    "python": {"call"},
    "typescript": {"call_expression", "jsx_opening_element", "jsx_self_closing_element"},
}
ANON = ("callback", "<anonymous>")


def text(node: Node, src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8", "replace")


def name_of(node: Node, src: bytes) -> str | None:
    nm = node.child_by_field_name("name")
    if nm is not None:
        return text(nm.children[-1] if nm.children else nm, src)
    if node.parent is not None and node.parent.type in ("variable_declarator", "assignment"):
        t = node.parent.child_by_field_name("name") or node.parent.child_by_field_name("left")
        if t is not None and t.type in ("identifier", "property_identifier"):
            return text(t, src)
    return None


def call_name(node: Node, src: bytes) -> tuple[str, bool] | None:
    """The called name, and whether the call had a receiver (`x.f()`)."""
    fn = node.child_by_field_name("function")
    if fn is None:
        nm = node.child_by_field_name("name")
        return (text(nm.children[-1] if nm.children else nm, src), False) if nm is not None else None
    if fn.type == "identifier":
        return (text(fn, src), False)
    prop = fn.child_by_field_name("property") or fn.child_by_field_name("attribute")
    return (text(prop, src), True) if prop is not None else None


def walk(node: Node, src: bytes, lang: str, bag: dict, depth: int, cls: str | None) -> None:
    bag["depths"].append(depth)
    bag["kinds"][node.type] += 1 if node.is_named else 0

    here = cls
    if node.type in CLS_TYPES[lang]:
        here = name_of(node, src) or cls
    if node.type in DEF_TYPES[lang]:
        nm = name_of(node, src)
        if nm and not any(a in nm for a in ANON):
            bag["defs"].append({
                "name": nm, "cls": cls, "line": node.start_point[0] + 1,
                "endLine": node.end_point[0] + 1, "depth": depth,
                "start": node.start_byte, "end": node.end_byte,
                "isMethod": cls is not None,
            })
    elif node.type in CALL_TYPES[lang]:
        got = call_name(node, src)
        if got:
            bag["calls"].append({"name": got[0], "attr": got[1], "at": node.start_byte})
    for c in node.children:
        walk(c, src, lang, bag, depth + 1, here)


def innermost(defs: list[dict], offset: int) -> dict | None:
    best = None
    for d in defs:
        if d["start"] <= offset < d["end"] and (
            best is None or (d["end"] - d["start"]) < (best["end"] - best["start"])
        ):
            best = d
    return best


def conductance(members: set[str], edges: list[tuple[str, str]]) -> dict:
    internal = cut = 0
    for a, b in edges:
        ina, inb = a in members, b in members
        if ina and inb:
            internal += 1
        elif ina or inb:
            cut += 1
    vol = 2 * internal + cut
    denom = min(vol, 2 * len(edges) - vol)
    return {"internal": internal, "cut": cut, "vol": vol,
            "phi": round(cut / denom, 3) if denom else None,
            "measurable": vol >= 6}


def modularity(assign: dict[str, str], edges: list[tuple[str, str]]) -> float:
    m = len(edges)
    if not m:
        return 0.0
    deg: Counter[str] = Counter()
    for a, b in edges:
        deg[a] += 1
        deg[b] += 1
    e_in: Counter[str] = Counter()
    d_tot: Counter[str] = Counter()
    for n, c in assign.items():
        d_tot[c] += deg[n]
    for a, b in edges:
        if assign[a] == assign[b]:
            e_in[assign[a]] += 1
    return round(sum((e_in[c] / m) - (d_tot[c] / (2 * m)) ** 2 for c in d_tot), 4)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", action="append", required=True,
                    help="path:language, repeatable")
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip", default="")
    args = ap.parse_args()

    skip = [s.strip() for s in args.skip.split(",") if s.strip()]
    parsers: dict[str, Parser] = {}
    nodes: dict[str, dict] = {}
    per_file: dict[str, dict] = {}
    sources = []

    for spec in args.source:
        rel, lang = spec.rsplit(":", 1)
        root = (REPO / rel).resolve()
        exts = EXT_FOR[lang]
        for e in exts:
            parsers.setdefault(e, Parser(Language(GRAMMARS[e][1]())))
        n_files = 0
        for f in sorted(root.rglob("*")):
            if not f.is_file() or f.suffix not in exts or any(s in str(f) for s in skip):
                continue
            n_files += 1
            src = f.read_bytes()
            bag = {"defs": [], "calls": [], "depths": [], "kinds": Counter()}
            walk(parsers[f.suffix].parse(src).root_node, src, lang, bag, 0, None)
            key = str(f.relative_to(REPO))
            per_file[key] = {**bag, "lang": lang, "root": rel,
                             "folder": str(f.parent.relative_to(root)) or ".",
                             "lines": len(src.splitlines())}
            for d in bag["defs"]:
                nid = f"{key}:{d['line']}"
                nodes[nid] = {
                    "id": nid, "name": d["name"], "lang": lang, "root": rel,
                    "folder": f"{rel}/{per_file[key]['folder']}".rstrip("/."),
                    "file": key, "cls": d["cls"], "line": d["line"],
                    "nloc": d["endLine"] - d["line"] + 1, "depth": d["depth"],
                    "isMethod": d["isMethod"],
                }
        sources.append({"root": rel, "lang": lang, "files": n_files})

    # Resolve by name: same file first, then a unique same-language definition of
    # the matching kind. A receiver means a method, a bare call means a function.
    by_key: dict[tuple[str, bool, str], list[str]] = defaultdict(list)
    for nid, n in nodes.items():
        by_key[(n["name"], n["isMethod"], n["lang"])].append(nid)

    edge_sites: Counter[tuple[str, str]] = Counter()
    unresolved = ambiguous = 0
    for key, blob in per_file.items():
        local = {(d["name"], d["isMethod"]): f"{key}:{d['line']}" for d in blob["defs"]}
        for c in blob["calls"]:
            caller = innermost(blob["defs"], c["at"])
            if caller is None:
                continue
            src_id = f"{key}:{caller['line']}"
            hit = local.get((c["name"], c["attr"]))
            if hit is None:
                cands = by_key.get((c["name"], c["attr"], blob["lang"]), [])
                if len(cands) == 1:
                    hit = cands[0]
                elif len(cands) > 1:
                    ambiguous += 1
                    continue
                else:
                    unresolved += 1
                    continue
            if hit != src_id:
                edge_sites[(src_id, hit)] += 1

    edges = list(edge_sites)
    indeg: Counter[str] = Counter(b for _, b in edges)
    outdeg: Counter[str] = Counter(a for a, _ in edges)
    sites_in: Counter[str] = Counter()
    for (_a, b), w in edge_sites.items():
        sites_in[b] += w
    for nid, n in nodes.items():
        n["leverage"] = indeg[nid]
        n["callSites"] = sites_in[nid]
        n["fanOut"] = outdeg[nid]

    levels = {
        "language": lambda n: n["lang"],
        "folder": lambda n: n["folder"],
        "file": lambda n: n["file"],
        "class": lambda n: f"{n['file']}::{n['cls'] or '<module>'}",
    }
    clusters: dict[str, dict] = {}
    summary: dict[str, dict] = {}
    for label, key in levels.items():
        groups: dict[str, set[str]] = defaultdict(set)
        for nid, n in nodes.items():
            groups[key(n)].add(nid)
        clusters[label] = {
            g: {**conductance(m, edges), "names": len(m),
                "nloc": sum(nodes[i]["nloc"] for i in m)}
            for g, m in groups.items()
        }
        inside = sum(1 for a, b in edges if key(nodes[a]) == key(nodes[b]))
        summary[label] = {
            "clusters": len(groups),
            "modularity": modularity({i: key(n) for i, n in nodes.items()}, edges),
            "insidePct": round(100 * inside / max(len(edges), 1)),
        }

    payload = {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "sources": sources,
        "nodes": list(nodes.values()),
        "edges": [{"source": a, "target": b, "sites": w} for (a, b), w in edge_sites.items()],
        "clusters": clusters,
        "summary": summary,
        "totals": {
            "nodes": len(nodes), "edges": len(edges),
            "callSites": sum(edge_sites.values()),
            "resolvedPct": round(100 * sum(edge_sites.values())
                                 / max(sum(edge_sites.values()) + unresolved + ambiguous, 1)),
            "ambiguous": ambiguous, "unresolved": unresolved,
            "orphanPct": round(100 * sum(1 for i in nodes if indeg[i] == 0) / max(len(nodes), 1)),
            "maxDepth": max((n["depth"] for n in nodes.values()), default=0),
        },
    }

    dest = REPO / args.out
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload), encoding="utf-8")
    t = payload["totals"]
    print(f"{t['nodes']} nodes, {t['edges']} edges, {t['callSites']} call sites")
    print(f"orphans {t['orphanPct']}%  ambiguous {t['ambiguous']}  unresolved {t['unresolved']}")
    for label, s in summary.items():
        print(f"  {label:<9} k={s['clusters']:<4} Q={s['modularity']:<8} inside={s['insidePct']}%")
    print(f"wrote {dest.relative_to(REPO)} ({dest.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
