/** Loading the graph, and turning a filtered slice of it into cytoscape elements. */
import type { ElementDefinition } from "cytoscape";
import { BAND, phiScale, sizeFor, type Metric, type PhiScale } from "./metrics";
import {
  clusterOf,
  type Cluster,
  type Graph,
  type GraphNode,
  type Level,
} from "./types";

export const loadGraph = async (url = "graph.json"): Promise<Graph> => {
  const res = await fetch(`${url}?v=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${url}: ${res.status} ${res.statusText}`);
  return (await res.json()) as Graph;
};

export interface Filters {
  /** Empty means every language. */
  langs: string[];
  /** Substring match on name or file. */
  search: string;
  /** Hide definitions with no caller in the graph. */
  hideOrphans: boolean;
  /** Drop edges below this call-site weight. Legibility, not truth. */
  minWeight: number;
  /** Cap on rendered nodes; the densest graphs are unreadable whole. */
  limit: number;
}

export const DEFAULT_FILTERS: Filters = {
  langs: [],
  search: "",
  hideOrphans: false,
  minWeight: 1,
  limit: 150,
};

export interface Slice {
  elements: ElementDefinition[];
  shown: number;
  total: number;
  hiddenByLimit: number;
  clusters: [string, Cluster][];
  /**
   * Which definitions survived the filters, and which of those actually made the cap.
   * Both, not just the second: selection outlives the view (the detail panel's
   * caller/callee buttons jump to nodes that may not be drawn), and "not on screen"
   * is useless to a reader who cannot tell which control to move to fix it.
   */
  keptIds: Set<string>;
  visibleIds: Set<string>;
  /**
   * The conductance banding for this boundary, carried on the slice so the canvas
   * tint and the cluster table band against the same distribution. Two callers
   * each deriving their own scale is how they would quietly disagree.
   */
  phiScale: PhiScale;
}

const matches = (n: GraphNode, f: Filters): boolean => {
  if (f.langs.length && !f.langs.includes(n.lang)) return false;
  if (f.hideOrphans && n.leverage === 0) return false;
  if (f.search) {
    const q = f.search.toLowerCase();
    if (!n.name.toLowerCase().includes(q) && !n.file.toLowerCase().includes(q))
      return false;
  }
  return true;
};

/**
 * Build the cytoscape elements for one view.
 *
 * Nodes are grouped into compound parents at `level`. Ranking by the active metric
 * before applying `limit` means the cap keeps what the reader is looking at rather
 * than whatever the parser happened to emit first.
 */
export const toElements = (
  graph: Graph,
  level: Level,
  metric: Metric,
  f: Filters,
): Slice => {
  const roots = graph.sources.map((s) => s.root);
  const kept = graph.nodes.filter((n) => matches(n, f));
  const ranked = [...kept].sort((a, b) => metric.value(b) - metric.value(a));
  const visible = ranked.slice(0, f.limit);
  const ids = new Set(visible.map((n) => n.id));

  const max = visible.reduce((m, n) => Math.max(m, metric.value(n)), 0);
  const used = new Set(visible.map((n) => clusterOf(n, level)));

  // Ranked against EVERY cluster at this boundary, not just the visible ones. A
  // band that shifted as you dragged the node cap or typed in the search box would
  // be measuring the filter rather than the graph.
  const scale = phiScale(Object.values(graph.clusters[level]));

  const elements: ElementDefinition[] = [];
  for (const key of used) {
    const c = graph.clusters[level][key];
    const band = scale.band(c?.phi ?? null, c?.measurable ?? false);
    elements.push({
      data: {
        id: `C::${key}`,
        label: shortCluster(key, level, roots),
        kind: "cluster",
        phi: c?.phi ?? null,
        band,
        tint: BAND[band],
      },
    });
  }

  for (const n of visible) {
    const v = metric.value(n);
    elements.push({
      data: {
        id: n.id,
        parent: `C::${clusterOf(n, level)}`,
        label: n.name,
        kind: "def",
        band: metric.band(v),
        colour: BAND[metric.band(v)],
        size: sizeFor(v, max),
        value: v,
      },
    });
  }

  for (const e of graph.edges) {
    if (e.sites < f.minWeight) continue;
    if (!ids.has(e.source) || !ids.has(e.target)) continue;
    elements.push({
      data: {
        id: `${e.source}->${e.target}`,
        source: e.source,
        target: e.target,
        sites: e.sites,
      },
    });
  }

  const clusters = [...used]
    .map((k) => [k, graph.clusters[level][k]!] as [string, Cluster])
    .filter(([, c]) => c)
    .sort((a, b) => (a[1].phi ?? 2) - (b[1].phi ?? 2));

  return {
    elements,
    shown: visible.length,
    total: kept.length,
    hiddenByLimit: kept.length - visible.length,
    clusters,
    keptIds: new Set(kept.map((n) => n.id)),
    visibleIds: ids,
    phiScale: scale,
  };
};

/** Cluster keys are paths; the tail is what identifies them on screen. */
export const shortCluster = (
  key: string,
  level: Level,
  roots: string[] = [],
): string => {
  if (level === "language") return key;
  if (level === "class") {
    const [file, cls] = key.split("::");
    return `${file!.split("/").pop()} · ${cls}`;
  }
  const stripped = roots.reduce(
    (k, r) => (k.startsWith(r + "/") ? k.slice(r.length + 1) : k),
    key,
  );
  const parts = stripped.split("/");
  return parts.slice(-2).join("/") || stripped;
};
