/**
 * What the chart specs read back from a mounted Plotly graph. Plotly keeps the traces and layout
 * it was last handed on the graph div (`gd.data`, `gd.layout`) and its resolved values on
 * `gd._fullLayout`; the drawn SVG is the proof the browser actually rendered them. Both are read
 * here so a spec asserts on what reached Plotly *and* on what Plotly drew.
 */
import { expect, type Locator, type Page } from "@playwright/test";
import tokens from "../../src/pytest_xharness_eval/assets/report.tokens.json" with { type: "json" };

export { tokens };

export interface TraceInfo {
  name: string | null;
  type: string;
  mode: string | null;
  visible: boolean | string;
  showlegend: boolean | null;
  x: (string | number | null)[];
  y: (number | null)[];
  yaxis: string | null;
  stackgroup: string | null;
  fill: string | null;
  fillcolor: string | null;
  lineColor: string | null;
  lineDash: string | null;
  lineShape: string | null;
  markerColor: string | null;
  hovertemplate: string | null;
}

export interface GraphInfo {
  traces: TraceInfo[];
  hovermode: string | null;
  barmode: string | null;
  fontColor: string | null;
  xTitle: string | null;
  yTitle: string | null;
  y2Title: string | null;
  hasY2: boolean;
  xRange: number[] | null;
  shapes: number;
  annotations: string[];
  width: number;
}

/** The one Plotly graph div inside `root` (the `role="img"` the `Plot` component renders). */
export const graph = (root: Locator | Page): Locator => root.locator('div[role="img"]');

/** Wait until Plotly has drawn into the graph div, then read back what it was handed. */
export async function readGraph(root: Locator | Page): Promise<GraphInfo> {
  const g = graph(root);
  await expect(g.locator(".main-svg").first()).toBeVisible();
  return g.evaluate((el) => {
    type AnyObj = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
    const gd = el as unknown as { data: AnyObj[]; layout: AnyObj; _fullLayout: AnyObj };
    const titleText = (t: unknown): string | null => (t && typeof t === "object" ? ((t as AnyObj).text ?? null) : typeof t === "string" ? t : null);
    const colorOf = (c: unknown): string | null => (typeof c === "string" ? c : null);
    return {
      traces: gd.data.map((d) => ({
        name: d.name ?? null,
        type: d.type,
        mode: d.mode ?? null,
        visible: d.visible ?? true,
        showlegend: d.showlegend ?? null,
        x: Array.from(d.x ?? []),
        y: Array.from(d.y ?? []),
        yaxis: d.yaxis ?? null,
        stackgroup: d.stackgroup ?? null,
        fill: d.fill ?? null,
        fillcolor: d.fillcolor ?? null,
        lineColor: colorOf(d.line?.color),
        lineDash: d.line?.dash ?? null,
        lineShape: d.line?.shape ?? null,
        markerColor: colorOf(d.marker?.color),
        hovertemplate: d.hovertemplate ?? null,
      })),
      hovermode: gd.layout.hovermode ?? null,
      barmode: gd.layout.barmode ?? null,
      fontColor: gd.layout.font?.color ?? null,
      xTitle: titleText(gd.layout.xaxis?.title),
      yTitle: titleText(gd.layout.yaxis?.title),
      y2Title: titleText(gd.layout.yaxis2?.title),
      hasY2: Boolean(gd.layout.yaxis2),
      xRange: gd.layout.xaxis?.range ? Array.from(gd.layout.xaxis.range as number[]) : null,
      shapes: (gd.layout.shapes ?? []).length,
      annotations: (gd.layout.annotations ?? []).map((a: AnyObj) => String(a.text)),
      width: gd._fullLayout.width,
    };
  });
}

/** The axis titles Plotly actually drew into the SVG. */
export async function drawnTitles(root: Locator | Page): Promise<{ x: string; y: string; y2: string }> {
  const g = graph(root);
  const text = async (sel: string) => ((await g.locator(sel).count()) ? ((await g.locator(sel).first().textContent()) ?? "") : "");
  return { x: await text(".g-xtitle text"), y: await text(".g-ytitle text"), y2: await text(".g-y2title text") };
}

/** `#rrggbb` as the `rgb(r, g, b)` Plotly writes into SVG styles. */
export const rgb = (hex: string): string => {
  const n = Number.parseInt(hex.slice(1), 16);
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
};

/** The legend chips of a `ChartLegend`, in order. */
export const chips = (root: Locator | Page): Locator => root.locator('[data-el="ChartLegend"] button');

/** Every `x` the drawn traces of a type put on screen (a rough count of rendered points). */
export async function drawnTraceCount(root: Locator | Page, layer: "scatterlayer" | "barlayer"): Promise<number> {
  return graph(root).locator(`.${layer} .trace`).count();
}
