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

/**
 * Data-encoding colours: they mean a band, not a brand, so they never re-skin.
 *
 * Chosen for WCAG 2.2 AAA: every value clears 7:1 against both panel (#111a2e)
 * and canvas (#0b1120) backgrounds, the two surfaces a band colour is ever read
 * against (legend swatch, cluster-table text, node fill) — comfortably above
 * the 3:1 a graphical object alone would need. Ratios (WebAIM formula):
 *   low  #34d399 on panel 9.02:1, on bg 9.79:1
 *   mid  #fb923c on panel 7.66:1, on bg 8.32:1
 *   high #fca5a5 on panel 9.14:1, on bg 9.92:1
 *   none #a3b3c9 on panel 8.13:1, on bg 8.83:1
 */
export const BAND = {
  low: "#34d399",
  mid: "#fb923c",
  high: "#fca5a5",
  none: "#a3b3c9",
} as const;

export type BandKey = keyof typeof BAND;

/**
 * Colour is never the only channel a band is carried on (WCAG 1.4.1): every band
 * also gets a distinct cytoscape node shape, drawn in the legend and on the
 * canvas alike.
 */
export const BAND_SHAPE: Record<BandKey, string> = {
  low: "ellipse",
  mid: "hexagon",
  high: "diamond",
  none: "rectangle",
};

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
