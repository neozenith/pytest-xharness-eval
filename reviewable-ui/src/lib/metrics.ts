/**
 * The metrics a node can be coloured by, and the bands each one uses.
 *
 * Bands are NOT calibrated. Nothing in docs/plans/maintainability/ has derived a
 * threshold that separates good from bad, and the experiments there show every
 * candidate objective has a degenerate optimum. These bands exist to make a
 * distribution visible, not to grade it, which is why the legend says "band"
 * rather than "good" or "bad".
 */
import type { GraphNode } from "./types";

/** Data-encoding colours: they mean a band, not a brand, so they never re-skin. */
export const BAND = {
  low: "#047857",
  mid: "#b45309",
  high: "#b91c1c",
  none: "#64748b",
} as const;

export type BandKey = keyof typeof BAND;

export interface Metric {
  id: string;
  label: string;
  /** What the number means, shown under the selector. */
  note: string;
  value: (n: GraphNode) => number;
  /** Band for a value. `none` is reserved for "not measurable", never for zero-is-fine. */
  band: (v: number) => BandKey;
  format: (v: number) => string;
}

const int = (v: number) => String(v);

export const METRICS: Metric[] = [
  {
    id: "leverage",
    label: "Leverage",
    note: "Distinct callers. 1 means a name that saves nobody any reading; 3+ means a rule.",
    value: (n) => n.leverage,
    band: (v) =>
      v === 0 ? "none" : v === 1 ? "high" : v === 2 ? "mid" : "low",
    format: int,
  },
  {
    id: "callSites",
    label: "Call sites",
    note: "Total call sites, which exceeds leverage whenever one caller calls twice.",
    value: (n) => n.callSites,
    band: (v) => (v === 0 ? "none" : v === 1 ? "high" : v <= 3 ? "mid" : "low"),
    format: int,
  },
  {
    id: "nloc",
    label: "Lines",
    note: "Source lines the definition spans. The best-evidenced static predictor of comprehension difficulty.",
    value: (n) => n.nloc,
    band: (v) => (v <= 15 ? "low" : v <= 40 ? "mid" : "high"),
    format: (v) => `${v} ln`,
  },
  {
    id: "depth",
    label: "Nesting depth",
    note: "How deep in the syntax tree the definition sits. Needs no partition, and extraction moves it rather than reducing it.",
    value: (n) => n.depth,
    band: (v) => (v <= 6 ? "low" : v <= 12 ? "mid" : "high"),
    format: (v) => `depth ${v}`,
  },
  {
    id: "fanOut",
    label: "Fan out",
    note: "Distinct names this one calls. High fan-out is a coordinator; zero is a leaf.",
    value: (n) => n.fanOut,
    band: (v) => (v === 0 ? "none" : v <= 3 ? "low" : v <= 8 ? "mid" : "high"),
    format: int,
  },
];

export const metricById = (id: string): Metric =>
  METRICS.find((m) => m.id === id) ?? METRICS[0]!;

/** Node diameter in pixels, on a square-root scale so area tracks the value. */
export const sizeFor = (v: number, max: number): number => {
  if (max <= 0) return 18;
  return 14 + 46 * Math.sqrt(Math.min(v, max) / max);
};

/** Conductance band, shared by the cluster table and the compound tint. */
export const phiBand = (phi: number | null, measurable: boolean): BandKey => {
  if (phi === null || !measurable) return "none";
  return phi < 0.25 ? "low" : phi < 0.5 ? "mid" : "high";
};
