/** The one Plotly mount point: draws what it is handed, reserves its height, redraws on new data. */
import { expect, test } from "@playwright/experimental-ct-react";
import type { Data, Layout } from "plotly.js";
import { Plot } from "../src/components/charts/Plot";
import { graph, readGraph } from "./charts.helpers";

const line: Data[] = [{ type: "scatter", mode: "lines+markers", name: "a", x: [1, 2, 3], y: [3, 1, 2] }];
const bars: Data[] = [
  { type: "bar", name: "p", x: ["t1", "t2"], y: [1, 2] },
  { type: "bar", name: "q", x: ["t1", "t2"], y: [3, 4] },
];
const layout: Partial<Layout> = { xaxis: { title: { text: "the x" } }, yaxis: { title: { text: "the y" } } };

test.describe("Plot", () => {
  test("draws an SVG of the traces it is handed, labelled for assistive tech", async ({ mount }) => {
    const c0 = await mount(<Plot data={line} layout={layout} height={260} ariaLabel="a line" />);
    const c = graph(c0);
    await expect(c).toHaveAttribute("role", "img");
    await expect(c).toHaveAttribute("aria-label", "a line");
    await expect(c.locator(".main-svg").first()).toBeVisible();
    await expect(c.locator(".scatterlayer .trace")).toHaveCount(1);
    await expect(c.locator(".scatterlayer .point")).toHaveCount(3);
    await expect(c.locator(".g-xtitle text")).toHaveText("the x");
    await expect(c.locator(".g-ytitle text")).toHaveText("the y");
  });

  test("reserves exactly its height, and hides the mode bar", async ({ mount }) => {
    const c0 = await mount(<Plot data={line} layout={{}} height={333} ariaLabel="h" />);
    const c = graph(c0);
    await expect(c.locator(".main-svg").first()).toBeVisible();
    expect((await c.boundingBox())!.height).toBeCloseTo(333, 0);
    expect(await c.locator(".main-svg").first().getAttribute("height")).toBe("333");
    await expect(c.locator(".modebar")).toHaveCount(0);
  });

  test("new data redraws in place (Plotly.react), not a second graph", async ({ mount, page }) => {
    const c0 = await mount(<Plot data={line} layout={{}} height={200} ariaLabel="x" />);
    const c = graph(c0);
    await expect(c.locator(".scatterlayer .trace")).toHaveCount(1);
    await c0.update(<Plot data={bars} layout={{ barmode: "stack" }} height={200} ariaLabel="x" />);
    await expect(c.locator(".barlayer .trace")).toHaveCount(2);
    await expect(c.locator(".scatterlayer .trace")).toHaveCount(0);
    await expect(page.locator(".main-svg").first()).toBeVisible();
    await expect(graph(page)).toHaveCount(1);
    expect((await readGraph(page)).barmode).toBe("stack");
  });

  test("a height change resizes the drawn SVG", async ({ mount }) => {
    const c0 = await mount(<Plot data={line} layout={{}} height={200} ariaLabel="x" />);
    const c = graph(c0);
    await expect(c.locator(".main-svg").first()).toHaveAttribute("height", "200");
    await c0.update(<Plot data={line} layout={{}} height={380} ariaLabel="x" />);
    await expect(c.locator(".main-svg").first()).toHaveAttribute("height", "380");
  });

  test("responsive: fills its container at two viewport widths", async ({ mount, page }) => {
    await page.setViewportSize({ width: 1100, height: 700 });
    const c0 = await mount(<Plot data={line} layout={{ autosize: true }} height={240} ariaLabel="x" />);
    const c = graph(c0);
    await expect(c.locator(".main-svg").first()).toBeVisible();
    const wide = Number(await c.locator(".main-svg").first().getAttribute("width"));
    expect(wide).toBeGreaterThan(900);
    await page.setViewportSize({ width: 500, height: 700 });
    await expect.poll(async () => Number(await c.locator(".main-svg").first().getAttribute("width"))).toBeLessThan(520);
  });

  test("an empty data list still draws empty axes", async ({ mount }) => {
    const c0 = await mount(<Plot data={[]} layout={{}} height={200} ariaLabel="empty" />);
    const c = graph(c0);
    await expect(c.locator(".main-svg").first()).toBeVisible();
    await expect(c.locator(".scatterlayer .trace, .barlayer .trace")).toHaveCount(0);
  });

  test("unmounting purges the graph", async ({ mount, page }) => {
    const c0 = await mount(<Plot data={line} layout={{}} height={200} ariaLabel="x" />);
    const c = graph(c0);
    await expect(c.locator(".main-svg").first()).toBeVisible();
    await c0.unmount();
    await expect(page.locator(".main-svg")).toHaveCount(0);
  });
});
