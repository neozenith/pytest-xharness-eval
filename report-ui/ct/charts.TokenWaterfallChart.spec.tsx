/**
 * The per-session token waterfall: stacked bars from baseline_tokens to accumulative_billed_tokens
 * with a USD line on a second axis per turn, a stacked step area per session-log line.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import { TokenWaterfallChart } from "../src/components/charts/TokenWaterfallChart";
import type { HooksConfig } from "../playwright";
import type { Subagent } from "../src/lib/types";
import { log, result, usage } from "./fixtures";
import { chips, drawnTitles, graph, readGraph, rgb, tokens } from "./charts.helpers";

const lines = log();
const CATS = [
  "baseline_tokens (harness)",
  "cache read (re-read context)",
  "new context (input + cache write)",
  "thinking",
  "visible output",
  "subagents (spawned threads' bill)",
];
const TOTAL = "accumulative_billed_tokens";
const COST = "accumulative cost (est. USD)";

const subagent = (over: Partial<Subagent> = {}): Subagent => ({
  agent: "Explore",
  id: "sub-1",
  log: "sub-1.jsonl",
  parent_turn: 2,
  turns: 1,
  description: "look around",
  usage: usage({ input_tokens: 0, output_tokens: 1_000, cache_read_tokens: 0, cache_write_tokens: 0, cache_write_1h_tokens: 0, reasoning_tokens: 0 }),
  calls: [],
  ...over,
});

/** The set of fills Plotly painted on bar segments. */
const barFills = (c: import("@playwright/test").Locator) =>
  graph(c)
    .locator(".barlayer .point path")
    .evaluateAll((ps) => [...new Set(ps.map((p) => getComputedStyle(p).fill))]);

test.describe("TokenWaterfallChart", () => {
  test("per turn: an invisible riser, seven stacked categories and the cost line on y2", async ({ mount }) => {
    const c = await mount(<TokenWaterfallChart result={result()} lines={lines} mode="turn" />);
    const g = await readGraph(c);
    expect(g.barmode).toBe("stack");
    expect(g.traces.map((t) => t.name)).toEqual(["base", ...CATS, TOTAL, COST]);
    const byName = Object.fromEntries(g.traces.map((t) => [t.name, t]));
    expect(byName.base!.markerColor).toBe("rgba(0,0,0,0)");
    expect(byName.base!.x).toEqual(["baseline", "t1", "t2", "t3", "total"]);
    // the riser: each column stands on the running sum so far
    expect(byName.base!.y).toEqual([0, 35_599, 35_799, 110_435, 0]);
    expect(byName["baseline_tokens (harness)"]!.y).toEqual([35_599, null, null, null, null]);
    // turn 1's prompt IS the baseline, so t1 carries no read or new context
    expect(byName["cache read (re-read context)"]!.y).toEqual([null, null, 70_000, 105_000, null]);
    expect(byName["new context (input + cache write)"]!.y).toEqual([null, null, 4_236, 4_236, null]);
    expect(byName.thinking!.y).toEqual([null, 42, 42, 42, null]);
    expect(byName["visible output"]!.y).toEqual([null, 158, 358, 558, null]);
    expect(byName[TOTAL]!.y).toEqual([null, null, null, null, 220_271]);
    const cost = byName[COST]!;
    expect(cost.yaxis).toBe("y2");
    expect(cost.mode).toBe("lines+markers");
    expect(cost.x).toEqual(["baseline", "t1", "t2", "t3", "total"]);
    const expected = [0, 0.06485, 0.1522, 0.26205, 1.027646];
    cost.y.forEach((v: number | null, i: number) => expect(v).toBeCloseTo(expected[i]!, 6));
    await expect(graph(c).locator(".barlayer .trace")).toHaveCount(8);
    await expect(graph(c).locator(".scatterlayer .trace")).toHaveCount(1);
    const t = await drawnTitles(c);
    expect(t.y).toBe("tokens");
    expect(t.y2).toBe("estimated USD so far");
    await expect(chips(c)).toHaveText([...CATS, TOTAL, COST]);
  });

  test("a subagent's bill lands on the turn that spawned it and reaches the total", async ({ mount }) => {
    const c = await mount(<TokenWaterfallChart result={result({ subagents: [subagent()] })} lines={lines} mode="turn" />);
    const byName = Object.fromEntries((await readGraph(c)).traces.map((t) => [t.name, t]));
    expect(byName["subagents (spawned threads' bill)"]!.y).toEqual([null, null, 1_000, null, null]);
    expect(byName[TOTAL]!.y).toEqual([null, null, null, null, 221_271]);
  });

  test("an unpriced result draws no cost line, no second axis, no cost chip", async ({ mount }) => {
    const c = await mount(<TokenWaterfallChart result={result({ rates_applied: {} })} lines={lines} mode="turn" />);
    const g = await readGraph(c);
    expect(g.traces.map((t) => t.name)).not.toContain(COST);
    expect(g.hasY2).toBe(false);
    expect((await drawnTitles(c)).y2).toBe("");
    await expect(chips(c)).toHaveText([...CATS, TOTAL]);
  });

  test("per line: a stacked hv step area over log lines with turn marks, cost as a step on y2", async ({ mount }) => {
    const c = await mount(<TokenWaterfallChart result={result()} lines={lines} mode="line" />);
    const g = await readGraph(c);
    expect(g.traces.map((t) => t.name)).toEqual([...CATS, COST]);
    for (const t of g.traces.slice(0, 6)) {
      expect(t.stackgroup).toBe("tokens");
      expect(t.lineShape).toBe("hv");
      expect(t.x).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9]);
    }
    expect(g.traces[0]!.y).toEqual([0, 35_599, 35_599, 35_599, 35_599, 35_599, 35_599, 35_599, 35_599]);
    expect(g.traces[1]!.y).toEqual([0, 0, 0, 0, 70_000, 70_000, 70_000, 175_000, 175_000]);
    const cost = g.traces[6]!;
    expect(cost.yaxis).toBe("y2");
    expect(cost.lineShape).toBe("hv");
    expect(cost.y[0]).toBeNull();
    expect(cost.y[1]).toBeCloseTo(0.06485, 6);
    expect(g.xRange).toEqual([1, 9]);
    expect(g.annotations).toEqual(["t1", "t2", "t3"]);
    await expect(graph(c).locator(".annotation-text")).toHaveText(["t1", "t2", "t3"]);
    // the total is the height of the stack here, so it has no chip of its own
    await expect(chips(c)).toHaveText([...CATS, COST]);
    const t = await drawnTitles(c);
    expect(t.x).toBe("session-log line");
    expect(t.y).toBe("accumulative_billed_tokens so far");
  });

  test("toggling between per turn and per line redraws the same result", async ({ mount }) => {
    const c = await mount(<TokenWaterfallChart result={result()} lines={lines} mode="turn" />);
    expect((await readGraph(c)).barmode).toBe("stack");
    await c.update(<TokenWaterfallChart result={result()} lines={lines} mode="line" />);
    await expect.poll(async () => (await readGraph(c)).traces[0]!.stackgroup).toBe("tokens");
    await expect(graph(c).locator(".barlayer .trace")).toHaveCount(0);
  });

  test("a legend chip hides its category, and the cost chip hides the line", async ({ mount }) => {
    const c = await mount(<TokenWaterfallChart result={result()} lines={lines} mode="turn" />);
    await chips(c).filter({ hasText: "thinking" }).click();
    await chips(c).filter({ hasText: COST }).click();
    await expect(chips(c).filter({ hasText: COST })).toHaveAttribute("aria-pressed", "false");
    await expect
      .poll(async () => Object.fromEntries((await readGraph(c)).traces.map((t) => [t.name, t.visible])))
      .toMatchObject({ thinking: "legendonly", [COST]: "legendonly", "visible output": true });
  });

  test("unified hover over a turn lists its segments", async ({ mount, page }) => {
    const c = await mount(<TokenWaterfallChart result={result()} lines={lines} mode="turn" />);
    await readGraph(c);
    const bar = graph(c).locator(".barlayer .trace").nth(2).locator(".point").nth(2);
    const box = (await bar.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    const hover = graph(c).locator(".hoverlayer");
    await expect(hover).toContainText("70,000 · cache read (re-read context)");
    await expect(hover).toContainText("t2");
  });

  for (const mode of ["light", "dark"] as const) {
    test(`segments are painted with the ${mode} waterfall tokens`, async ({ mount }) => {
      const w = tokens.themes[mode].waterfall;
      const c = await mount<HooksConfig>(<TokenWaterfallChart result={result({ subagents: [subagent()] })} lines={lines} mode="turn" />, {
        hooksConfig: { mode },
      });
      const g = await readGraph(c);
      const byName = Object.fromEntries(g.traces.map((t) => [t.name, t]));
      expect(byName["cache read (re-read context)"]!.markerColor).toBe(w.read);
      expect(byName[TOTAL]!.markerColor).toBe(w.total);
      expect(byName[COST]!.lineColor).toBe(tokens.themes[mode].accent);
      const fills = await barFills(c);
      for (const k of ["baseline", "read", "context", "thinking", "output", "sub", "total"] as const) expect(fills).toContain(rgb(w[k]));
    });
  }

  // The note and the plot label were one fixed string: they promised a cost line an unpriced run
  // never draws, and described "the last bar" on the per-line chart, which has no bars.
  test("an unpriced result's note and label promise no cost line", async ({ mount }) => {
    const c = await mount(<TokenWaterfallChart result={result({ rates_applied: {} })} lines={lines} mode="turn" />);
    await readGraph(c);
    const panel = c.locator("#TokenWaterfallChart");
    await expect(panel).not.toContainText("running estimated cost");
    await expect(panel).toContainText("no rates_applied");
    await expect(graph(c)).not.toHaveAttribute("aria-label", /cost/);
  });

  test("per line the note describes the stacked area, not bars", async ({ mount }) => {
    const c = await mount(<TokenWaterfallChart result={result()} lines={lines} mode="line" />);
    await readGraph(c);
    const panel = c.locator("#TokenWaterfallChart");
    await expect(panel).not.toContainText(/\bbars?\b/);
    await expect(panel).toContainText("Per session-log line");
    await expect(panel).toContainText("running estimated cost");
    await expect(graph(c)).toHaveAttribute("aria-label", /session-log line/);
  });

  test("per turn the note names the last bar and the cost line", async ({ mount }) => {
    const c = await mount(<TokenWaterfallChart result={result()} lines={lines} mode="turn" />);
    await readGraph(c);
    const panel = c.locator("#TokenWaterfallChart");
    await expect(panel).toContainText("The last bar is accumulative_billed_tokens");
    await expect(panel).toContainText("running estimated cost");
    await expect(graph(c)).toHaveAttribute("aria-label", /cost/);
  });

  test("at a narrow viewport the legend wraps beneath the plot", async ({ mount, page }) => {
    await page.setViewportSize({ width: 480, height: 900 });
    const c = await mount(<TokenWaterfallChart result={result()} lines={lines} mode="turn" />);
    await readGraph(c);
    const plot = (await graph(c).boundingBox())!;
    const legend = (await c.locator('[data-el="ChartLegend"]').boundingBox())!;
    expect(legend.y).toBeGreaterThanOrEqual(plot.y + plot.height);
    expect(plot.width).toBeLessThanOrEqual(480);
  });
});
