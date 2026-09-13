#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# ///
"""Score a call graph: conductance per cluster, leverage per name.

Reads a graph produced by callgraph.py and emits <prefix>scores.json.

Definitions used, stated so a document can cite them exactly:

  vol(S)    sum of degrees of nodes in S, i.e. every edge endpoint incident to S.
            An edge inside S contributes 2; a boundary edge contributes 1.
  cut(S)    edges with exactly one endpoint in S.
  phi(S)    cut(S) / min(vol(S), vol(V\\S))   -- standard graph conductance.
            0 means a closed cluster, 1 means every edge leaves.
  leverage  in-degree of a node: how many distinct call sites reach this name.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
# Graph JSON lives with the run output, not beside the script.
DATA = Path(os.environ.get("CONDUCTANCE_DATA", REPO / "tmp" / "conductance"))


def conductance(members: set[str], edges: list[tuple[str, str]]) -> dict[str, float | int]:
    internal = cut = 0
    for a, b in edges:
        ina, inb = a in members, b in members
        if ina and inb:
            internal += 1
        elif ina or inb:
            cut += 1
    vol_s = 2 * internal + cut
    total_vol = 2 * len(edges)
    vol_rest = total_vol - vol_s
    denom = min(vol_s, vol_rest)
    phi = cut / denom if denom else 0.0
    return {"internal": internal, "cut": cut, "vol": vol_s, "phi": round(phi, 3)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--graph", type=Path, default=DATA / "callgraph.json")
    ap.add_argument("--prefix", default="", help="prefix for the output filename")
    args = ap.parse_args()

    raw = json.loads(args.graph.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in raw["nodes"]}
    edges = [(e["source"], e["target"]) for e in raw["edges"] if e["source"] in nodes and e["target"] in nodes]

    indeg: dict[str, int] = defaultdict(int)
    for _, b in edges:
        indeg[b] += 1

    by_layer: dict[str, set[str]] = defaultdict(set)
    by_file: dict[str, set[str]] = defaultdict(set)
    for nid, n in nodes.items():
        by_layer[n["layer"]].add(nid)
        by_file[n["file"]].add(nid)

    def leverage_profile(members: set[str]) -> dict[str, float | int]:
        degs = [indeg[m] for m in members]
        n = len(degs) or 1
        return {
            "names": len(degs),
            "orphan": sum(1 for d in degs if d == 0),
            "singleton": sum(1 for d in degs if d == 1),
            "leveraged": sum(1 for d in degs if d >= 3),
            "singleton_rate": round(sum(1 for d in degs if d == 1) / n, 3),
            "mean_leverage": round(sum(degs) / n, 2),
        }

    layers = {
        name: {**conductance(members, edges), **leverage_profile(members)}
        for name, members in sorted(by_layer.items())
    }
    files = {
        name: {**conductance(members, edges), **leverage_profile(members)}
        for name, members in sorted(by_file.items())
    }

    top_leverage = sorted(
        ({"name": n["name"], "file": n["file"], "line": n["line"], "leverage": indeg[nid]} for nid, n in nodes.items()),
        key=lambda r: -r["leverage"],
    )[:15]

    out = {
        "source": raw.get("source", ""),
        "totals": {
            "nodes": len(nodes),
            "edges": len(edges),
            "mean_leverage": round(len(edges) / (len(nodes) or 1), 2),
            "singleton_rate": round(sum(1 for nid in nodes if indeg[nid] == 1) / (len(nodes) or 1), 3),
            "orphan_rate": round(sum(1 for nid in nodes if indeg[nid] == 0) / (len(nodes) or 1), 3),
        },
        "layers": layers,
        "files": files,
        "top_leverage": top_leverage,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    dest = DATA / f"{args.prefix}scores.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"{len(nodes)} nodes, {len(edges)} edges  [{raw.get('source', '')}]\n")
    print(f"{'layer':<14} {'names':>6} {'int':>5} {'cut':>5} {'vol':>5} {'phi':>6} {'sing%':>7} {'mean lev':>9}")
    for name, s in sorted(layers.items(), key=lambda kv: kv[1]["phi"]):
        print(
            f"{name:<14} {s['names']:>6} {s['internal']:>5} {s['cut']:>5} "
            f"{s['vol']:>5} {s['phi']:>6} {s['singleton_rate']:>7} {s['mean_leverage']:>9}"
        )
    print("\ntop leverage:")
    for r in top_leverage[:10]:
        print(f"  {r['leverage']:>3}  {r['name']:<30} {r['file']}:{r['line']}")


if __name__ == "__main__":
    main()
