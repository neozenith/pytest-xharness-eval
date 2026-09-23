import { expect, test } from "./test";
import { ContextWindowChart } from "../src/components/charts/ContextWindowChart";
import type { HooksConfig } from "../playwright";
import { call, log, result } from "./fixtures";
import { drawnTitles, graph, readGraph, rgb, tokens } from "./charts.helpers";

const lines = log();

test.describe("ContextWindowChart", () => {
  test("per turn draws one line+markers trace: t1..tN then final, % of window", async ({ mount }) => {
    const c = await mount(<ContextWindowChart result={result()} lines={lines} mode="turn" />);
    await expect(c.locator("#ContextWindowChart")).toBeVisible();
    await expect(c.getByText("Context window consumption", { exact: false }).first()).toBeVisible();
    const g = await readGraph(c);
    expect(g.traces).toHaveLength(1);
    const [t] = g.traces;
    expect(t!.mode).toBe("lines+markers");
    expect(t!.x).toEqual(["t1", "t2", "t3", "final"]);
    expect(t!.y).toEqual([4, 8, 12, 12.06]);
    expect(g.hovermode).toBe("closest");
    expect(g.shapes).toBe(0);
    await expect(graph(c).locator(".scatterlayer .trace")).toHaveCount(1);
    await expect(graph(c).locator(".scatterlayer .point")).toHaveCount(4);
    expect((await drawnTitles(c)).y).toBe("% of 1M window");
  });

  test("per turn note states peak and final and the window size", async ({ mount }) => {
    const c = await mount(<ContextWindowChart result={result()} lines={lines} mode="turn" />);
    const note = c.locator("#ContextWindowNote");
    await expect(note).toContainText("Each point is the prompt that turn processed");
    await expect(note).toContainText("Peak");
    await expect(note).toContainText("12.0");
    await expect(note).toContainText("final");
  });

  test("per line draws an hv step over log lines 1..N with a t<n> mark at each measuring line", async ({ mount }) => {
    const c = await mount(<ContextWindowChart result={result()} lines={lines} mode="line" />);
    const g = await readGraph(c);
    expect(g.traces).toHaveLength(1);
    const [t] = g.traces;
    expect(t!.mode).toBe("lines");
    expect(t!.lineShape).toBe("hv");
    expect(t!.x).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9]);
    // the assistant records sit on lines 2, 5, 8: nothing measured before line 2
    expect(t!.y).toEqual([null, 4, 4, 4, 8, 8, 8, 12, 12]);
    expect(g.xRange).toEqual([1, 9]);
    expect(g.shapes).toBe(3);
    expect(g.annotations).toEqual(["t1", "t2", "t3"]);
    await expect(graph(c).locator(".annotation-text")).toHaveText(["t1", "t2", "t3"]);
    expect((await drawnTitles(c)).x).toBe("session-log line");
    await expect(c.locator("#ContextWindowNote")).toContainText("Per session-log line");
  });

  test("per line without the log text falls back to each turn's first record", async ({ mount }) => {
    const c = await mount(<ContextWindowChart result={result()} lines={null} mode="line" />);
    const g = await readGraph(c);
    expect(g.traces[0]!.y).toEqual([4, 4, 4, 8, 8, 8, 12, 12, 12]);
  });

  for (const mode of ["turn", "line"] as const) {
    test(`no context window (${mode}): warns, draws no plot`, async ({ mount }) => {
      const c = await mount(<ContextWindowChart result={result({ context_window: null })} lines={lines} mode={mode} />);
      const note = c.locator("#ContextWindowNote");
      await expect(note).toHaveClass(/warn/);
      await expect(note).toContainText("reported no context window");
      await expect(graph(c)).toHaveCount(0);
    });
  }

  test("hovering a point shows its percentage and token count", async ({ mount, page }) => {
    const c = await mount(<ContextWindowChart result={result()} lines={lines} mode="turn" />);
    await readGraph(c);
    const point = graph(c).locator(".scatterlayer .point").nth(1);
    const box = (await point.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    const hover = graph(c).locator(".hoverlayer .hovertext");
    await expect(hover).toBeVisible();
    await expect(hover).toContainText("8.00%");
    await expect(hover).toContainText("80,000 tokens");
  });

  for (const mode of ["light", "dark"] as const) {
    test(`line colour and ink come from the ${mode} tokens`, async ({ mount }) => {
      const theme = tokens.themes[mode];
      const c = await mount<HooksConfig>(<ContextWindowChart result={result()} lines={lines} mode="turn" />, { hooksConfig: { mode } });
      const g = await readGraph(c);
      expect(g.traces[0]!.lineColor).toBe(theme.accent);
      expect(g.fontColor).toBe(theme.ink);
      await expect(graph(c).locator(".scatterlayer .js-line")).toHaveCSS("stroke", rgb(theme.accent));
      await expect(graph(c).locator(".g-ytitle text")).toHaveCSS("fill", rgb(theme.muted));
    });
  }

  test("the plot follows the viewport width", async ({ mount, page }) => {
    await page.setViewportSize({ width: 1200, height: 800 });
    const c = await mount(<ContextWindowChart result={result()} lines={lines} mode="turn" />);
    const wide = (await readGraph(c)).width;
    await page.setViewportSize({ width: 520, height: 800 });
    await expect.poll(async () => (await readGraph(c)).width).toBeLessThan(wide - 300);
  });

  test("a single-turn run still draws its turn and final point", async ({ mount }) => {
    const c = await mount(<ContextWindowChart result={result({ calls: [call(1)], turns: 1 })} lines={lines} mode="turn" />);
    const g = await readGraph(c);
    expect(g.traces[0]!.x).toEqual(["t1", "final"]);
  });
});
