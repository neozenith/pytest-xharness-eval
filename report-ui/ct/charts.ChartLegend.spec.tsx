/** The HTML legend column every chart shares: chips that toggle series, a fading edge when clipped. */
import { expect, test } from "@playwright/experimental-ct-react";
import { ChartLegend } from "../src/components/charts/Plot";
import type { HooksConfig } from "../playwright";
import { rgb, tokens } from "./charts.helpers";
import { LegendWithHidden } from "./charts.stories";

const items = [
  { key: "a", label: "alpha", color: "#4f46e5" },
  { key: "b", label: "beta", color: "#d97706" },
  { key: "c", label: "gamma", color: "#059669" },
];
const swatch = (chip: import("@playwright/test").Locator) => chip.locator("div[aria-hidden]").first();

test.describe("ChartLegend", () => {
  test("one chip per item, in order, each with its colour swatch", async ({ mount }) => {
    const m = await mount(<ChartLegend items={items} />);
    const c = m.locator('[data-el="ChartLegend"]');
    const chips = c.locator("button");
    await expect(chips).toHaveText(["alpha", "beta", "gamma"]);
    for (const [i, item] of items.entries()) {
      await expect(swatch(chips.nth(i))).toHaveCSS("background-color", rgb(item.color));
      await expect(chips.nth(i)).toHaveAttribute("aria-pressed", "true");
    }
  });

  test("no items renders nothing", async ({ mount, page }) => {
    await mount(<ChartLegend items={[]} />);
    await expect(page.locator('[data-el="ChartLegend"]')).toHaveCount(0);
  });

  test("a hidden key shows its chip off: outline swatch, unpressed, muted text", async ({ mount }) => {
    const m = await mount(<LegendWithHidden items={items} hidden={["b"]} />);
    const c = m.locator('[data-el="ChartLegend"]');
    const off = c.locator("button").nth(1);
    await expect(off).toHaveAttribute("aria-pressed", "false");
    await expect(swatch(off)).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
    await expect(swatch(off)).toHaveCSS(
      "box-shadow",
      new RegExp(`${rgb(items[1]!.color).replace(/[()]/g, "\\$&")}.*inset|inset.*${rgb(items[1]!.color).replace(/[()]/g, "\\$&")}`),
    );
    const onColor = await c
      .locator("button")
      .nth(0)
      .locator("span")
      .first()
      .evaluate((el) => getComputedStyle(el).color);
    const offColor = await off
      .locator("span")
      .first()
      .evaluate((el) => getComputedStyle(el).color);
    expect(offColor).not.toBe(onColor);
  });

  test("clicking a chip calls onToggle with its key", async ({ mount }) => {
    const keys: string[] = [];
    const m = await mount(<ChartLegend items={items} onToggle={(k) => keys.push(k)} />);
    const c = m.locator('[data-el="ChartLegend"]');
    await c.locator("button", { hasText: "gamma" }).click();
    await c.locator("button", { hasText: "alpha" }).click();
    await expect.poll(() => keys).toEqual(["c", "a"]);
    await expect(c.locator("button").first()).toHaveAttribute("title", "toggle alpha");
  });

  test("without onToggle the chips are inert and carry no toggle title", async ({ mount }) => {
    const m = await mount(<ChartLegend items={items} />);
    const c = m.locator('[data-el="ChartLegend"]');
    await expect(c.locator("button").first()).not.toHaveAttribute("title", /toggle/);
  });

  test("a legend taller than maxHeight scrolls and fades only the clipped edge", async ({ mount }) => {
    const many = Array.from({ length: 30 }, (_, i) => ({ key: `k${i}`, label: `series number ${i}`, color: "#4f46e5" }));
    const m = await mount(<ChartLegend items={many} maxHeight={200} />);
    const c = m.locator('[data-el="ChartLegend"]');
    const box = (await c.boundingBox())!;
    expect(box.height).toBeLessThanOrEqual(201);
    const scrolls = await c.evaluate((el) => el.scrollHeight > el.clientHeight);
    expect(scrolls).toBe(true);
    const mask = () => c.evaluate((el) => (el as HTMLElement).style.cssText);
    // at the top: only the bottom edge fades
    await expect.poll(mask).toMatch(/black 0px.*black calc\(100% - 28px\)/);
    await c.evaluate((el) => el.scrollTo({ top: el.scrollHeight }));
    await expect.poll(mask).toMatch(/black 28px.*black calc\(100% [-+] 0px\)/);
  });

  test("a legend that fits fades no edge", async ({ mount }) => {
    const m = await mount(<ChartLegend items={items} maxHeight={400} />);
    const c = m.locator('[data-el="ChartLegend"]');
    const mask = await c.evaluate((el) => (el as HTMLElement).style.cssText);
    expect(mask).toMatch(/black 0px.*black calc\(100% [-+] 0px\)/);
  });

  for (const mode of ["light", "dark"] as const) {
    test(`label ink follows the ${mode} theme`, async ({ mount }) => {
      const m = await mount<HooksConfig>(<ChartLegend items={items} />, { hooksConfig: { mode } });
      const c = m.locator('[data-el="ChartLegend"]');
      await expect(c.locator("button").first().locator("span").first()).toHaveCSS("color", rgb(tokens.themes[mode].ink));
    });
  }
});
