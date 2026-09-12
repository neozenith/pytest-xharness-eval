/** The controls, the selected-node detail, and the cluster table. */
import {
  BAND,
  BAND_SHAPE,
  METRICS,
  phiBand,
  type BandKey,
  type Metric,
} from "@/lib/metrics";
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

/** Each band's shape, rendered as a small CSS icon so colour is never the only channel. */
const ShapeIcon = ({ band }: { band: BandKey }) => (
  <i
    className={`swatch-shape shape-${BAND_SHAPE[band]}`}
    style={{ background: BAND[band] }}
    aria-hidden="true"
  />
);

export const Legend = ({ metric }: { metric: Metric }) => (
  <div className="legend" data-testid="legend">
    <p className="note">
      Colour <em>and</em> shape both encode <strong>{metric.label}</strong>.
    </p>
    {(["low", "mid", "high", "none"] as const).map((b) => (
      <span key={b} className="swatch">
        <ShapeIcon band={b} />
        {b === "none" ? "no callers" : `${b} band`}
      </span>
    ))}
    <span className="caveat">
      Bands are uncalibrated: they show a distribution, they do not grade it.
    </span>
  </div>
);

export const Detail = ({
  node,
  graph,
  onSelect,
}: {
  node: GraphNode | null;
  graph: Graph;
  /** Optional: lets "called by" / "calls" entries jump the selection there too. */
  onSelect?: (id: string) => void;
}) => {
  // The empty state keeps the same testid as the populated one. A panel that changes
  // its identity with its state ("I am `detail` when full, an anonymous <p> when
  // empty") makes the empty state unaddressable -- to a test runner, and to anything
  // else that wants to point at the inspector regardless of what is in it.
  if (!node)
    return (
      <p className="empty" data-testid="detail">
        Tap a node to inspect it.
      </p>
    );
  const callers = graph.edges.filter((e) => e.target === node.id);
  const callees = graph.edges.filter((e) => e.source === node.id);
  const byId = (id: string) => graph.nodes.find((n) => n.id === id)?.name ?? id;
  return (
    <div className="detail" data-testid="detail">
      {/* Only the identity line is announced on selection change (WCAG 4.1.3):
          the full metric dump below would make every click read out a wall of
          text, which is worse than saying nothing. */}
      <div aria-live="polite">
        <h3>{node.name}</h3>
        <p className="mono small">
          {node.file}:{node.line}
        </p>
      </div>
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
      <ul className="jump-list">
        {callers.slice(0, 12).map((e) => (
          <li key={e.source}>
            <button type="button" onClick={() => onSelect?.(e.source)}>
              {byId(e.source)}
            </button>
          </li>
        ))}
      </ul>
      <h4>Calls ({callees.length})</h4>
      <ul className="jump-list">
        {callees.slice(0, 12).map((e) => (
          <li key={e.target}>
            <button type="button" onClick={() => onSelect?.(e.target)}>
              {byId(e.target)}
            </button>
          </li>
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
        <th scope="col">cluster</th>
        <th scope="col">names</th>
        <th scope="col">internal</th>
        <th scope="col">cut</th>
        <th scope="col">phi</th>
      </tr>
    </thead>
    <tbody>
      {clusters.map(([key, c]) => {
        const band = phiBand(c.phi, c.measurable);
        return (
          <tr key={key}>
            <td title={key}>{shortCluster(key, level, roots)}</td>
            <td>{c.names}</td>
            <td>{c.internal}</td>
            <td>{c.cut}</td>
            <td className={`phi-cell band-${band}`} style={{ color: BAND[band] }}>
              {c.measurable && c.phi !== null ? c.phi.toFixed(3) : "not measurable"}
            </td>
          </tr>
        );
      })}
    </tbody>
  </table>
);
