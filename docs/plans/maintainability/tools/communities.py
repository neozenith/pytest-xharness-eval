#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = ["sqlite-muninn>=0.4.0"]
# ///
"""Compare the declared architecture to the one the call graph actually has.

The folders under src/pytest_xharness_eval/ are a *declared* partition: a human
said these names belong together. graph_leiden computes the partition the call
graph itself implies. Conductance scores both, so the two are comparable.

If the declared partition has materially higher conductance than the discovered
one, the folders are cutting through cohesive clusters -- which is a finding a
reviewer can act on, and one no per-unit metric can produce.

Writes tmp/conductance/communities.json and prints the comparison.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

import sqlite_muninn

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
# Graph JSON lives with the run output, not beside the script.
DATA = Path(os.environ.get("CONDUCTANCE_DATA", REPO / "tmp" / "conductance"))


def conductance(members: set[str], edges: list[tuple[str, str]]) -> float:
    internal = cut = 0
    for a, b in edges:
        ina, inb = a in members, b in members
        if ina and inb:
            internal += 1
        elif ina or inb:
            cut += 1
    vol_s = 2 * internal + cut
    vol_rest = 2 * len(edges) - vol_s
    denom = min(vol_s, vol_rest)
    return cut / denom if denom else 0.0


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

    leiden = {
        row[0]: row[1] for row in db.execute("SELECT node, community_id FROM graph_leiden('calls','src','dst')")
    }
    modularity = db.execute("SELECT modularity FROM graph_leiden('calls','src','dst') LIMIT 1").fetchone()[0]
    pagerank = {row[0]: row[1] for row in db.execute("SELECT node, rank FROM graph_pagerank('calls','src','dst')")}

    # Declared partition: the folder each name lives in.
    declared: dict[str, set[str]] = defaultdict(set)
    for nid, n in nodes.items():
        declared[n["layer"]].add(nid)

    # Discovered partition: the community Leiden put each name in.
    discovered: dict[int, set[str]] = defaultdict(set)
    for nid, cid in leiden.items():
        discovered[cid].add(nid)

    # Only nodes that appear in an edge are partitioned by Leiden; isolated
    # names have no community. Compare on the connected subgraph, and say so.
    connected = set(leiden)

    dec_scores = {
        name: conductance(members & connected, edges) for name, members in declared.items() if members & connected
    }
    dis_scores = {cid: conductance(members, edges) for cid, members in discovered.items() if len(members) >= 3}

    dec_mean = sum(dec_scores.values()) / len(dec_scores)
    dis_mean = sum(dis_scores.values()) / len(dis_scores)

    # How badly does each Leiden community get split across declared folders?
    splits = []
    for cid, members in sorted(discovered.items(), key=lambda kv: -len(kv[1])):
        if len(members) < 4:
            continue
        layers = Counter(nodes[m]["layer"] for m in members)
        splits.append(
            {
                "community": cid,
                "size": len(members),
                "phi": round(conductance(members, edges), 3),
                "layers": dict(layers),
                "spans": len(layers),
                "sample": sorted(nodes[m]["name"] for m in members)[:6],
                "members": sorted(members),
            }
        )

    # ---- the residual, as a fraction of all call edges ----------------------
    # A partition is a model whose single prediction is "calls stay inside a
    # cluster". Every edge that crosses is a prediction the model got wrong,
    # so the crossing fraction is L(D|H) normalised: the residual rate.
    layer_of = {nid: n["layer"] for nid, n in nodes.items()}
    scoped = [(a, b) for a, b in edges if a in connected and b in connected]
    declared_cross = sum(1 for a, b in scoped if layer_of[a] != layer_of[b])
    discovered_cross = sum(1 for a, b in scoped if leiden[a] != leiden[b])
    residual = {
        "edges_scored": len(scoped),
        "declared_cross": declared_cross,
        "discovered_cross": discovered_cross,
        "declared_residual": round(declared_cross / len(scoped), 3),
        "irreducible_residual": round(discovered_cross / len(scoped), 3),
        "avoidable_residual": round((declared_cross - discovered_cross) / len(scoped), 3),
        "avoidable_share": round((declared_cross - discovered_cross) / declared_cross, 3),
    }

    top_rank = sorted(
        ({"name": nodes[n]["name"], "file": nodes[n]["file"], "rank": round(r, 5)} for n, r in pagerank.items() if n in nodes),
        key=lambda r: -r["rank"],
    )[:12]

    out = {
        "connected_nodes": len(connected),
        "total_nodes": len(nodes),
        "edges": len(edges),
        "modularity": round(modularity, 4),
        "communities": len(discovered),
        "declared_mean_phi": round(dec_mean, 3),
        "discovered_mean_phi": round(dis_mean, 3),
        "residual": residual,
        "declared": {k: round(v, 3) for k, v in sorted(dec_scores.items(), key=lambda kv: kv[1])},
        "splits": splits[:12],
        "top_pagerank": top_rank,
    }
    (DATA / f"{args.prefix}communities.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"{len(connected)}/{len(nodes)} names appear in a call edge; {len(edges)} edges")
    print(f"Leiden: {len(discovered)} communities, modularity {modularity:.4f}\n")
    print(f"declared (folders)   mean phi = {dec_mean:.3f}  over {len(dec_scores)} clusters")
    print(f"discovered (Leiden)  mean phi = {dis_mean:.3f}  over {len(dis_scores)} clusters >=3\n")
    print("residual: the share of call edges the partition fails to predict")
    print(f"  declared (folders)  {residual['declared_residual']:.1%}  "
          f"({declared_cross}/{len(scoped)} edges cross)")
    print(f"  irreducible (Leiden) {residual['irreducible_residual']:.1%}  "
          f"({discovered_cross}/{len(scoped)} edges cross)")
    print(f"  avoidable            {residual['avoidable_residual']:.1%}  "
          f"= {residual['avoidable_share']:.1%} of the declared residual\n")
    print("communities that span more than one declared layer:")
    for s in splits[:10]:
        if s["spans"] > 1:
            print(f"  c{s['community']:<3} n={s['size']:<3} phi={s['phi']:<6} {s['layers']}")
            print(f"       {', '.join(s['sample'])}")
    print("\ntop pagerank:")
    for r in top_rank[:8]:
        print(f"  {r['rank']:<9} {r['name']:<28} {Path(r['file']).name}")


if __name__ == "__main__":
    main()
