/**
 * The shared frame behind TurnTiersChart and OutputPerTurnChart, mounted through `UsageBars`
 * (charts.stories.tsx) because `valueOf` is a synchronous function the runner cannot proxy.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import { log, result } from "./fixtures";
import { chips, drawnTitles, graph, readGraph } from "./charts.helpers";
import { UsageBars } from "./charts.stories";

const series = [
  { key: "cache_read_tokens", label: "read", color: "#111111" },
  { key: "output_tokens", label: "out", color: "#222222" },
];
const props = { id: "MyBars", title: "My bars", yLabel: "my tokens", series, result: result(), lines: log() };

test.describe("PerTurnBars", () => {
  test("a stacked bar per series in the given order and colours, under a ChartPanel", async ({ mount }) => {
    const c = await mount(<UsageBars {...props} mode="turn" />);
    await expect(c.locator("section#MyBars")).toContainText("My bars");
    const g = await readGraph(c);
    expect(g.barmode).toBe("stack");
    expect(g.traces.map((t) => [t.name, t.markerColor])).toEqual([
      ["read", "#111111"],
      ["out", "#222222"],
    ]);
    expect(g.traces[1]!.y).toEqual([200, 400, 600]);
    expect((await drawnTitles(c)).y).toBe("my tokens");
    await expect(graph(c)).toHaveAttribute("aria-label", "My bars");
    await expect(chips(c)).toHaveText(["read", "out"]);
    await expect(graph(c).locator(".main-svg").first()).toHaveAttribute("height", "300");
  });

  test("per line: x is the measuring line, range pads one line past the last start", async ({ mount }) => {
    const c = await mount(<UsageBars {...props} mode="line" />);
    const g = await readGraph(c);
    expect(g.traces[0]!.x).toEqual([2, 5, 8]);
    expect(g.xRange).toEqual([0, 9]);
    expect(g.annotations).toEqual(["t1", "t2", "t3"]);
    // the hover still names the turn, not the line
    expect(g.traces[0]!.hovertemplate).toContain("%{customdata}");
  });

  test("hidden series survive a mode switch", async ({ mount }) => {
    const c = await mount(<UsageBars {...props} mode="turn" />);
    await chips(c).first().click();
    await expect.poll(async () => (await readGraph(c)).traces[0]!.visible).toBe("legendonly");
    await c.update(<UsageBars {...props} mode="line" />);
    await expect.poll(async () => (await readGraph(c)).traces[0]!.x).toEqual([2, 5, 8]);
    expect((await readGraph(c)).traces[0]!.visible).toBe("legendonly");
    await expect(chips(c).first()).toHaveAttribute("aria-pressed", "false");
  });

  test("a result with no calls draws empty axes rather than crashing", async ({ mount }) => {
    const c = await mount(<UsageBars {...props} result={result({ calls: [] })} mode="line" />);
    const g = await readGraph(c);
    for (const t of g.traces) expect(t.x).toEqual([]);
    expect(g.xRange).toEqual([0, 2]);
  });
});
