#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = ["sqlite-muninn>=0.6.0"]
# ///
"""Does counting call sites instead of distinct callers change the verdict?

callHierarchy/incomingCalls returns `fromRanges`: every call site inside the
caller, not just one. Collapsing to a set of (caller, callee) pairs measures
distinct calling *functions*. Weighting each edge by its site count measures
call *sites*, which is closer to what leverage claims to be: how many places
does this one name save you from reading.

muninn 0.6.0 sums edge weight rather than counting edges, so both readings are
one query apart.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import sqlite_muninn

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
# Graph JSON lives with the run output, not beside the script.
DATA = Path(os.environ.get("CONDUCTANCE_DATA", REPO / "tmp" / "conductance"))

QUERY = """
SELECT group_id, size, internal, cut, vol, phi
  FROM graph_conductance
 WHERE edge_table = 'calls' AND src_col = 'src' AND dst_col = 'dst'
   {weight}
   AND direction = 'both'
   AND membership_table = 'declared'
   AND group_col = 'layer' AND member_col = 'node'
"""


def main() -> None:
    graph = json.loads((DATA / "callgraph-sites.json").read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in graph["nodes"]}

    db = sqlite3.connect(":memory:")
    db.enable_load_extension(True)
    sqlite_muninn.load(db)
    db.execute("CREATE TABLE calls(src TEXT, dst TEXT, sites REAL)")
    db.executemany(
        "INSERT INTO calls VALUES(?,?,?)",
        [(e["source"], e["target"], float(e["sites"])) for e in graph["edges"]],
    )
    db.execute("CREATE TABLE declared(node TEXT, layer TEXT)")
    db.executemany("INSERT INTO declared VALUES(?,?)", ((k, v["layer"]) for k, v in nodes.items()))

    plain = {r[0]: r for r in db.execute(QUERY.format(weight=""))}
    weighted = {r[0]: r for r in db.execute(QUERY.format(weight="AND weight_col = 'sites'"))}

    total_sites = sum(e["sites"] for e in graph["edges"])
    print(f"{len(graph['edges'])} distinct edges, {int(total_sites)} call sites "
          f"(+{100 * total_sites / len(graph['edges']) - 100:.0f}%)\n")
    print(f"{'layer':<12} {'phi (edges)':>12} {'phi (sites)':>12} {'shift':>8}   verdict")
    print("-" * 62)
    for layer in sorted(plain, key=lambda k: plain[k][5]):
        a, b = plain[layer][5], weighted[layer][5]
        band_a = "deep" if a < 0.25 else "mid" if a < 0.5 else "shallow"
        band_b = "deep" if b < 0.25 else "mid" if b < 0.5 else "shallow"
        flag = "" if band_a == band_b else f"   BAND MOVED {band_a} -> {band_b}"
        print(f"{layer:<12} {a:>12.3f} {b:>12.3f} {b - a:>+8.3f}   {band_b}{flag}")


if __name__ == "__main__":
    main()
