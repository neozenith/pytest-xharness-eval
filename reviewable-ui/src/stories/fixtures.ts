/**
 * Shared fixtures for component stories: a small, hand-built `Graph` that matches
 * `src/lib/types.ts` exactly (no `any`, nothing widened), plus a couple of single
 * nodes and a `sliceOf` helper that runs the real `toElements` builder from
 * `src/lib/graph.ts` so a story never hand-rolls cytoscape elements or clusters --
 * it gets the same shape the app itself computes.
 *
 * The graph is two languages, three files, ten definitions. Every `leverage`,
 * `callSites` and `fanOut` on a node is the true count from `edges` below (verified
 * by hand), and every `Cluster` in `clusters` is the true internal/cut/vol for that
 * partition -- this is not filler data, it is a graph small enough to check by hand.
 */
import { DEFAULT_FILTERS, toElements, type Filters, type Slice } from "@/lib/graph";
import { metricById } from "@/lib/metrics";
import type { Cluster, Graph, GraphEdge, GraphNode, Level, LevelSummary, Totals } from "@/lib/types";

const cluster = (fields: Omit<Cluster, "phi" | "measurable"> & { phi: number | null }): Cluster => ({
  ...fields,
  measurable: fields.phi !== null,
});

const nodes: GraphNode[] = [
  {
    id: "src/pkg/core/alpha.py::parse_config",
    name: "parse_config",
    lang: "python",
    root: "src/pkg",
    folder: "src/pkg/core",
    file: "src/pkg/core/alpha.py",
    cls: null,
    line: 12,
    nloc: 22,
    depth: 4,
    isMethod: false,
    leverage: 2,
    callSites: 3,
    fanOut: 0,
  },
  {
    id: "src/pkg/core/alpha.py::load_file",
    name: "load_file",
    lang: "python",
    root: "src/pkg",
    folder: "src/pkg/core",
    file: "src/pkg/core/alpha.py",
    cls: null,
    line: 30,
    nloc: 14,
    depth: 2,
    isMethod: false,
    leverage: 2,
    callSites: 2,
    fanOut: 0,
  },
  {
    id: "src/pkg/core/alpha.py::Loader.__init__",
    name: "__init__",
    lang: "python",
    root: "src/pkg",
    folder: "src/pkg/core",
    file: "src/pkg/core/alpha.py",
    cls: "Loader",
    line: 45,
    nloc: 9,
    depth: 3,
    isMethod: true,
    leverage: 0,
    callSites: 0,
    fanOut: 1,
  },
  {
    id: "src/pkg/core/alpha.py::Loader.run",
    name: "run",
    lang: "python",
    root: "src/pkg",
    folder: "src/pkg/core",
    file: "src/pkg/core/alpha.py",
    cls: "Loader",
    line: 55,
    nloc: 48,
    depth: 14,
    isMethod: true,
    leverage: 0,
    callSites: 0,
    fanOut: 3,
  },
  {
    id: "src/pkg/core/beta.py::validate",
    name: "validate",
    lang: "python",
    root: "src/pkg",
    folder: "src/pkg/core",
    file: "src/pkg/core/beta.py",
    cls: null,
    line: 8,
    nloc: 6,
    depth: 1,
    isMethod: false,
    leverage: 2,
    callSites: 3,
    fanOut: 0,
  },
  {
    id: "src/pkg/core/beta.py::transform",
    name: "transform",
    lang: "python",
    root: "src/pkg",
    folder: "src/pkg/core",
    file: "src/pkg/core/beta.py",
    cls: null,
    line: 18,
    nloc: 31,
    depth: 7,
    isMethod: false,
    leverage: 0,
    callSites: 0,
    fanOut: 2,
  },
  {
    id: "src/pkg/core/beta.py::format_label",
    name: "format_label",
    lang: "python",
    root: "src/pkg",
    folder: "src/pkg/core",
    file: "src/pkg/core/beta.py",
    cls: null,
    line: 50,
    nloc: 5,
    depth: 1,
    isMethod: false,
    leverage: 0,
    callSites: 0,
    fanOut: 0,
  },
  {
    id: "web/app/components/Widget.tsx::useWidget",
    name: "useWidget",
    lang: "typescript",
    root: "web/app",
    folder: "web/app/components",
    file: "web/app/components/Widget.tsx",
    cls: null,
    line: 6,
    nloc: 19,
    depth: 5,
    isMethod: false,
    leverage: 2,
    callSites: 3,
    fanOut: 0,
  },
  {
    id: "web/app/components/Widget.tsx::Widget.constructor",
    name: "constructor",
    lang: "typescript",
    root: "web/app",
    folder: "web/app/components",
    file: "web/app/components/Widget.tsx",
    cls: "Widget",
    line: 28,
    nloc: 11,
    depth: 3,
    isMethod: true,
    leverage: 1,
    callSites: 1,
    fanOut: 1,
  },
  {
    id: "web/app/components/Widget.tsx::Widget.render",
    name: "render",
    lang: "typescript",
    root: "web/app",
    folder: "web/app/components",
    file: "web/app/components/Widget.tsx",
    cls: "Widget",
    line: 40,
    nloc: 58,
    depth: 11,
    isMethod: true,
    leverage: 0,
    callSites: 0,
    fanOut: 2,
  },
];

const edges: GraphEdge[] = [
  { source: "src/pkg/core/alpha.py::Loader.run", target: "src/pkg/core/alpha.py::parse_config", sites: 2 },
  { source: "src/pkg/core/alpha.py::Loader.run", target: "src/pkg/core/alpha.py::load_file", sites: 1 },
  { source: "src/pkg/core/alpha.py::Loader.run", target: "src/pkg/core/beta.py::validate", sites: 1 },
  { source: "src/pkg/core/alpha.py::Loader.__init__", target: "src/pkg/core/alpha.py::load_file", sites: 1 },
  { source: "src/pkg/core/beta.py::transform", target: "src/pkg/core/beta.py::validate", sites: 2 },
  { source: "src/pkg/core/beta.py::transform", target: "src/pkg/core/alpha.py::parse_config", sites: 1 },
  {
    source: "web/app/components/Widget.tsx::Widget.constructor",
    target: "web/app/components/Widget.tsx::useWidget",
    sites: 1,
  },
  {
    source: "web/app/components/Widget.tsx::Widget.render",
    target: "web/app/components/Widget.tsx::useWidget",
    sites: 2,
  },
  {
    source: "web/app/components/Widget.tsx::Widget.render",
    target: "web/app/components/Widget.tsx::Widget.constructor",
    sites: 1,
  },
];

const summary: Record<Level, LevelSummary> = {
  language: { clusters: 2, modularity: 0.52, insidePct: 100 },
  folder: { clusters: 2, modularity: 0.52, insidePct: 100 },
  file: { clusters: 3, modularity: 0.38, insidePct: 83.3 },
  class: { clusters: 5, modularity: 0.15, insidePct: 25 },
};

const clusters: Record<Level, Record<string, Cluster>> = {
  language: {
    python: cluster({ internal: 8, cut: 0, vol: 16, phi: 0, names: 7, nloc: 135 }),
    typescript: cluster({ internal: 4, cut: 0, vol: 8, phi: 0, names: 3, nloc: 88 }),
  },
  folder: {
    "src/pkg/core": cluster({ internal: 8, cut: 0, vol: 16, phi: 0, names: 7, nloc: 135 }),
    "web/app/components": cluster({ internal: 4, cut: 0, vol: 8, phi: 0, names: 3, nloc: 88 }),
  },
  file: {
    "src/pkg/core/alpha.py": cluster({ internal: 4, cut: 2, vol: 10, phi: 0.2, names: 4, nloc: 93 }),
    "src/pkg/core/beta.py": cluster({ internal: 2, cut: 2, vol: 6, phi: 0.333, names: 3, nloc: 42 }),
    "web/app/components/Widget.tsx": cluster({ internal: 4, cut: 0, vol: 8, phi: 0, names: 3, nloc: 88 }),
  },
  class: {
    "src/pkg/core/alpha.py::<module>": cluster({ internal: 0, cut: 5, vol: 5, phi: null, names: 2, nloc: 36 }),
    "src/pkg/core/alpha.py::Loader": cluster({ internal: 0, cut: 5, vol: 5, phi: 1, names: 2, nloc: 57 }),
    "src/pkg/core/beta.py::<module>": cluster({ internal: 2, cut: 2, vol: 6, phi: 0.333, names: 3, nloc: 42 }),
    "web/app/components/Widget.tsx::<module>": cluster({ internal: 0, cut: 3, vol: 3, phi: null, names: 1, nloc: 19 }),
    "web/app/components/Widget.tsx::Widget": cluster({ internal: 1, cut: 3, vol: 5, phi: 0.6, names: 2, nloc: 69 }),
  },
};

const totals: Totals = {
  nodes: nodes.length,
  edges: edges.length,
  callSites: edges.reduce((n, e) => n + e.sites, 0),
  resolvedPct: 92.5,
  ambiguous: 2,
  unresolved: 3,
  orphanPct: 50,
  maxDepth: 14,
};

/** A small, hand-verified graph: two languages, three files, ten definitions. */
export const sampleGraph: Graph = {
  generated: "2026-08-01T09:30:00.000Z",
  sources: [
    { root: "src/pkg", lang: "python", files: 2 },
    { root: "web/app", lang: "typescript", files: 1 },
  ],
  nodes,
  edges,
  clusters,
  summary,
  totals,
};

/** What a fatal-free but data-free graph looks like: every record present, all zero. */
export const emptyGraph: Graph = {
  generated: "2026-08-01T09:30:00.000Z",
  sources: [],
  nodes: [],
  edges: [],
  clusters: { language: {}, folder: {}, file: {}, class: {} },
  summary: {
    language: { clusters: 0, modularity: 0, insidePct: 0 },
    folder: { clusters: 0, modularity: 0, insidePct: 0 },
    file: { clusters: 0, modularity: 0, insidePct: 0 },
    class: { clusters: 0, modularity: 0, insidePct: 0 },
  },
  totals: {
    nodes: 0,
    edges: 0,
    callSites: 0,
    resolvedPct: 0,
    ambiguous: 0,
    unresolved: 0,
    orphanPct: 0,
    maxDepth: 0,
  },
};

const nodeById = (id: string): GraphNode => {
  const found = sampleGraph.nodes.find((n) => n.id === id);
  if (!found) throw new Error(`fixtures: no node with id ${id}`);
  return found;
};

/** `Loader.run`: a hub. Calls three other definitions, is called by none. */
export const hubNode: GraphNode = nodeById("src/pkg/core/alpha.py::Loader.run");

/** `useWidget`: called from two places, calls out to nothing. */
export const calledNode: GraphNode = nodeById("web/app/components/Widget.tsx::useWidget");

/** `format_label`: a true orphan -- no caller, no callee, isolated in the graph. */
export const orphanNode: GraphNode = nodeById("src/pkg/core/beta.py::format_label");

/** Filters at the extremes the range inputs allow, with a language pinned and search set. */
export const extremeFilters: Filters = {
  langs: ["python"],
  search: "widget",
  hideOrphans: true,
  minWeight: 6,
  limit: 800,
};

/** Runs the real `toElements` builder so a story's elements/clusters are never hand-rolled. */
export const sliceOf = (
  graph: Graph,
  level: Level = "file",
  metricId = "leverage",
  filters: Filters = DEFAULT_FILTERS,
): Slice => toElements(graph, level, metricById(metricId), filters);
