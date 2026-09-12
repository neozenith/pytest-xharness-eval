/**
 * reviewable: the tree-sitter call graph with the maintainability metrics over it.
 *
 * The header carries the extraction's validity numbers before any score, because a
 * graph with a high orphan rate is a graph that was extracted wrong, and every
 * metric computed from it inherits that. See docs/plans/maintainability/README.md,
 * "What we still cannot extract".
 */
import { useEffect, useMemo, useState } from "react";
import { GraphCanvas } from "@/components/GraphCanvas";
import { ClusterTable, Controls, Detail, Legend } from "@/components/Panels";
import {
  DEFAULT_FILTERS,
  loadGraph,
  toElements,
  type Filters,
} from "@/lib/graph";
import { metricById } from "@/lib/metrics";
import type { Graph, Level } from "@/lib/types";

export const App = () => {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState<Level>("folder");
  const [metricId, setMetricId] = useState("leverage");
  const [layout, setLayout] = useState("dagre");
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    loadGraph()
      .then(setGraph)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : String(e)),
      );
  }, []);

  const metric = metricById(metricId);
  const slice = useMemo(
    () => (graph ? toElements(graph, level, metric, filters) : null),
    [graph, level, metric, filters],
  );
  const node = useMemo(
    () =>
      graph && selected
        ? (graph.nodes.find((n) => n.id === selected) ?? null)
        : null,
    [graph, selected],
  );

  if (error) {
    return (
      <main className="fatal" data-testid="fatal">
        <h1>No graph</h1>
        <p className="mono">{error}</p>
        <p>
          Generate one with <code>make reviewable-data</code>, or point the dev
          server at an existing file with{" "}
          <code>RU_GRAPH=path/to/graph.json</code>.
        </p>
      </main>
    );
  }
  if (!graph || !slice) return <main className="loading">Loading graph…</main>;

  const t = graph.totals;
  return (
    <main className="app">
      <header data-testid="header">
        <h1>reviewable</h1>
        <div className="totals">
          <span>
            <b>{t.nodes}</b> definitions
          </span>
          <span>
            <b>{t.edges}</b> edges
          </span>
          <span>
            <b>{t.callSites}</b> call sites
          </span>
          <span className={t.orphanPct > 40 ? "warn" : ""}>
            <b>{t.orphanPct}%</b> orphans
          </span>
          <span className={t.resolvedPct < 50 ? "warn" : ""}>
            <b>{t.resolvedPct}%</b> resolved
          </span>
          <span>
            <b>{t.maxDepth}</b> max depth
          </span>
        </div>
        <p className="note">
          {graph.sources
            .map((s) => `${s.root} (${s.lang}, ${s.files} files)`)
            .join("  ·  ")}
        </p>
        {t.orphanPct > 40 && (
          <p className="warn banner">
            {t.orphanPct}% of definitions have no caller in this graph. Read
            that as an extraction problem before reading any score.
          </p>
        )}
      </header>

      <div className="body">
        <aside className="left">
          <Controls
            graph={graph}
            level={level}
            metric={metric}
            layout={layout}
            filters={filters}
            onLevel={setLevel}
            onMetric={setMetricId}
            onLayout={setLayout}
            onFilters={setFilters}
          />
          <Legend metric={metric} />
          <p className="note" data-testid="shown">
            showing {slice.shown} of {slice.total}
            {slice.hiddenByLimit > 0
              ? ` · ${slice.hiddenByLimit} hidden by the node cap`
              : ""}
          </p>
        </aside>

        <section className="middle">
          <GraphCanvas
            elements={slice.elements}
            layout={layout}
            onSelect={setSelected}
          />
        </section>

        <aside className="right">
          <Detail node={node} graph={graph} />
          <h4>Clusters at this boundary</h4>
          <ClusterTable
            clusters={slice.clusters}
            level={level}
            roots={graph.sources.map((s) => s.root)}
          />
        </aside>
      </div>
    </main>
  );
};
