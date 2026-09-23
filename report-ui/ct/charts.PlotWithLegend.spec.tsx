/** The chart with its legend on the right, wrapping beneath only when the row gets too narrow. */
import { expect, test } from "@playwright/experimental-ct-react";
import type { Data } from "plotly.js";
import { PlotWithLegend } from "../src/components/charts/Plot";
import { graph, readGraph } from "./charts.helpers";
import { PlotWithLegendHidden } from "./charts.stories";

const data: Data[] = [
  { type: "scatter", mode: "lines", name: "one", x: [1, 2], y: [1, 2] },
  { type: "scatter", mode: "lines", name: "two", x: [1, 2], y: [2, 1] },
];
const items = [
  { key: "one", label: "one", color: "#4f46e5" },
  { key: "two", label: "two", color: "#d97706" },
];

test.describe("PlotWithLegend", () => {
  test("draws the plot and a chip per item; Plotly's own legend stays off", async ({ mount }) => {
    const c = await mount(<PlotWithLegend data={data} layout={{ showlegend: false }} height={300} ariaLabel="pair" items={items} />);
    await readGraph(c);
    await expect(graph(c).locator(".scatterlayer .trace")).toHaveCount(2);
    await expect(c.locator('[data-el="ChartLegend"] button')).toHaveText(["one", "two"]);
    await expect(graph(c).locator(".legend")).toHaveCount(0);
  });

  test("the legend never grows past the chart's height", async ({ mount }) => {
    const many = Array.from({ length: 40 }, (_, i) => ({ key: `k${i}`, label: `k${i}`, color: "#4f46e5" }));
    const c = await mount(<PlotWithLegend data={data} layout={{}} height={240} ariaLabel="many" items={many} />);
    const legend = (await c.locator('[data-el="ChartLegend"]').boundingBox())!;
    expect(legend.height).toBeLessThanOrEqual(241);
  });

  test("onToggle is wired through to the chips", async ({ mount }) => {
    const keys: string[] = [];
    const c = await mount(
      <PlotWithLegendHidden data={data} layout={{}} height={240} ariaLabel="t" items={items} hidden={["two"]} onToggle={(k) => keys.push(k)} />,
    );
    await expect(c.locator("button", { hasText: "two" })).toHaveAttribute("aria-pressed", "false");
    await c.locator("button", { hasText: "two" }).click();
    await expect.poll(() => keys).toEqual(["two"]);
  });

  for (const [width, beside] of [
    [1200, true],
    [520, false],
  ] as const) {
    test(`at ${width}px the legend sits ${beside ? "beside" : "beneath"} the plot`, async ({ mount, page }) => {
      await page.setViewportSize({ width, height: 800 });
      const c = await mount(<PlotWithLegend data={data} layout={{}} height={260} ariaLabel="w" items={items} />);
      await readGraph(c);
      const plot = (await graph(c).boundingBox())!;
      const legend = (await c.locator('[data-el="ChartLegend"]').boundingBox())!;
      if (beside) {
        expect(legend.x).toBeGreaterThanOrEqual(plot.x + plot.width);
        expect(legend.width).toBeCloseTo(240, 0);
      } else {
        expect(legend.y).toBeGreaterThanOrEqual(plot.y + plot.height);
        expect(plot.width).toBeGreaterThanOrEqual(320);
      }
      // no horizontal page scroll either way
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
  }
});
