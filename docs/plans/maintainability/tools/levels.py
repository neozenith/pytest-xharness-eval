#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# ///
"""Score conductance at every boundary level, not just the folder.

A call site crosses several boundaries at once. Conductance is defined on any
partition, so the same graph can be scored at each level and the levels compared.

    language   a process or a document contract
    folder     a directory
    file       a module
    class      the receiver
    function   a scope, crossed by definition, so it cannot discriminate

The number that matters per level is the share of call VOLUME that stays inside.
A level where almost everything crosses is not telling you about the code, it is
telling you the boundary is drawn too finely to be a boundary.

Usage: levels.py <graph.json> [<graph.json> ...]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]

# Each level names a node field, or derives one. Ordered coarse to fine.
LEVELS: list[tuple[str, callable]] = [
    ("language", lambda n: n.get("lang", "?")),
    ("folder", lambda n: n.get("folder") or str(Path(n["file"]).parent)),
    ("file", lambda n: n["file"]),
    ("class", lambda n: f"{n['file']}::{n['cls']}" if n.get("cls") else f"{n['file']}::<module>"),
]


def conductance(members: set[str], edges: list[tuple[str, str, int]], weighted: bool) -> dict:
    internal = cut = 0
    for a, b, sites in edges:
        w = sites if weighted else 1
        ina, inb = a in members, b in members
        if ina and inb:
            internal += w
        elif ina or inb:
            cut += w
    vol = 2 * internal + cut
    total = sum((s if weighted else 1) for _, _, s in edges) * 2
    denom = min(vol, total - vol)
    return {"internal": internal, "cut": cut, "vol": vol,
            "phi": round(cut / denom, 3) if denom else None}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("graphs", nargs="+", type=Path)
    ap.add_argument("--weighted", action="store_true", help="weight edges by call-site count")
    ap.add_argument("--min-vol", type=int, default=6,
                    help="clusters below this volume are not measurable, only counted")
    args = ap.parse_args()

    for path in args.graphs:
        raw = json.loads(path.read_text(encoding="utf-8"))
        nodes = {n["id"]: n for n in raw["nodes"]}
        edges = [(e["source"], e["target"], e.get("sites", 1))
                 for e in raw["edges"] if e["source"] in nodes and e["target"] in nodes]

        print(f"\n{path.name}   {raw.get('source', '')}")
        print(f"{len(nodes)} callables, {len(edges)} edges, "
              f"{sum(s for _, _, s in edges)} call sites, "
              f"extractor {raw.get('extractor', 'lsp')}")
        print(f"\n{'level':<10} {'clusters':>9} {'measurable':>11} {'inside %':>9} {'median phi':>11}")
        print("-" * 56)

        total_edges = len(edges) or 1
        for label, key in LEVELS:
            groups: dict[str, set[str]] = defaultdict(set)
            for nid, n in nodes.items():
                groups[key(n)].add(nid)

            # The headline per level: what share of calls stay inside a cluster.
            inside = sum(1 for a, b, _ in edges if key(nodes[a]) == key(nodes[b]))

            scored = [conductance(m, edges, args.weighted) for m in groups.values()]
            usable = sorted(s["phi"] for s in scored if s["phi"] is not None and s["vol"] >= args.min_vol)
            median = usable[len(usable) // 2] if usable else None

            print(f"{label:<10} {len(groups):>9} {len(usable):>11} "
                  f"{100 * inside / total_edges:>8.0f}% "
                  f"{median if median is not None else '-':>11}")

        print(f"\n{'':<10} inside % is the share of call edges that do NOT cross that boundary.")


if __name__ == "__main__":
    main()
