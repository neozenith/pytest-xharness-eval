/**
 * The overview's aggregate waterfall: a mean column per turn index over the runs that reached it,
 * faded by how many did, with a min–max whisker riding the top of each stack.
 */
import { expect, test } from "./test";
import { TokenWaterfallAggregateChart } from "../src/components/charts/TokenWaterfallAggregateChart";
import type { HooksConfig } from "../playwright";
import type { Cell, RunResult } from "../src/lib/types";
import { call, cell, result, sweep } from "./fixtures";
import { chips, drawnTitles, graph, readGraph, rgb, tokens } from "./charts.helpers";

const resultsFor = (cells: Cell[], over: (c: Cell) => Partial<RunResult> = () => ({})): Record<string, RunResult> =>
  Object.fromEntries(cells.map((c) => [c.session_id, result({ session_id: c.session_id, harness: c.harness, model: c.model, effort: c.effort, ...over(c) })]));

const CATS = [
  "baseline_tokens (harness)",
  "cache read (re-read context)",
  "new context (input + cache write)",
  "thinking",
  "visible output",
  "subagents (spawned threads' bill)",
  "accumulative_billed_tokens",
];
const SPREAD = "min–max across runs";

/** Read the whisker trace's error arrays and the bars' per-point opacity straight off the graph. */
const extras = (c: import("@playwright/test").Locator) =>
  graph(c).evaluate((el) => {
    const gd = el as unknown as { data: { name: string; marker?: { opacity?: number[] }; error_y?: { array: number[]; arrayminus: number[] } }[] };
    const spread = gd.data.find((d) => d.name === "min–max across runs")!;
    const read = gd.data.find((d) => d.name === "cache read (re-read context)")!;
    return { plus: spread.error_y!.array, minus: spread.error_y!.arrayminus, opacity: read.marker!.opacity! };
  });

test.describe("TokenWaterfallAggregateChart", () => {
  test("every rung of the sweep folds into one mean waterfall of all the runs in view", async ({ mount }) => {
    const cells = sweep();
    const c = await mount(<TokenWaterfallAggregateChart cells={cells} results={resultsFor(cells)} />);
    await expect(c.locator("#TokenWaterfallAggregateChart")).toContainText("Token waterfall, averaged over 7 runs");
    const g = await readGraph(c);
    expect(g.barmode).toBe("stack");
    expect(g.hovermode).toBe("x unified");
    expect(g.traces.map((t) => t.name)).toEqual(["base", ...CATS, SPREAD]);
    expect(g.traces[0]!.x).toEqual(["baseline", "t1", "t2", "t3", "total"]);
    // identical runs: the mean is the run, the whisker collapses
    const byName = Object.fromEntries(g.traces.map((t) => [t.name, t]));
    expect(byName["accumulative_billed_tokens"]!.y).toEqual([null, null, null, null, 220_271]);
    expect(byName[SPREAD]!.y).toEqual([35_599, 35_799, 110_435, 220_271, 220_271]);
    const e = await extras(c);
    expect(e.plus).toEqual([0, 0, 0, 0, 0]);
    expect(e.minus).toEqual([0, 0, 0, 0, 0]);
    await expect(graph(c).locator(".barlayer .trace")).toHaveCount(8);
    await expect(chips(c)).toHaveText([...CATS, SPREAD]);
    expect((await drawnTitles(c)).y).toBe("mean tokens");
  });

  test("runs of unequal length: later columns average fewer runs and fade", async ({ mount }) => {
    const cells = [cell({ session_id: "long", effort: "high" }), cell({ session_id: "short", effort: "low" })];
    const c = await mount(
      <TokenWaterfallAggregateChart cells={cells} results={resultsFor(cells, (x) => (x.session_id === "short" ? { calls: [call(1)] } : {}))} />,
    );
    const g = await readGraph(c);
    expect(g.traces[0]!.x).toEqual(["baseline", "t1", "t2", "t3", "total"]);
    const e = await extras(c);
    // 2, 2, 1, 1 of 2 runs reached the column; the total is over both
    expect(e.opacity).toEqual([1, 1, 0.625, 0.625, 1]);
    // the total column spans the short run's 35,799 up to the long run's 220,271
    const spread = g.traces.find((t) => t.name === SPREAD)!;
    const mean = spread.y[4]!;
    expect(mean).toBe((35_799 + 220_271) / 2);
    expect(e.plus[4]).toBe(220_271 - mean);
    expect(e.minus[4]).toBe(mean - 35_799);
    // a column one run reached has no spread
    expect(e.plus[2]).toBe(0);
    await expect(c.locator("#TokenWaterfallAggregateChart")).toContainText("averaged over 2 runs");
  });

  // ADR 0049: two rungs are two experiments. The accumulation chart keeps them apart; this chart
  // pools them by design, so its note has to say it is pooling, and how many arms.
  test("pooling several arms is named in the note; one arm is not called a pool", async ({ mount }) => {
    const cells = sweep();
    const c = await mount(<TokenWaterfallAggregateChart cells={cells} results={resultsFor(cells)} />);
    await expect(c.locator("#TokenWaterfallAggregateChart")).toContainText("pools 7 arms (harness × model × effort rung)");
    const one = [cell({ session_id: "a", effort: "high" }), cell({ session_id: "b", effort: "high" })];
    await c.update(<TokenWaterfallAggregateChart cells={one} results={resultsFor(one)} />);
    await expect(c.locator("#TokenWaterfallAggregateChart")).toContainText("averaged over 2 runs");
    await expect(c.locator("#TokenWaterfallAggregateChart")).not.toContainText("pools");
  });

  test("an unledgered arm does not count toward the pool", async ({ mount }) => {
    const cells = [cell({ session_id: "a", effort: "high" }), cell({ session_id: "b", effort: "low", has_ledger: false })];
    const c = await mount(<TokenWaterfallAggregateChart cells={cells} results={resultsFor(cells)} />);
    await expect(c.locator("#TokenWaterfallAggregateChart")).toContainText("averaged over 1 run");
    await expect(c.locator("#TokenWaterfallAggregateChart")).not.toContainText("pools");
  });

  test("one run: the singular title", async ({ mount }) => {
    const cells = [cell()];
    const c = await mount(<TokenWaterfallAggregateChart cells={cells} results={resultsFor(cells)} />);
    await expect(c.locator("#TokenWaterfallAggregateChart")).toContainText("averaged over 1 run");
    await expect(c.locator("#TokenWaterfallAggregateChart")).not.toContainText("1 runs");
  });

  test("no ledgered session in view: a message, no plot", async ({ mount }) => {
    for (const [cells, results] of [
      [[], {}],
      [[cell({ has_ledger: false })], resultsFor([cell()])],
      [[cell()], {}],
    ] as [Cell[], Record<string, RunResult>][]) {
      const c = await mount(<TokenWaterfallAggregateChart cells={cells} results={results} />);
      await expect(c.getByText("No session with a per-call ledger in view; clear the filters, or run the evals or the replay.")).toBeVisible();
      await expect(c.locator("#TokenWaterfallAggregateChart")).toContainText("averaged over 0 runs");
      await expect(graph(c)).toHaveCount(0);
      await c.unmount();
    }
  });

  test("the spread chip hides the whisker; a category chip hides its bars", async ({ mount }) => {
    const cells = sweep();
    const c = await mount(<TokenWaterfallAggregateChart cells={cells} results={resultsFor(cells)} />);
    await chips(c).filter({ hasText: SPREAD }).click();
    await chips(c).filter({ hasText: "visible output" }).click();
    await expect
      .poll(async () => Object.fromEntries((await readGraph(c)).traces.map((t) => [t.name, t.visible])))
      .toMatchObject({ [SPREAD]: "legendonly", "visible output": "legendonly", thinking: true });
    await chips(c).filter({ hasText: SPREAD }).click();
    await expect.poll(async () => (await readGraph(c)).traces.find((t) => t.name === SPREAD)!.visible).toBe(true);
  });

  test("unified hover names the mean and how many runs it is over", async ({ mount, page }) => {
    const cells = [cell({ session_id: "long" }), cell({ session_id: "short" })];
    const c = await mount(
      <TokenWaterfallAggregateChart cells={cells} results={resultsFor(cells, (x) => (x.session_id === "short" ? { calls: [call(1)] } : {}))} />,
    );
    await readGraph(c);
    // the fourth bar trace is `thinking`; hover its t1 segment
    const seg = graph(c).locator(".barlayer .trace").nth(4).locator(".point").nth(1);
    const box = (await seg.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    const hover = graph(c).locator(".hoverlayer");
    await expect(hover).toContainText("42 mean of 2 run(s) · thinking");
    await expect(hover).toContainText("across 2 run(s)");
  });

  for (const mode of ["light", "dark"] as const) {
    test(`bars and whisker take the ${mode} tokens`, async ({ mount }) => {
      const theme = tokens.themes[mode];
      const cells = sweep();
      const c = await mount<HooksConfig>(<TokenWaterfallAggregateChart cells={cells} results={resultsFor(cells)} />, { hooksConfig: { mode } });
      const g = await readGraph(c);
      const byName = Object.fromEntries(g.traces.map((t) => [t.name, t]));
      expect(byName["new context (input + cache write)"]!.markerColor).toBe(theme.waterfall.context);
      expect(byName[SPREAD]!.markerColor).toBe(theme.muted);
      expect(g.fontColor).toBe(theme.ink);
      const fills = await graph(c)
        .locator(".barlayer .point path")
        .evaluateAll((ps) => [...new Set(ps.map((p) => getComputedStyle(p).fill))]);
      expect(fills).toContain(rgb(theme.waterfall.context));
      await expect(chips(c).last().locator("div[aria-hidden]").first()).toHaveCSS("background-color", rgb(theme.muted));
    });
  }

  test("width follows the viewport; the legend moves under the plot when narrow", async ({ mount, page }) => {
    const cells = sweep();
    await page.setViewportSize({ width: 1280, height: 900 });
    const c = await mount(<TokenWaterfallAggregateChart cells={cells} results={resultsFor(cells)} />);
    const wide = (await readGraph(c)).width;
    await page.setViewportSize({ width: 560, height: 900 });
    await expect.poll(async () => (await readGraph(c)).width).toBeLessThan(wide);
    const plot = (await graph(c).boundingBox())!;
    const legend = (await c.locator('[data-el="ChartLegend"]').boundingBox())!;
    expect(legend.y).toBeGreaterThanOrEqual(plot.y + plot.height);
  });
});
