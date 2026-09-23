/** The four billing tiers stacked per turn, or at each turn's measuring log line. */
import { expect, test } from "@playwright/experimental-ct-react";
import { TurnTiersChart } from "../src/components/charts/TurnTiersChart";
import type { HooksConfig } from "../playwright";
import { call, log, result, usage } from "./fixtures";
import { chips, drawnTitles, graph, readGraph, rgb, tokens } from "./charts.helpers";

const lines = log();
const TIERS = ["cache read", "cache write", "input (uncached)", "output"];

test.describe("TurnTiersChart", () => {
  test("per turn: four stacked tiers over t1..tN", async ({ mount }) => {
    const c = await mount(<TurnTiersChart result={result()} lines={lines} mode="turn" />);
    await expect(c.locator("#TurnTiersChart")).toContainText("Billing tiers");
    const g = await readGraph(c);
    expect(g.barmode).toBe("stack");
    expect(g.traces.map((t) => t.name)).toEqual(TIERS);
    for (const t of g.traces) expect(t.x).toEqual(["t1", "t2", "t3"]);
    expect(g.traces[0]!.y).toEqual([35_000, 70_000, 105_000]);
    expect(g.traces[1]!.y).toEqual([4_234, 4_234, 4_234]);
    expect(g.traces[2]!.y).toEqual([2, 2, 2]);
    expect(g.traces[3]!.y).toEqual([200, 400, 600]);
    expect(g.shapes).toBe(0);
    await expect(graph(c).locator(".barlayer .trace")).toHaveCount(4);
    await expect(graph(c).locator(".barlayer .point")).toHaveCount(12);
    const t = await drawnTitles(c);
    expect(t.x).toBe("turn");
    expect(t.y).toBe("tokens");
    await expect(chips(c)).toHaveText(TIERS);
  });

  test("a zero tier is left out of the stack (null, not a zero-height bar)", async ({ mount }) => {
    const r = result({ calls: [call(1, { usage: usage({ input_tokens: 0 }) }), call(2)] });
    const c = await mount(<TurnTiersChart result={r} lines={lines} mode="turn" />);
    const g = await readGraph(c);
    expect(g.traces[2]!.y).toEqual([null, 2]);
  });

  test("per line: bars at each turn's measuring line, turn starts marked", async ({ mount }) => {
    const c = await mount(<TurnTiersChart result={result()} lines={lines} mode="line" />);
    const g = await readGraph(c);
    for (const t of g.traces) expect(t.x).toEqual([2, 5, 8]);
    expect(g.xRange).toEqual([0, 9]);
    expect(g.annotations).toEqual(["t1", "t2", "t3"]);
    expect(g.shapes).toBe(3);
    await expect(graph(c).locator(".annotation-text")).toHaveText(["t1", "t2", "t3"]);
    expect((await drawnTitles(c)).x).toBe("session-log line");
  });

  test("per line without the log text: each turn's first record", async ({ mount }) => {
    const c = await mount(<TurnTiersChart result={result()} lines={null} mode="line" />);
    const g = await readGraph(c);
    expect(g.traces[0]!.x).toEqual([1, 4, 7]);
  });

  test("switching mode redraws the axis in place", async ({ mount }) => {
    const c = await mount(<TurnTiersChart result={result()} lines={lines} mode="turn" />);
    expect((await readGraph(c)).traces[0]!.x).toEqual(["t1", "t2", "t3"]);
    await c.update(<TurnTiersChart result={result()} lines={lines} mode="line" />);
    await expect.poll(async () => (await readGraph(c)).traces[0]!.x).toEqual([2, 5, 8]);
    await c.update(<TurnTiersChart result={result()} lines={lines} mode="turn" />);
    await expect.poll(async () => (await readGraph(c)).shapes).toBe(0);
  });

  test("hover names the value, the tier and the turn", async ({ mount, page }) => {
    const c = await mount(<TurnTiersChart result={result()} lines={lines} mode="line" />);
    await readGraph(c);
    const bar = graph(c).locator(".barlayer .trace").first().locator(".point").nth(1);
    const box = (await bar.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await expect(graph(c).locator(".hoverlayer")).toContainText("70,000 · cache read (t2)");
  });

  test("a chip hides its tier", async ({ mount }) => {
    const c = await mount(<TurnTiersChart result={result()} lines={lines} mode="turn" />);
    await chips(c).filter({ hasText: "cache write" }).click();
    await expect.poll(async () => (await readGraph(c)).traces.map((t) => t.visible)).toEqual([true, "legendonly", true, true]);
  });

  for (const mode of ["light", "dark"] as const) {
    test(`tiers take series 1-4 of the ${mode} tokens`, async ({ mount }) => {
      const s = tokens.themes[mode].series;
      const c = await mount<HooksConfig>(<TurnTiersChart result={result()} lines={lines} mode="turn" />, { hooksConfig: { mode } });
      const g = await readGraph(c);
      expect(g.traces.map((t) => t.markerColor)).toEqual(s.slice(0, 4));
      const fills = await graph(c)
        .locator(".barlayer .point path")
        .evaluateAll((ps) => [...new Set(ps.map((p) => getComputedStyle(p).fill))]);
      expect(fills.sort()).toEqual(s.slice(0, 4).map(rgb).sort());
    });
  }

  // `~s` is d3's SI format: a billion tokens read "1G", giga, on a token axis.
  test("a billion-token axis reads B, never SI giga", async ({ mount }) => {
    const r = result({
      calls: [call(1, { usage: usage({ cache_read_tokens: 1_200_000_000 }) }), call(2, { usage: usage({ cache_read_tokens: 2_400_000_000 }) })],
    });
    const c = await mount(<TurnTiersChart result={r} lines={lines} mode="turn" />);
    await readGraph(c);
    const ticks = await graph(c).locator(".ytick text").allTextContents();
    expect(ticks.some((t) => /\dB$/.test(t))).toBe(true);
    expect(ticks.filter((t) => /G$/.test(t))).toEqual([]);
  });

  test("a legend chip toggles from the keyboard", async ({ mount, page }) => {
    const c = await mount(<TurnTiersChart result={result()} lines={lines} mode="turn" />);
    await readGraph(c);
    await chips(c).first().focus();
    await page.keyboard.press("Space");
    await expect(chips(c).first()).toHaveAttribute("aria-pressed", "false");
    await expect.poll(async () => (await readGraph(c)).traces[0]!.visible).toBe("legendonly");
    await page.keyboard.press("Enter");
    await expect(chips(c).first()).toHaveAttribute("aria-pressed", "true");
  });

  test("two viewport widths: the plot narrows with the page", async ({ mount, page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    const c = await mount(<TurnTiersChart result={result()} lines={lines} mode="turn" />);
    const wide = (await readGraph(c)).width;
    await page.setViewportSize({ width: 640, height: 800 });
    await expect.poll(async () => (await readGraph(c)).width).toBeLessThan(wide - 300);
  });
});
