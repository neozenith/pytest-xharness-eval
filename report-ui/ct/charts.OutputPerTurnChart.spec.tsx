/** Thinking and visible output stacked per turn, or at each turn's measuring log line. */
import { expect, test } from "./test";
import { OutputPerTurnChart } from "../src/components/charts/OutputPerTurnChart";
import type { HooksConfig } from "../playwright";
import { call, log, result, usage } from "./fixtures";
import { chips, drawnTitles, graph, readGraph, rgb, tokens } from "./charts.helpers";

const lines = log();

test.describe("OutputPerTurnChart", () => {
  test("per turn: thinking under visible output (output_tokens minus reasoning)", async ({ mount }) => {
    const c = await mount(<OutputPerTurnChart result={result()} lines={lines} mode="turn" />);
    await expect(c.locator("#OutputPerTurnChart")).toContainText("Output and thinking");
    const g = await readGraph(c);
    expect(g.barmode).toBe("stack");
    expect(g.traces.map((t) => t.name)).toEqual(["thinking", "visible output"]);
    expect(g.traces[0]!.x).toEqual(["t1", "t2", "t3"]);
    expect(g.traces[0]!.y).toEqual([42, 42, 42]);
    expect(g.traces[1]!.y).toEqual([158, 358, 558]);
    await expect(graph(c).locator(".barlayer .trace")).toHaveCount(2);
    const t = await drawnTitles(c);
    expect(t.x).toBe("turn");
    expect(t.y).toBe("output_tokens");
    await expect(chips(c)).toHaveText(["thinking", "visible output"]);
  });

  test("no reasoning: the thinking segment is absent, not zero", async ({ mount }) => {
    const r = result({ calls: [call(1, { usage: usage({ reasoning_tokens: 0, output_tokens: 50 }) })] });
    const c = await mount(<OutputPerTurnChart result={r} lines={lines} mode="turn" />);
    const g = await readGraph(c);
    expect(g.traces[0]!.y).toEqual([null]);
    expect(g.traces[1]!.y).toEqual([50]);
  });

  test("reasoning reported above output never draws a negative visible segment", async ({ mount }) => {
    const r = result({ calls: [call(1, { usage: usage({ reasoning_tokens: 500, output_tokens: 100 }) })] });
    const c = await mount(<OutputPerTurnChart result={r} lines={lines} mode="turn" />);
    const g = await readGraph(c);
    expect(g.traces[1]!.y).toEqual([null]);
  });

  test("per line: bars at the measuring lines with t<n> marks", async ({ mount }) => {
    const c = await mount(<OutputPerTurnChart result={result()} lines={lines} mode="line" />);
    const g = await readGraph(c);
    expect(g.traces[0]!.x).toEqual([2, 5, 8]);
    expect(g.annotations).toEqual(["t1", "t2", "t3"]);
    expect((await drawnTitles(c)).x).toBe("session-log line");
  });

  test("hover names the value, series and turn", async ({ mount, page }) => {
    const c = await mount(<OutputPerTurnChart result={result()} lines={lines} mode="turn" />);
    await readGraph(c);
    const bar = graph(c).locator(".barlayer .trace").nth(1).locator(".point").nth(2);
    const box = (await bar.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await expect(graph(c).locator(".hoverlayer")).toContainText("558 · visible output (t3)");
  });

  test("a chip hides thinking", async ({ mount }) => {
    const c = await mount(<OutputPerTurnChart result={result()} lines={lines} mode="turn" />);
    await chips(c).first().click();
    await expect(chips(c).first()).toHaveAttribute("aria-pressed", "false");
    await expect.poll(async () => (await readGraph(c)).traces.map((t) => t.visible)).toEqual(["legendonly", true]);
  });

  for (const mode of ["light", "dark"] as const) {
    test(`colours are the ${mode} waterfall thinking/output tokens`, async ({ mount }) => {
      const w = tokens.themes[mode].waterfall;
      const c = await mount<HooksConfig>(<OutputPerTurnChart result={result()} lines={lines} mode="turn" />, { hooksConfig: { mode } });
      const g = await readGraph(c);
      expect(g.traces.map((t) => t.markerColor)).toEqual([w.thinking, w.output]);
      await expect(graph(c).locator(".barlayer .trace").first().locator(".point path").first()).toHaveCSS("fill", rgb(w.thinking));
    });
  }

  test("two viewport widths: the plot narrows with the page", async ({ mount, page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    const c = await mount(<OutputPerTurnChart result={result()} lines={lines} mode="turn" />);
    const wide = (await readGraph(c)).width;
    await page.setViewportSize({ width: 600, height: 800 });
    await expect.poll(async () => (await readGraph(c)).width).toBeLessThan(wide - 300);
  });
});
