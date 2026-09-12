/** The controls, the selected-node detail, and the cluster table. */
import { BAND, METRICS, phiBand, type Metric } from "@/lib/metrics";
import { shortCluster, type Filters } from "@/lib/graph";
import {
  LEVELS,
  type Cluster,
  type Graph,
  type GraphNode,
  type Level,
} from "@/lib/types";

export interface ControlsProps {
  graph: Graph;
  level: Level;
  metric: Metric;
  layout: string;
  filters: Filters;
  onLevel: (l: Level) => void;
  onMetric: (id: string) => void;
  onLayout: (l: string) => void;
  onFilters: (f: Filters) => void;
}

const LAYOUT_IDS = ["dagre", "cose", "concentric", "grid"];

export const Controls = ({
  graph,
  level,
  metric,
  layout,
  filters,
  onLevel,
  onMetric,
  onLayout,
  onFilters,
}: ControlsProps) => {
  const langs = [...new Set(graph.nodes.map((n) => n.lang))].sort();
  const set = (patch: Partial<Filters>) => onFilters({ ...filters, ...patch });

  return (
    <div className="controls" data-testid="controls">
      <label>
        Boundary
        <select
          data-testid="level"
          value={level}
          onChange={(e) => onLevel(e.target.value as Level)}
        >
          {LEVELS.map((l) => (
            <option key={l} value={l}>
              {l} · Q {graph.summary[l].modularity} ·{" "}
              {graph.summary[l].insidePct}% inside
            </option>
          ))}
        </select>
      </label>

      <label>
        Colour by
        <select
          data-testid="metric"
          value={metric.id}
          onChange={(e) => onMetric(e.target.value)}
        >
          {METRICS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
      </label>

      <label>
        Layout
        <select
          data-testid="layout"
          value={layout}
          onChange={(e) => onLayout(e.target.value)}
        >
          {LAYOUT_IDS.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      </label>

      <label>
        Search
        <input
          data-testid="search"
          type="search"
          placeholder="name or file"
          value={filters.search}
          onChange={(e) => set({ search: e.target.value })}
        />
      </label>

      <label>
        Min edge weight <span className="mono">{filters.minWeight}</span>
        <input
          data-testid="min-weight"
          type="range"
          min={1}
          max={6}
          value={filters.minWeight}
          onChange={(e) => set({ minWeight: Number(e.target.value) })}
        />
      </label>

      <label>
        Max nodes <span className="mono">{filters.limit}</span>
        <input
          data-testid="limit"
          type="range"
          min={50}
          max={800}
          step={50}
          value={filters.limit}
          onChange={(e) => set({ limit: Number(e.target.value) })}
        />
      </label>

      <fieldset className="langs">
        <legend>Language</legend>
        {langs.map((l) => (
          <label key={l} className="chip">
            <input
              type="checkbox"
              checked={filters.langs.length === 0 || filters.langs.includes(l)}
              onChange={(e) => {
                const on = e.target.checked;
                const cur = filters.langs.length === 0 ? langs : filters.langs;
                const next = on
                  ? [...new Set([...cur, l])]
                  : cur.filter((x) => x !== l);
                set({ langs: next.length === langs.length ? [] : next });
              }}
            />
            {l}
          </label>
        ))}
        <label className="chip">
          <input
            type="checkbox"
            checked={filters.hideOrphans}
            onChange={(e) => set({ hideOrphans: e.target.checked })}
          />
          hide orphans
        </label>
      </fieldset>

      <p className="note">{metric.note}</p>
    </div>
  );
};

export const Legend = ({ metric }: { metric: Metric }) => (
  <div className="legend" data-testid="legend">
    {(["low", "mid", "high", "none"] as const).map((b) => (
      <span key={b} className="swatch">
        <i style={{ background: BAND[b] }} />
        {b === "none" ? "no callers" : `${b} band`}
      </span>
    ))}
    <span className="caveat">
      Bands are uncalibrated: they show a distribution, they do not grade it.
    </span>
    <span className="sr-only">{metric.label}</span>
  </div>
);

export const Detail = ({
  node,
  graph,
}: {
  node: GraphNode | null;
  graph: Graph;
}) => {
  if (!node) return <p className="empty">Tap a node to inspect it.</p>;
  const callers = graph.edges.filter((e) => e.target === node.id);
  const callees = graph.edges.filter((e) => e.source === node.id);
  const byId = (id: string) => graph.nodes.find((n) => n.id === id)?.name ?? id;
  return (
    <div className="detail" data-testid="detail">
      <h3>{node.name}</h3>
      <p className="mono small">
        {node.file}:{node.line}
      </p>
      <dl>
        <dt>leverage</dt>
        <dd>
          {node.leverage} callers, {node.callSites} sites
        </dd>
        <dt>fan out</dt>
        <dd>{node.fanOut}</dd>
        <dt>lines</dt>
        <dd>{node.nloc}</dd>
        <dt>depth</dt>
        <dd>{node.depth}</dd>
        <dt>class</dt>
        <dd>{node.cls ?? "—"}</dd>
      </dl>
      <h4>Called by ({callers.length})</h4>
      <ul>
        {callers.slice(0, 12).map((e) => (
          <li key={e.source}>{byId(e.source)}</li>
        ))}
      </ul>
      <h4>Calls ({callees.length})</h4>
      <ul>
        {callees.slice(0, 12).map((e) => (
          <li key={e.target}>{byId(e.target)}</li>
        ))}
      </ul>
    </div>
  );
};

export const ClusterTable = ({
  clusters,
  level,
  roots,
}: {
  clusters: [string, Cluster][];
  level: Level;
  roots: string[];
}) => (
  <table className="clusters" data-testid="cluster-table">
    <thead>
      <tr>
        <th>cluster</th>
        <th>names</th>
        <th>internal</th>
        <th>cut</th>
        <th>phi</th>
      </tr>
    </thead>
    <tbody>
      {clusters.map(([key, c]) => (
        <tr key={key}>
          <td title={key}>{shortCluster(key, level, roots)}</td>
          <td>{c.names}</td>
          <td>{c.internal}</td>
          <td>{c.cut}</td>
          <td style={{ color: BAND[phiBand(c.phi, c.measurable)] }}>
            {c.measurable && c.phi !== null
              ? c.phi.toFixed(3)
              : "not measurable"}
          </td>
        </tr>
      ))}
    </tbody>
  </table>
);
