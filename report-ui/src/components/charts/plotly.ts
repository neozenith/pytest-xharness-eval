/**
 * The Plotly side of the design tokens (ADR 0024): Plotly writes concrete colours into SVG
 * attributes, so the `--xh-*` custom properties are resolved to their current values here
 * and re-resolved whenever the theme flips. Every chart builds its layout from this one
 * theme object; nothing hardcodes a colour.
 */
import { useEffect, useState } from "react";
import type { Layout } from "plotly.js";

export interface ChartTheme {
  ink: string;
  muted: string;
  grid: string;
  /** The baseline and its ticks: a step darker than `grid`, so the anchor outranks the ladder. */
  axis: string;
  plot: string;
  panel: string;
  accent: string;
  fontBody: string;
  fontMono: string;
  series: string[];
  waterfall: Record<string, string>;
}

const FALLBACK: Record<string, string> = {
  "--xh-ink": "#1f2430",
  "--xh-muted": "#6b7280",
  "--xh-grid": "#e5e7eb",
  "--xh-axis": "#c8ccd6",
  "--xh-plot": "#ffffff",
  "--xh-panel": "#ffffff",
  "--xh-accent": "#2563eb",
  "--xh-font-body": "system-ui, sans-serif",
  "--xh-font-mono": "ui-monospace, monospace",
  "--xh-series-1": "#2563eb",
  "--xh-series-2": "#0d9488",
  "--xh-series-3": "#d97706",
  "--xh-series-4": "#dc2626",
  "--xh-series-5": "#7c3aed",
  "--xh-series-6": "#db2777",
  "--xh-series-7": "#65a30d",
  "--xh-series-8": "#0891b2",
  "--xh-waterfall-baseline": "#94a3b8",
  "--xh-waterfall-read": "#93c5fd",
  "--xh-waterfall-context": "#2563eb",
  "--xh-waterfall-thinking": "#a855f7",
  "--xh-waterfall-output": "#16a34a",
  "--xh-waterfall-sub": "#ea580c",
  "--xh-waterfall-total": "#475569",
};

function cssVar(styles: CSSStyleDeclaration, name: string): string {
  return styles.getPropertyValue(name).trim() || FALLBACK[name] || "#888888";
}

export function readChartTheme(): ChartTheme {
  const styles = typeof document === "undefined" ? null : getComputedStyle(document.documentElement);
  const get = (name: string) => (styles ? cssVar(styles, name) : (FALLBACK[name] ?? "#888888"));
  return {
    ink: get("--xh-ink"),
    muted: get("--xh-muted"),
    grid: get("--xh-grid"),
    axis: get("--xh-axis"),
    plot: get("--xh-plot"),
    panel: get("--xh-panel"),
    accent: get("--xh-accent"),
    fontBody: get("--xh-font-body"),
    fontMono: get("--xh-font-mono"),
    series: Array.from({ length: 8 }, (_, i) => get(`--xh-series-${i + 1}`)),
    waterfall: Object.fromEntries(["baseline", "read", "context", "thinking", "output", "sub", "total"].map((k) => [k, get(`--xh-waterfall-${k}`)])),
  };
}

/** The current theme, re-read when the root element's class or inline style changes (the theme toggle does both). */
export function useChartTheme(): ChartTheme {
  const [theme, setTheme] = useState<ChartTheme>(readChartTheme);
  useEffect(() => {
    const observer = new MutationObserver(() => setTheme(readChartTheme()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "style"] });
    return () => observer.disconnect();
  }, []);
  return theme;
}

/**
 * Series past the token palette cycle through it with a different dash per lap (ADR 0031):
 * sixteen sessions stay sixteen distinguishable lines without inventing colours.
 */
export const seriesColor = (t: ChartTheme, i: number): string => t.series[i % t.series.length] ?? t.accent;

const DASHES = ["solid", "dash", "dot", "dashdot"] as const;
export const seriesDash = (t: ChartTheme, i: number): (typeof DASHES)[number] => DASHES[Math.floor(i / t.series.length) % DASHES.length] ?? "solid";

export interface AxisOptions {
  title?: string;
  compact?: boolean;
  integer?: boolean;
}

export function axis(t: ChartTheme, { title, compact, integer }: AxisOptions = {}): Partial<Layout["xaxis"]> {
  return {
    title: title ? { text: title, font: { color: t.muted, size: 11 }, standoff: 10 } : undefined,
    // `grid` rules the ladder, `axis` the rules that anchor it: gridlines recede, spines and
    // the zero line hold. This object is spread over the frames below, so it must agree with them.
    gridcolor: t.grid,
    zerolinecolor: t.axis,
    linecolor: t.axis,
    tickfont: { color: t.muted, size: 11 },
    automargin: true,
    ...(compact ? { tickformat: "~s" } : {}),
    ...(integer ? { tickformat: ",d", dtick: undefined } : {}),
  };
}

/**
 * The grid does the reading, not the frame. Values run left to right, so only the horizontal
 * rules survive: the y axis keeps its gridlines and drops its spine, the x axis keeps a spine
 * and short outward ticks and drops its gridlines. What is left is a baseline and a ladder —
 * every vertical rule that used to cut through the bars is gone. The two are drawn in
 * different tokens on purpose: the ladder in `grid`, the baseline and the zero line in the
 * darker `axis`, so the rule the data stands on never reads as one more gridline.
 */
const xAxisFrame = (t: ChartTheme) => ({
  showgrid: false,
  zeroline: false,
  showline: true,
  linecolor: t.axis,
  linewidth: 1,
  ticks: "outside" as const,
  ticklen: 4,
  tickcolor: t.axis,
  // No crosshair: Plotly lays a solid contrast-coloured underlay two pixels wider than any
  // spike it draws, which is a white halo over a dark plot. The unified hover box names its
  // own x value in the title, so the anchor is already there.
  showspikes: false,
});

const yAxisFrame = (t: ChartTheme) => ({
  showgrid: true,
  gridcolor: t.grid,
  gridwidth: 1,
  zeroline: true,
  zerolinecolor: t.axis,
  zerolinewidth: 1,
  showline: false,
  ticks: "" as const,
  showspikes: false,
});

/** Transparent paper over the card, token ink and grid, unified hover: the frame every chart shares. */
export function baseLayout(t: ChartTheme, overrides: Partial<Layout> = {}): Partial<Layout> {
  const { xaxis, yaxis, ...rest } = overrides;
  return {
    autosize: true,
    // `automargin` on both axes grows these back when a tick or title needs the room, so the
    // frame starts tight instead of reserving a gutter every chart then has to fill.
    margin: { t: 12, r: 8, b: 40, l: 56 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: t.fontBody, size: 12, color: t.ink },
    showlegend: false,
    hovermode: "x unified",
    hoverlabel: {
      bgcolor: t.panel,
      // Plotly gives a hover box no elevation, so its border is the whole edge. On `grid` the
      // box was panel-on-panel held together by an invisible hairline; `muted` reads as a real
      // boundary over empty plot area in both themes (6.2:1 light, 6.7:1 dark).
      bordercolor: t.muted,
      align: "left",
      // Series names here are sentences ("new context (input + cache write)"); Plotly's default
      // truncates them to 15 characters, which reads as a different series.
      namelength: -1,
      font: { color: t.ink, size: 11, family: t.fontBody },
    },
    ...rest,
    xaxis: { ...xAxisFrame(t), ...xaxis },
    yaxis: { ...yAxisFrame(t), ...yaxis },
  };
}

/** Dotted vertical marks at each turn's measuring log line, labelled `t<n>` (per-line axis, ADR 0025). */
export function turnMarks(t: ChartTheme, starts: number[]): Pick<Partial<Layout>, "shapes" | "annotations"> {
  return {
    shapes: starts.map((s) => ({
      type: "line",
      x0: s,
      x1: s,
      y0: 0,
      y1: 1,
      yref: "paper",
      // `axis`, not `grid`: a turn start anchors the reading the way the baseline does, and at
      // grid weight the dotted rule vanished against the paper while still cutting the bars.
      line: { color: t.axis, width: 1, dash: "dot" },
    })),
    annotations: starts.map((s, i) => ({
      x: s,
      y: 1,
      yref: "paper",
      yanchor: "bottom",
      text: `t${i + 1}`,
      showarrow: false,
      font: { color: t.muted, size: 10 },
    })),
  };
}
