/**
 * The metrics a node can be coloured by, and the bands each one uses.
 *
 * Bands are NOT calibrated. Nothing in docs/plans/maintainability/ has derived a
 * threshold that separates good from bad, and the experiments there show every
 * candidate objective has a degenerate optimum. These bands exist to make a
 * distribution visible, not to grade it, which is why the legend says "band"
 * rather than "good" or "bad".
 *
 * Two consequences of that are load-bearing here, because both were quietly
 * violated by earlier revisions of this file:
 *
 *   1. A band is a rank, never a verdict. The palette below therefore encodes
 *      magnitude and nothing else -- see BAND.
 *   2. Conductance in particular has no fixed threshold and never will (the
 *      README says so four times over). Its banding is therefore relative to the
 *      graph in front of you -- see phiScale -- not against constants.
 */
import type { GraphNode } from "./types";

/**
 * Data-encoding colours: they mean a band, not a brand, so they never re-skin.
 *
 * This palette is the result of a constrained search (tmp/band_final.py), not a
 * hand-pick, because the constraints pull against each other:
 *
 *   AAA (WCAG 1.4.6): a band colour is used as TEXT -- the cluster-table phi cell
 *     and the band chip -- so it needs 7:1, not the 3:1 a purely graphical object
 *     would need, and it needs it against BOTH surfaces a band is read on:
 *       low  #09dddb  panel 10.22:1   canvas 11.10:1
 *       mid  #97edae  panel 12.42:1   canvas 13.49:1
 *       high #f5f299  panel 14.90:1   canvas 16.18:1
 *       none #a3b3c9  panel  8.13:1   canvas  8.83:1
 *
 *   No valence. The previous palette ran emerald -> orange -> red, which says
 *     good -> bad. Nothing here has earned the right to say that: the bands are a
 *     distribution, so the ramp is cyan -> mint -> pale yellow, which has no
 *     "bad" pole to land on.
 *
 *   Monotone lightness. L* runs 80.1 -> 87.1 -> 94.0, with `none` at 72.4, below
 *     the whole ramp. That is the actual magnitude encoding, and it is the one
 *     channel that survives every colour vision deficiency including
 *     monochromacy (greyscale: #c7c7c7 -> #dadada -> #eeeeee, none #b2b2b2).
 *     The old palette's L* was 75.8 -> 70.5 -> 76.3: its mid band was the
 *     DARKEST of the three, so lightness said nothing about rank and hue had to
 *     carry it alone -- which is precisely why it reached for green-to-red.
 *
 * The cost is measured, not waved away: monotone lightness plus the AAA floor
 * narrows the usable sRGB gamut, dropping the worst-case CIEDE2000 separation
 * among the three ranked bands from 18.6 to 11.8 (across normal, protanopic and
 * deuteranopic vision). 11.8 is still comfortably distinct, and BAND_SHAPE below
 * is what makes that acceptable rather than merely tolerable.
 */
export const BAND = {
  low: "#09dddb",
  mid: "#97edae",
  high: "#f5f299",
  none: "#a3b3c9",
} as const;

export type BandKey = keyof typeof BAND;

/**
 * Colour is never the only channel a band is carried on (WCAG 1.4.1): every band
 * also gets a distinct cytoscape node shape, drawn in the legend and on the
 * canvas alike.
 *
 * This is not redundancy for its own sake. AAA pins every swatch above L*~68, so
 * four swatches have roughly 32 L* units to share and adjacent bands can differ
 * by at most ~5 CIEDE2000 in greyscale no matter how they are chosen. Colour
 * provably cannot carry four ranks under that constraint; shape carries the rest.
 *
 * The shapes are ordered too, by how angular they are (round -> six sides ->
 * four), so they read as a progression rather than three arbitrary glyphs.
 * `none` is a rectangle: outside the ramp, because it means "not measurable".
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
  /**
   * Band for a value. `none` is reserved for "not measurable", never for
   * zero-is-fine.
   *
   * Every metric here bands MONOTONICALLY in magnitude: a larger value never
   * bands lower. Two of them used to invert -- leverage 1 banded "high" and
   * leverage 3+ banded "low", because 1 was judged worse than 3 -- which made
   * the band a verdict rather than a rank, and put two metrics on the opposite
   * polarity to the other three while sharing one legend. Whether a big number
   * is good is the reader's call; the band's job is only to say it is big.
   */
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
      v === 0 ? "none" : v === 1 ? "low" : v === 2 ? "mid" : "high",
    format: int,
  },
  {
    id: "callSites",
    label: "Call sites",
    note: "Total call sites, which exceeds leverage whenever one caller calls twice.",
    value: (n) => n.callSites,
    band: (v) => (v === 0 ? "none" : v === 1 ? "low" : v <= 3 ? "mid" : "high"),
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

/** What phiScale needs off a cluster: its conductance, and whether it has one. */
export interface PhiSample {
  phi: number | null;
  measurable: boolean;
}

/** A conductance banding derived from one graph's own distribution. */
export interface PhiScale {
  /**
   * The two cut points the bands are split on, or null when there were too few
   * measurable clusters to rank. Exposed so the UI can state them: a relative
   * band that does not say what it is relative to is just a threshold again.
   */
  cuts: readonly [number, number] | null;
  /** How many measurable clusters the cuts were derived from. */
  n: number;
  /** Band for one cluster, relative to the rest of this graph. */
  band: (phi: number | null, measurable: boolean) => BandKey;
}

/**
 * Band conductance by its rank WITHIN THIS GRAPH, never against a constant.
 *
 * This used to be `phi < 0.25 ? "low" : phi < 0.5 ? "mid" : "high"`. Those two
 * numbers were invented. docs/plans/maintainability/README.md is unusually
 * explicit that they cannot exist -- "No thresholds exist", "There is no
 * threshold separating a good score from a bad one", "Anyone who tells you a
 * phi of 0.4 is a problem is making that up", "Conductance has no fixed
 * threshold and never will", "gate on the delta and never on the value" -- so a
 * tool built on that research grading a cluster against 0.25 contradicted its
 * own premise in the one place a reader would believe it.
 *
 * Terciles of the measurable clusters are the honest replacement, and they have
 * a precedent the README already cites: Alves, Ypma and Visser (ICSM 2010)
 * derive metric thresholds from benchmark percentiles rather than asserting
 * them. The claim shrinks from "this cluster is bad" to "this cluster is in the
 * upper third of this graph", which is all the data supports.
 *
 * Below three measurable clusters there is no distribution to rank, so every
 * measurable cluster bands `mid` and `cuts` is null -- saying nothing, rather
 * than manufacturing a spread out of one or two points.
 */
export const phiScale = (clusters: Iterable<PhiSample>): PhiScale => {
  const sorted = [...clusters]
    .filter((c): c is PhiSample & { phi: number } => c.measurable && c.phi !== null)
    .map((c) => c.phi)
    .sort((a, b) => a - b);
  const n = sorted.length;
  // Nearest-rank percentiles. Ties can collapse a band to empty, which is the
  // correct reading of a degenerate distribution rather than a case to smooth over.
  const cuts: readonly [number, number] | null =
    n >= 3 ? [sorted[Math.floor(n / 3)]!, sorted[Math.floor((2 * n) / 3)]!] : null;
  return {
    cuts,
    n,
    band: (phi, measurable) => {
      if (phi === null || !measurable) return "none";
      if (!cuts) return "mid";
      return phi < cuts[0] ? "low" : phi < cuts[1] ? "mid" : "high";
    },
  };
};
