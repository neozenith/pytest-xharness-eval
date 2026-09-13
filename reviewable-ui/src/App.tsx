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
import {
  BandCaveat,
  ClusterTable,
  Controls,
  Detail,
  Lede,
  Legend,
  type OffSlice,
} from "@/components/Panels";
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
        <p className="mono" role="alert">
          {error}
        </p>
        <p>
          Generate one with <code>make reviewable-data</code>, or point the dev
          server at an existing file with{" "}
          <code>RU_GRAPH=path/to/graph.json</code>.
        </p>
      </main>
    );
  }
  if (!graph || !slice) {
    return (
      <main className="loading" role="status" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <h1>Loading graph…</h1>
        <p className="note">
          Reading <code>graph.json</code>. Large graphs can take a few seconds
          to parse.
        </p>
      </main>
    );
  }

  /*
   * A zero-node graph is not a small graph, it is a failed extraction — and every
   * total the header would print for one is vacuously flattering. "0% orphans" and
   * "100% resolved" are what you get from `0/0` handled charitably, and they are the
   * two numbers this page exists to make a reader distrust. Rendering the normal
   * chrome over them would be the page telling its most confident lie on its worst
   * input, so this state gets its own screen instead.
   */
  if (graph.nodes.length === 0) {
    return (
      <main className="fatal" data-testid="empty-graph">
        <h1>Empty graph</h1>
        <p role="alert">
          <code>graph.json</code> parsed, but it contains no definitions. Nothing
          below it can be computed, and the totals it reports (
          <span className="mono">{graph.totals.orphanPct}% orphans</span>,{" "}
          <span className="mono">{graph.totals.resolvedPct}% resolved</span>) are
          arithmetic over an empty set, not findings.
        </p>
        <p>
          The extractor ran against{" "}
          {graph.sources.length === 0
            ? "no sources at all"
            : graph.sources
                .map((s) => `${s.root} (${s.lang}, ${s.files} files)`)
                .join("  ·  ")}
          . Check that the roots exist and that the tree-sitter grammar for each
          language is installed, then re-run <code>make reviewable-data</code>.
        </p>
      </main>
    );
  }

  const t = graph.totals;
  const capped = slice.hiddenByLimit > 0;
  // Selection outlives the slice: the detail panel's caller/callee buttons and the
  // lede's own link both jump to definitions a filter or the cap may exclude.
  const offSlice: OffSlice =
    selected && !slice.visibleIds.has(selected)
      ? slice.keptIds.has(selected)
        ? "capped"
        : "filtered"
      : null;
  return (
    <div className="shell">
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
        <Lede
          graph={graph}
          level={level}
          clusters={slice.clusters}
          shown={slice.shown}
          total={slice.total}
          visibleIds={slice.visibleIds}
          keptIds={slice.keptIds}
          onSelect={setSelected}
        />
        {t.orphanPct > 40 && (
          <p className="warn banner" role="status">
            {t.orphanPct}% of definitions have no caller in this graph. Read
            that as an extraction problem before reading any score.
          </p>
        )}
      </header>

      <main className="app">
        <div className="body">
          <aside className="left" aria-labelledby="controls-heading">
            <h2 id="controls-heading" className="panel-heading">
              Controls
            </h2>
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
            <h2 className="panel-heading">Legend</h2>
            <Legend metric={metric} />
          </aside>

          <section className="middle" aria-labelledby="graph-heading">
            <h2 id="graph-heading" className="sr-only">
              Call graph
            </h2>
            {/*
              Both of these moved out of `aside.left`. They qualify what the canvas is
              showing, and the sidebar that used to hold them is a scrolling region —
              so on a short viewport the page could report "60 of 412 drawn" and
              "these bands do not grade" to a reader who never saw either. A caveat
              that scrolls away is a caveat the page has quietly made optional.
            */}
            <div className="graph-status">
              <p
                className={capped ? "note banner warn" : "note"}
                role="status"
                aria-live="polite"
                data-testid="shown"
              >
                {capped ? (
                  <>
                    <b>
                      {slice.hiddenByLimit} of {slice.total}
                    </b>{" "}
                    definitions are hidden by the {filters.limit}-node cap.
                    Raise &ldquo;Max nodes&rdquo; in Controls to see them — this
                    is data loss, not a footnote.
                  </>
                ) : (
                  <>
                    showing {slice.shown} of {slice.total}
                  </>
                )}
              </p>
              <BandCaveat />
            </div>
            <GraphCanvas
              elements={slice.elements}
              layout={layout}
              selected={selected}
              onSelect={setSelected}
            />
          </section>

          <aside className="right" aria-labelledby="inspector-heading">
            <h2 id="inspector-heading" className="sr-only">
              Inspector
            </h2>
            <Detail
              node={node}
              graph={graph}
              onSelect={setSelected}
              offSlice={offSlice}
            />
            <h3 className="panel-heading">Clusters at this boundary</h3>
            <ClusterTable
              clusters={slice.clusters}
              level={level}
              roots={graph.sources.map((s) => s.root)}
              phiScale={slice.phiScale}
            />
          </aside>
        </div>
      </main>
    </div>
  );
};
