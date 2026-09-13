#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# ///
"""Assemble every sweep into chart payloads, along the capacity axis.

The framing this answers: if a codebase is a model, the number of NAMES is its
capacity. Inlining reduces capacity, extraction raises it, and behaviour is held
fixed throughout, so the curve of a score against name count is the analogue of a
learning curve against model size.

That is what makes the double-descent question askable. Classical bias-variance
predicts a U: too few names is one giant function, too many is three hundred
wrappers. Double descent would predict the curve turning again past the point
where every name is trivial.

Writes tmp/richdocs/data/cap-*.json for the richdocs page.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
DATA = REPO / "tmp" / "conductance"
OUT = REPO / "tmp" / "richdocs" / "data"

GOOD, MID, BAD, REF = "#047857", "#b45309", "#b91c1c", "#7c3aed"


def graph_stats(n: int) -> dict | None:
    p = DATA / f"exp-{n}.json"
    if not p.exists():
        return None
    raw = json.loads(p.read_text(encoding="utf-8"))
    nodes = {x["id"] for x in raw["nodes"]}
    edges = [(e["source"], e["target"]) for e in raw["edges"]
             if e["source"] in nodes and e["target"] in nodes]
    indeg = Counter(b for _, b in edges)
    return {
        "nodes": len(nodes),
        "edges": len(edges),
        "lev3": sum(1 for i in nodes if indeg[i] >= 3),
        "singleton": round(100 * sum(1 for i in nodes if indeg[i] == 1) / max(len(nodes), 1), 1),
        "orphan": round(100 * sum(1 for i in nodes if indeg[i] == 0) / max(len(nodes), 1), 1),
    }


def load(tag: str) -> list[dict]:
    p = DATA / f"{tag}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def write(name: str, payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    rows: dict[int, dict] = {}
    for tag in ("wave5", "wave3b", "wave4", "wave2", "wave-ts"):
        for r in load(tag):
            g = graph_stats(r["n"])
            if g and "fold_q" in r:
                rows.setdefault(r["n"], {**r, **g})

    # ---- 1. capacity curve: names against both scores ----------------------
    capacity_order = [
        (52, "inline 3+"), (51, "inline 2+"), (50, "inline 1"), (1, "baseline"),
        (56, "extract /12"), (55, "extract /6"), (54, "extract /3"), (53, "extract /1"),
    ]
    pts = [(lbl, rows[n]) for n, lbl in capacity_order if n in rows]
    write("cap-curve.json", {
        "data": [
            {"type": "scatter", "mode": "lines+markers", "name": "modularity Q",
             "x": [r["nodes"] for _, r in pts], "y": [r["fold_q"] for _, r in pts],
             "text": [l for l, _ in pts], "hoverinfo": "text+x+y",
             "marker": {"size": 11}, "yaxis": "y"},
            {"type": "scatter", "mode": "lines+markers", "name": "description length (bits)",
             "x": [r["nodes"] for _, r in pts], "y": [r["fold_bits"] for _, r in pts],
             "text": [l for l, _ in pts], "hoverinfo": "text+x+y",
             "marker": {"size": 11}, "yaxis": "y2"},
        ],
        "layout": {
            "xaxis": {"title": "names in the codebase (model capacity)"},
            "yaxis": {"title": "modularity Q", "side": "left"},
            "yaxis2": {"title": "description length (bits)", "overlaying": "y", "side": "right"},
            "legend": {"orientation": "h", "y": -0.2},
            "annotations": [{"x": pts[3][1]["nodes"] if len(pts) > 3 else 312,
                             "y": 0.59, "text": "the real codebase", "showarrow": True, "ay": -40}],
        },
        "height": 480,
    })

    # ---- 2. the driver chart: every variant, Q against leveraged names ------
    fam = {"baseline": REF, "leiden": GOOD, "duplicate": BAD, "god-class": BAD,
           "inline": MID, "extract": MID, "flatten": BAD, "single": BAD,
           "fold-collapse": BAD, "split": MID, "alpha": MID, "hash": MID, "random": MID}
    py = [r for r in rows.values() if r["n"] < 100]
    write("cap-drivers.json", {
        "data": [{
            "type": "scatter", "mode": "markers+text",
            "x": [r["lev3"] for r in py], "y": [r["fold_q"] for r in py],
            "text": [r["transform"] if r["transform"] in ("baseline", "leiden", "duplicate", "god-class") else "" for r in py],
            "textposition": "top center",
            "hovertext": [f"{r['transform']} k={r['k']}<br>Q {r['fold_q']}<br>"
                          f"{r['nodes']} names, {r['lev3']} leveraged" for r in py],
            "hoverinfo": "text",
            "marker": {"size": 13, "color": [fam.get(r["transform"], MID) for r in py],
                       "line": {"width": 1, "color": "#0f172a"}},
        }],
        "layout": {
            "xaxis": {"title": "names with 3+ callers (the damper)"},
            "yaxis": {"title": "modularity Q (the spring)"},
            "showlegend": False,
            "shapes": [{"type": "line", "x0": 16, "x1": 16, "y0": 0, "y1": 0.7,
                        "line": {"dash": "dot", "width": 1}}],
            "annotations": [{"x": 16, "y": 0.70, "text": "baseline leverage", "showarrow": False}],
        },
        "height": 480,
    })

    # ---- 3. the two archetypes side by side --------------------------------
    def series(ns: list[int], label: str) -> dict:
        got = [rows[n] for n in ns if n in rows]
        return {"type": "bar", "name": label,
                "x": [f"{r['transform']}{(' k=' + str(r['k'])) if r['k'] != '' else ''}" for r in got],
                "y": [r["fold_q"] for r in got]}

    write("cap-archetype.json", {
        "data": [
            series([1, 2, 7, 44, 3], "Python library  src/pytest_xharness_eval"),
            series([100, 105, 108, 101], "TypeScript webapp  report-ui/src"),
        ],
        "layout": {"barmode": "group", "yaxis": {"title": "modularity Q"},
                   "legend": {"orientation": "h", "y": -0.25}},
        "height": 440,
    })

    # ---- 4. granularity: Q against folder count ----------------------------
    hashes = sorted((r for r in py if r["transform"] == "hash"), key=lambda r: r["folder_k"])
    ts_h = sorted((r for r in rows.values() if r["n"] >= 100 and r["transform"] == "hash"),
                  key=lambda r: r["folder_k"])
    write("cap-granularity.json", {
        "data": [
            {"type": "scatter", "mode": "lines+markers", "name": "Python, random folders",
             "x": [r["folder_k"] for r in hashes], "y": [r["fold_q"] for r in hashes]},
            {"type": "scatter", "mode": "lines+markers", "name": "TypeScript, random folders",
             "x": [r["folder_k"] for r in ts_h], "y": [r["fold_q"] for r in ts_h]},
            {"type": "scatter", "mode": "markers", "name": "the real architectures",
             "x": [rows[1]["folder_k"], rows[100]["folder_k"]] if 100 in rows else [rows[1]["folder_k"]],
             "y": [rows[1]["fold_q"], rows[100]["fold_q"]] if 100 in rows else [rows[1]["fold_q"]],
             "marker": {"size": 16, "symbol": "star", "color": REF}},
        ],
        "layout": {"xaxis": {"title": "number of folders"}, "yaxis": {"title": "modularity Q"},
                   "legend": {"orientation": "h", "y": -0.2}},
        "height": 440,
    })

    print(f"{len(rows)} variants assembled")
    print(f"{'#':>4} {'transform':<14} {'k':>3} {'nodes':>6} {'edges':>6} {'Q':>7} {'bits':>6} {'lev3':>5} {'sing%':>6}")
    for n in sorted(rows):
        r = rows[n]
        print(f"{n:>4} {r['transform']:<14} {str(r['k']):>3} {r['nodes']:>6} {r['edges']:>6} "
              f"{r['fold_q']:>7} {r['fold_bits']:>6} {r['lev3']:>5} {r['singleton']:>5}%")
    (DATA / "all-variants.json").write_text(json.dumps(list(rows.values()), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
