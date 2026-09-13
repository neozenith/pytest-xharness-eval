#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["tree-sitter>=0.25", "tree-sitter-python>=0.25", "tree-sitter-typescript>=0.23"]
# ///
"""Run a wave of rearrangement experiments and tabulate what each one scores.

For each variant: materialise it, extract a call graph with tree-sitter, and
score conductance at every boundary level. The table is the experiment.

Reported per variant, all of them behaviour-preserving rearrangements:

  edges        should be INVARIANT across filing transforms. If it moves, the
               transform changed the program and the row is not comparable.
  fold-in %    share of call edges that stay inside a folder
  file-in %    ... inside a file
  cls-in %     ... inside a class
  folder phi   median conductance of a folder, above the volume floor
  bits/bnd     residual bits saved per boundary introduced, the MDL score

Usage: sweep.py <wave.json>     where wave.json is [{"n":1,"transform":"flatten",...}]
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TOOLS = Path(__file__).resolve().parent
OUT = REPO / "tmp" / "conductance"


def run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def conductance(members: set[str], edges: list[tuple[str, str]]) -> float | None:
    internal = cut = 0
    for a, b in edges:
        ina, inb = a in members, b in members
        if ina and inb:
            internal += 1
        elif ina or inb:
            cut += 1
    vol = 2 * internal + cut
    denom = min(vol, 2 * len(edges) - vol)
    return round(cut / denom, 3) if denom and vol >= 6 else None


def two_part_total(assign: dict[str, str], edges: list[tuple[str, str]], n: int) -> float:
    """Total description length in bits: L(H) + L(D given H). Lower is better.

    Wave 1 showed the earlier scheme was degenerate at one cluster: an internal
    edge inside a cluster of size n cost log2(n), exactly what a crossing cost,
    so collapsing everything into one folder paid nothing and scored best.

    A crossing edge must cost strictly more, because naming a target outside
    your cluster means naming the cluster first:

        L(H)      = n * log2(k)                  which cluster each name is in
        internal  = log2(|C_target|)             index within my own cluster
        crossing  = log2(k) + log2(|C_target|)   name the cluster, then index

    At k = 1 nothing can cross and the total is E*log2(n), the no-architecture
    baseline. At k = n every edge crosses and L(H) is maximal. A real optimum
    sits between, which is what makes this usable as an objective.
    """
    sizes = Counter(assign.values())
    k = len(sizes)
    l_h = n * math.log2(k) if k > 1 else 0.0
    l_d = 0.0
    for a, b in edges:
        within = math.log2(max(sizes[assign[b]], 2))
        l_d += within if assign[a] == assign[b] else math.log2(k) + within
    return round(l_h + l_d)


def modularity(assign: dict[str, str], edges: list[tuple[str, str]]) -> float:
    """Newman modularity: inside-edge share, minus what chance would give.

    Three earlier objectives each had a degenerate optimum, which is why this
    one is here rather than a fourth hand-rolled attempt:

      inside %        maximised by one cluster: nothing can cross.
      bits/boundary   maximised by two clusters: the divisor is k - 1.
      MDL total       maximised by one cluster, because L(H) = n*log2(k) scales
                      with NAMES while the saving scales with EDGES, and this
                      graph has fewer edges than names.

    Modularity subtracts the expected inside-share of a random graph with the
    same degrees, so it is 0 at one cluster by construction and negative when
    clusters are so small that everything crosses. The optimum is interior,
    which is the property an objective needs to be searched at all.
    """
    m = len(edges)
    if m == 0:
        return 0.0
    deg: Counter[str] = Counter()
    for a, b in edges:
        deg[a] += 1
        deg[b] += 1
    e_in: Counter[str] = Counter()
    d_tot: Counter[str] = Counter()
    for node, c in assign.items():
        d_tot[c] += deg[node]
    for a, b in edges:
        if assign[a] == assign[b]:
            e_in[assign[a]] += 1
    q = 0.0
    for c in d_tot:
        q += (e_in[c] / m) - (d_tot[c] / (2 * m)) ** 2
    return round(q, 4)


def score(graph_path: Path) -> dict:
    raw = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = {x["id"]: x for x in raw["nodes"]}
    edges = [(e["source"], e["target"]) for e in raw["edges"]
             if e["source"] in nodes and e["target"] in nodes]
    total = len(edges) or 1

    def key_folder(x: dict) -> str:
        return x.get("folder") or str(Path(x["file"]).parent)

    keys = {"folder": key_folder, "file": lambda x: x["file"],
            "cls": lambda x: f"{x['file']}::{x.get('cls') or '<module>'}"}

    out: dict = {"nodes": len(nodes), "edges": len(edges),
                 "sites": sum(e.get("sites", 1) for e in raw["edges"])}

    for label, key in keys.items():
        groups: dict[str, set[str]] = defaultdict(set)
        for nid, x in nodes.items():
            groups[key(x)].add(nid)
        inside = sum(1 for a, b in edges if key(nodes[a]) == key(nodes[b]))
        phis = sorted(p for p in (conductance(m, edges) for m in groups.values()) if p is not None)
        out[f"{label}_in"] = round(100 * inside / total)
        out[f"{label}_phi"] = phis[len(phis) // 2] if phis else None
        out[f"{label}_k"] = len(groups)

    out["fold_q"] = modularity({i: key_folder(x) for i, x in nodes.items()}, edges)
    out["file_q"] = modularity({i: x["file"] for i, x in nodes.items()}, edges)
    out["fold_bits"] = two_part_total({i: key_folder(x) for i, x in nodes.items()}, edges, len(nodes))
    out["file_bits"] = two_part_total({i: x["file"] for i, x in nodes.items()}, edges, len(nodes))

    indeg: Counter[str] = Counter(b for _, b in edges)
    out["singleton"] = round(100 * sum(1 for i in nodes if indeg[i] == 1) / max(len(nodes), 1))
    out["orphan"] = round(100 * sum(1 for i in nodes if indeg[i] == 0) / max(len(nodes), 1))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("wave", type=Path)
    ap.add_argument("--tag", default="wave")
    ap.add_argument("--src", default="")
    ap.add_argument("--ext", default="")
    ap.add_argument("--skip", default="")
    args = ap.parse_args()

    spec = json.loads(args.wave.read_text(encoding="utf-8"))
    args_src = {"src": args.src, "ext": args.ext, "skip": args.skip}
    rows = []

    for item in spec:
        cmd = ["uv", "run", str(TOOLS / "experiment.py"), item["transform"], "--n", str(item["n"])]
        for opt in ("k", "seed", "graph"):
            if opt in item and item[opt] != "":
                cmd += [f"--{opt}", str(item[opt])]
        for opt in ("src", "ext", "skip"):
            if args_src.get(opt):
                cmd += [f"--{opt}", args_src[opt]]
        label = run(cmd).strip().split(": ", 1)
        note = label[1] if len(label) > 1 else ""

        src = f"tmp/exp-{item['n']}-pytest-xharness-evals"
        graph = OUT / f"exp-{item['n']}.json"
        tcmd = ["uv", "run", str(TOOLS / "treesitter.py"), src, "--out", str(graph.relative_to(REPO))]
        if args_src.get("skip"):
            tcmd += ["--exclude", args_src["skip"]]
        run(tcmd)

        row = {"n": item["n"], "transform": item["transform"],
               "k": item.get("k", ""), "note": note, **score(graph)}
        rows.append(row)
        print(f"  scored exp-{item['n']} {item['transform']}")

    dest = OUT / f"{args.tag}.json"
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    base = next((r["edges"] for r in rows if r["transform"] == "baseline"), None)
    hdr = (f"{'#':>3} {'transform':<14} {'k':>3} {'edges':>6} {'fold Q':>8} {'file Q':>8} "
           f"{'fold-in':>8} {'fold phi':>9} {'fold k':>7} {'MDL bits':>9}")
    print(f"\n{hdr}\n" + "-" * len(hdr))
    for r in sorted(rows, key=lambda x: -x["fold_q"]):
        mark = "" if base is None or r["edges"] == base else "  *"
        print(f"{r['n']:>3} {r['transform']:<14} {str(r['k']):>3} {r['edges']:>6} "
              f"{r['fold_q']:>8} {r['file_q']:>8} {r['folder_in']:>7}% "
              f"{str(r['folder_phi']):>9} {r['folder_k']:>7} {r['fold_bits']:>9}{mark}")
    print("\n  * edge count differs from baseline: the transform changed name "
          "resolution, so the row is not strictly comparable.")
    print(f"\nwrote {dest.relative_to(REPO)}")


if __name__ == "__main__":
    main()
