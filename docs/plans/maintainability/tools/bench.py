#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = ["sqlite-muninn>=0.6.0"]
# ///
"""Benchmark three conductance implementations at increasing graph size.

Three variants, so the result separates language from algorithm:

  py-naive    what score.py does today: for each cluster, walk every edge.
              O(k*E). The honest baseline, because it is the code in use.
  py-1pass    same language, same algorithm as muninn: one pass over edges,
              bucketing by the endpoints' cluster labels. O(E).
  muninn      graph_conductance in C over CSR adjacency. O(E).

Two timings per variant, because they answer different questions:

  compute     the SQLite table is already populated. This is the real tool's
              situation: the call graph lives in lsp_index.db already.
  end-to-end  including CREATE TABLE + executemany. This is what a script
              holding the graph in Python memory actually pays.

Usage: bench.py [--reps N] [--max-edges N]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import statistics
import time
from collections import defaultdict
from pathlib import Path

import sqlite_muninn

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
# Graph JSON lives with the run output, not beside the script.
DATA = Path(os.environ.get("CONDUCTANCE_DATA", REPO / "tmp" / "conductance"))


# ---- the three implementations -------------------------------------------


def py_naive(edges: list[tuple[str, str]], membership: dict[str, str]) -> dict[str, float]:
    """O(k*E): the loop score.py runs today."""
    clusters: dict[str, set[str]] = defaultdict(set)
    for node, group in membership.items():
        clusters[group].add(node)
    total_vol = 2 * len(edges)
    out = {}
    for group, members in clusters.items():
        internal = cut = 0
        for a, b in edges:
            ina, inb = a in members, b in members
            if ina and inb:
                internal += 1
            elif ina or inb:
                cut += 1
        vol = 2 * internal + cut
        denom = min(vol, total_vol - vol)
        out[group] = cut / denom if denom else 0.0
    return out


def py_1pass(edges: list[tuple[str, str]], membership: dict[str, str]) -> dict[str, float]:
    """O(E): one pass, bucketing each edge by its endpoints' labels."""
    internal: dict[str, int] = defaultdict(int)
    cut: dict[str, int] = defaultdict(int)
    for a, b in edges:
        ga, gb = membership.get(a), membership.get(b)
        if ga is None or gb is None:
            continue
        if ga == gb:
            internal[ga] += 1
        else:
            cut[ga] += 1
            cut[gb] += 1
    total_vol = 2 * len(edges)
    groups = set(internal) | set(cut)
    out = {}
    for g in groups:
        vol = 2 * internal[g] + cut[g]
        denom = min(vol, total_vol - vol)
        out[g] = cut[g] / denom if denom else 0.0
    return out


def muninn_query(db: sqlite3.Connection) -> dict[str, float]:
    rows = db.execute(
        """
        SELECT group_id, phi FROM graph_conductance
         WHERE edge_table = 'calls' AND src_col = 'src' AND dst_col = 'dst'
           AND direction = 'both'
           AND membership_table = 'declared'
           AND group_col = 'layer' AND member_col = 'node'
        """
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def muninn_load(edges: list[tuple[str, str]], membership: dict[str, str]) -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.enable_load_extension(True)
    sqlite_muninn.load(db)
    db.execute("CREATE TABLE calls(src TEXT, dst TEXT)")
    db.executemany("INSERT INTO calls VALUES(?,?)", edges)
    db.execute("CREATE TABLE declared(node TEXT, layer TEXT)")
    db.executemany("INSERT INTO declared VALUES(?,?)", membership.items())
    return db


# ---- harness --------------------------------------------------------------


def timed(fn, reps: int) -> float:
    """Median of `reps` runs, in milliseconds. Median resists a scheduler blip."""
    fn()  # warm up: first call pays import and allocator costs
    samples = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return statistics.median(samples)


def synthetic(n_nodes: int, n_edges: int, k: int, seed: int = 7) -> tuple[list, dict]:
    """A planted-partition graph: mostly within-cluster edges, some across.

    Shaped like real code (low conductance clusters) so the benchmark is not
    measuring a degenerate case.
    """
    rng = random.Random(seed)
    nodes = [f"n{i}" for i in range(n_nodes)]
    membership = {node: f"c{i % k}" for i, node in enumerate(nodes)}
    by_group: dict[str, list[str]] = defaultdict(list)
    for node, g in membership.items():
        by_group[g].append(node)
    groups = list(by_group)
    edges = []
    for _ in range(n_edges):
        if rng.random() < 0.85:  # within cluster
            g = rng.choice(groups)
            pool = by_group[g]
            edges.append((rng.choice(pool), rng.choice(pool)))
        else:
            edges.append((rng.choice(nodes), rng.choice(nodes)))
    return edges, membership


def run_case(label: str, edges: list, membership: dict, reps: int) -> dict:
    k = len(set(membership.values()))
    db = muninn_load(edges, membership)

    t_naive = timed(lambda: py_naive(edges, membership), reps)
    t_1pass = timed(lambda: py_1pass(edges, membership), reps)
    t_muninn = timed(lambda: muninn_query(db), reps)
    t_e2e = timed(lambda: muninn_query(muninn_load(edges, membership)), max(reps // 3, 3))

    # agreement check, so a fast wrong answer cannot win
    a, b, c = py_naive(edges, membership), py_1pass(edges, membership), muninn_query(db)
    shared = set(a) & set(b) & set(c)
    drift = max((max(abs(a[g] - b[g]), abs(a[g] - c[g])) for g in shared), default=0.0)

    print(
        f"{label:<26} {len(edges):>8} {k:>5} "
        f"{t_naive:>11.2f} {t_1pass:>10.2f} {t_muninn:>9.2f} {t_e2e:>10.2f} "
        f"{t_naive / t_muninn:>8.1f}x {drift:>9.2e}"
    )
    return {"label": label, "edges": len(edges), "k": k, "naive": t_naive,
            "onepass": t_1pass, "muninn": t_muninn, "e2e": t_e2e, "drift": drift}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reps", type=int, default=15)
    ap.add_argument("--max-edges", type=int, default=200_000)
    args = ap.parse_args()

    print(f"{'case':<26} {'edges':>8} {'k':>5} {'py-naive ms':>11} {'py-1pass':>10} "
          f"{'muninn':>9} {'m+load':>10} {'naive/mun':>9} {'max drift':>9}")
    print("-" * 106)

    results = []
    for label, gf in (("real: Python src/", "callgraph.json"), ("real: TypeScript ui/", "callgraph-ts.json")):
        g = json.loads((DATA / gf).read_text(encoding="utf-8"))
        nodes = {n["id"]: n for n in g["nodes"]}
        edges = [(e["source"], e["target"]) for e in g["edges"]]
        results.append(run_case(label, edges, {i: n["layer"] for i, n in nodes.items()}, args.reps))

    for n_edges in (1_000, 10_000, 50_000, args.max_edges):
        if n_edges > args.max_edges:
            continue
        n_nodes = max(n_edges // 3, 50)
        for k in (8, 64):
            edges, membership = synthetic(n_nodes, n_edges, k)
            reps = args.reps if n_edges <= 10_000 else max(args.reps // 5, 3)
            results.append(run_case(f"synthetic k={k}", edges, membership, reps))

    (DATA / "bench.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("\nwrote tmp/conductance/bench.json")


if __name__ == "__main__":
    main()
