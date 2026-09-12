# reviewable-ui

The tree-sitter call graph with the maintainability metrics layered over it.

Companion to [docs/plans/maintainability/](../docs/plans/maintainability/), which
argues what the metrics mean. This renders them.

## Run it

```bash
make reviewable-data     # parse the repo into reviewable-ui/public/graph.json
make reviewable-dev      # vite dev server
```

Point it at a different graph without regenerating:

```bash
RU_GRAPH=path/to/graph.json make reviewable-dev
```

## What it shows

- **Boundary** picks the partition: language, folder, file or class. The selector
  carries each level's modularity and inside-share, so the cost of the choice is
  visible while making it.
- **Colour by** picks the per-node metric: leverage, call sites, lines, nesting
  depth, fan out.
- **Cluster table** lists conductance per cluster at the chosen boundary, with
  `not measurable` rather than a number below the volume floor.

The header carries the extraction's validity numbers **before** any score, because
a graph with a high orphan rate was extracted wrong and every metric computed from
it inherits that.

## What it is not

The bands are **uncalibrated**. Nothing in this work has derived a threshold that
separates good from bad, and the experiments in
[experiments.md](../docs/plans/maintainability/experiments.md) show every candidate
objective has a degenerate optimum. Colour shows a distribution; it does not grade
one.

## Layout

| Path                             | What                                                                     |
| -------------------------------- | ------------------------------------------------------------------------ |
| `src/lib/types.ts`               | the contract with `tools/graphdata.py`; change one and change the other  |
| `src/lib/graph.ts`               | loading, filtering, and the cytoscape element build                      |
| `src/lib/metrics.ts`             | the metrics and their bands, and the only place a band colour is defined |
| `src/components/GraphCanvas.tsx` | owns the cytoscape instance                                              |
| `src/components/Panels.tsx`      | controls, legend, detail, cluster table                                  |

Unlike `report-ui`, this is **not** a single inlined file: the graph JSON is
hundreds of kilobytes and grows with the codebase, so it is fetched at runtime.
