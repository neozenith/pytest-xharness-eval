#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = ["sqlite-muninn>=0.4.0"]
# ///
"""Score a folder structure as a model of the call graph, in bits.

A partition of the names is a *model* H. Its single prediction is "a call stays
inside a cluster". The two-part code from README.md then applies directly:

    L(H)      how many bits to state which cluster each name is in
    L(D|H)    how many bits to state the call edges, given that
    total     L(H) + L(D|H) -- lower is a better description

Coding scheme (a defensible choice, not the canonical one -- see the caveat the
document carries):

    L(H)   = n * log2(k)                  one cluster id per name
    L(D|H) = sum over edges of
                log2(|C_target|)          internal: index within the cluster
                log2(n)                   crossing: a global index

This is what makes "the folders match the call graph" a number rather than an
impression. It also prices Leiden's 85 communities honestly: a partition that
lowers the residual by inventing clusters pays for every one of them in L(H).

Compares: one cluster, the declared folders, the files, Leiden, one per name.
"""

from __future__ import annotations

import argparse
import json
import os
import math
import sqlite3
from collections import Counter
from pathlib import Path

import sqlite_muninn

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
# Graph JSON lives with the run output, not beside the script.
DATA = Path(os.environ.get("CONDUCTANCE_DATA", REPO / "tmp" / "conductance"))


def two_part_code(assign: dict[str, str | int], edges: list[tuple[str, str]], n: int) -> dict[str, float | int]:
    sizes = Counter(assign.values())
    k = len(sizes)
    l_h = n * math.log2(k) if k > 1 else 0.0

    l_d_given_h = 0.0
    crossing = 0
    for a, b in edges:
        if assign[a] == assign[b]:
            l_d_given_h += math.log2(max(sizes[assign[b]], 2))
        else:
            crossing += 1
            l_d_given_h += math.log2(n)

    return {
        "clusters": k,
        "L(H)": round(l_h),
        "L(D|H)": round(l_d_given_h),
        "total": round(l_h + l_d_given_h),
        "crossing": crossing,
        "crossing_pct": round(100 * crossing / len(edges), 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--graph", type=Path, default=DATA / "callgraph.json")
    ap.add_argument("--prefix", default="")
    args = ap.parse_args()

    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = [(e["source"], e["target"]) for e in graph["edges"]]

    db = sqlite3.connect(":memory:")
    db.enable_load_extension(True)
    sqlite_muninn.load(db)
    db.execute("CREATE TABLE calls(src TEXT, dst TEXT)")
    db.executemany("INSERT INTO calls VALUES(?,?)", edges)
    leiden = {r[0]: r[1] for r in db.execute("SELECT node, community_id FROM graph_leiden('calls','src','dst')")}

    # Score on the connected subgraph: names with no call edge are invisible to
    # every partition equally, so including them only adds a constant.
    connected = sorted(set(leiden))
    scoped = [(a, b) for a, b in edges if a in leiden and b in leiden]
    n = len(connected)

    # A codebase whose top-level folders are lopsided (one folder holding most
    # names) is barely partitioned at depth 1. Scoring depth 2 as well asks
    # whether the nested folders earn boundaries the top level does not.
    source = graph.get("source", "")

    def depth2(nid: str) -> str:
        rel = nodes[nid]["file"]
        parts = rel[len(source) :].strip("/").split("/")
        return "/".join(parts[:2]) if len(parts) > 2 else (parts[0] if len(parts) > 1 else "<root>")

    partitions = {
        "one cluster (no architecture)": {nid: 0 for nid in connected},
        "the declared folders": {nid: nodes[nid]["layer"] for nid in connected},
        "declared folders, depth 2": {nid: depth2(nid) for nid in connected},
        "one cluster per file": {nid: nodes[nid]["file"] for nid in connected},
        "Leiden communities": {nid: leiden[nid] for nid in connected},
        "one cluster per name": {nid: nid for nid in connected},
    }

    results = {name: two_part_code(a, scoped, n) for name, a in partitions.items()}

    # The comparison that survives the scheme's degeneracy at k=1: how many bits
    # of the edge list does this partition save, per boundary it asks you to
    # learn? This is "leverage per name" from README.md, asked of a boundary.
    baseline = results["one cluster (no architecture)"]["L(D|H)"]
    for name, r in results.items():
        saved = baseline - r["L(D|H)"]
        extra = r["clusters"] - 1
        r["bits_saved"] = saved
        r["saved_pct"] = round(100 * saved / baseline, 1)
        r["bits_per_cluster"] = round(saved / extra, 1) if extra else 0.0
    (DATA / f"{args.prefix}mdl.json").write_text(json.dumps({"n": n, "edges": len(scoped), "results": results}, indent=2), encoding="utf-8")

    print(f"{n} names, {len(scoped)} call edges between them\n")
    print(f"{'partition':<32} {'k':>5} {'L(H)':>7} {'L(D|H)':>8} {'saved':>7} {'per cluster':>12}")
    print("-" * 78)
    for name, r in results.items():
        print(
            f"{name:<32} {r['clusters']:>5} {r['L(H)']:>7} {r['L(D|H)']:>8} "
            f"{r['saved_pct']:>6}% {r['bits_per_cluster']:>12}"
        )
    ranked = sorted(
        ((k, v) for k, v in results.items() if v["clusters"] > 1),
        key=lambda kv: -kv[1]["bits_per_cluster"],
    )
    print(f"\nmost efficient partition: {ranked[0][0]} at {ranked[0][1]['bits_per_cluster']} bits per boundary")


if __name__ == "__main__":
    main()
