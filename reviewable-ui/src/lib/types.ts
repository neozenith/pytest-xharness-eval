/**
 * The shape `docs/plans/maintainability/tools/graphdata.py` writes.
 *
 * This file is the other half of that contract. Change one and change the other,
 * the same rule report-ui/src/lib/types.ts follows for the report JSON.
 */

/** A boundary a call can cross. Ordered coarse to fine. */
export const LEVELS = ["language", "folder", "file", "class"] as const;
export type Level = (typeof LEVELS)[number];

/** One callable. Carries every boundary it sits inside, so the app re-clusters locally. */
export interface GraphNode {
  id: string;
  name: string;
  lang: string;
  root: string;
  folder: string;
  file: string;
  cls: string | null;
  line: number;
  /** Source lines the definition spans. */
  nloc: number;
  /** How deep in the syntax tree the definition sits. Free from the parse, and partition-free. */
  depth: number;
  isMethod: boolean;
  /** Distinct callers. */
  leverage: number;
  /** Call sites, which is larger than `leverage` whenever one caller calls twice. */
  callSites: number;
  fanOut: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  sites: number;
}

/** Conductance for one cluster at one level. `phi` is null below the volume floor. */
export interface Cluster {
  internal: number;
  cut: number;
  vol: number;
  phi: number | null;
  measurable: boolean;
  names: number;
  nloc: number;
}

export interface LevelSummary {
  clusters: number;
  modularity: number;
  insidePct: number;
}

export interface Totals {
  nodes: number;
  edges: number;
  callSites: number;
  /** Share of call sites that resolved to a definition. A validity gate, not a metric. */
  resolvedPct: number;
  ambiguous: number;
  unresolved: number;
  /** Definitions with no caller in the graph. High means the extraction is suspect. */
  orphanPct: number;
  maxDepth: number;
}

export interface Graph {
  generated: string;
  sources: { root: string; lang: string; files: number }[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  clusters: Record<Level, Record<string, Cluster>>;
  summary: Record<Level, LevelSummary>;
  totals: Totals;
}

/** Which boundary a node belongs to at a given level. */
export const clusterOf = (n: GraphNode, level: Level): string => {
  switch (level) {
    case "language":
      return n.lang;
    case "folder":
      return n.folder;
    case "file":
      return n.file;
    case "class":
      return `${n.file}::${n.cls ?? "<module>"}`;
  }
};
