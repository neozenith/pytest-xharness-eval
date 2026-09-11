#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = ["sqlite-muninn>=0.6.0"]
# ///
"""Cross-check sqlite-muninn 0.6.0's graph_conductance against our own.

score.py computes conductance in Python by walking the edge list. muninn 0.6.0
computes it in C over its CSR adjacency. The two were written independently from
the same definition, so agreement is real evidence for both and any disagreement
is a bug in one of them.

Runs over both call graphs already extracted in this directory.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections import defaultdict
from pathlib import Path

import sqlite_muninn

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
# Graph JSON lives with the run output, not beside the script.
DATA = Path(os.environ.get("CONDUCTANCE_DATA", REPO / "tmp" / "conductance"))

CASES = [
    ("Python  src/pytest_xharness_eval", "callgraph.json", "scores.json"),
    ("TypeScript  report-ui/src", "callgraph-ts.json", "ts-scores.json"),
]


def muninn_conductance(edges: list[tuple[str, str]], membership: dict[str, str]) -> dict[str, dict]:
    db = sqlite3.connect(":memory:")
    db.enable_load_extension(True)
    sqlite_muninn.load(db)
    db.execute("CREATE TABLE calls(src TEXT, dst TEXT)")
    db.executemany("INSERT INTO calls VALUES(?,?)", edges)
    db.execute("CREATE TABLE declared(node TEXT, layer TEXT)")
    db.executemany("INSERT INTO declared VALUES(?,?)", membership.items())

    rows = db.execute(
        """
        SELECT group_id, size, internal, cut, vol, phi
          FROM graph_conductance
         WHERE edge_table = 'calls' AND src_col = 'src' AND dst_col = 'dst'
           AND direction = 'both'
           AND membership_table = 'declared'
           AND group_col = 'layer' AND member_col = 'node'
        """
    ).fetchall()
    return {r[0]: {"size": r[1], "internal": r[2], "cut": r[3], "vol": r[4], "phi": r[5]} for r in rows}


def main() -> None:
    worst = 0.0
    for label, graph_file, scores_file in CASES:
        graph = json.loads((DATA / graph_file).read_text(encoding="utf-8"))
        ours = json.loads((DATA / scores_file).read_text(encoding="utf-8"))["layers"]

        nodes = {n["id"]: n for n in graph["nodes"]}
        edges = [(e["source"], e["target"]) for e in graph["edges"]]
        membership = {nid: n["layer"] for nid, n in nodes.items()}

        theirs = muninn_conductance(edges, membership)

        print(f"\n{label}")
        print(f"{'layer':<14} {'ours phi':>9} {'muninn phi':>11} {'delta':>8}   {'cut':>5} {'vol':>5}")
        print("-" * 62)
        for layer in sorted(ours, key=lambda k: ours[k]["phi"]):
            o = ours[layer]["phi"]
            t = theirs.get(layer)
            if t is None:
                print(f"{layer:<14} {o:>9} {'absent':>11}")
                continue
            delta = abs(o - t["phi"])
            worst = max(worst, delta)
            flag = "" if delta < 5e-3 else "   <-- MISMATCH"
            print(f"{layer:<14} {o:>9} {t['phi']:>11.3f} {delta:>8.4f}   {int(t['cut']):>5} {int(t['vol']):>5}{flag}")

    print(f"\nlargest disagreement across both graphs: {worst:.5f}")


if __name__ == "__main__":
    main()
