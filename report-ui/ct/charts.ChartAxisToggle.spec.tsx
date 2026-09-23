/** The per-turn / per-line switch the four session charts share. */
import { expect, test } from "@playwright/experimental-ct-react";
import type { Page } from "@playwright/test";
import { ChartAxisToggle } from "../src/components/charts/ChartAxisToggle";
import type { HooksConfig } from "../playwright";
import type { AxisMode } from "../src/lib/series";

/** The component's own root (the mount locator is the provider wrapper around it). */
const root = (page: Page) => page.locator("#ChartAxisToggle");
const segment = (page: Page, name: "per turn" | "per session-log line") => root(page).getByRole("button", { name, exact: true });

test.describe("ChartAxisToggle", () => {
  test("renders its label, both segments and the gloss", async ({ mount, page }) => {
    await mount(<ChartAxisToggle mode="turn" onChange={() => {}} />);
    const c = root(page);
    await expect(c).toHaveAttribute("data-el", "ChartAxisToggle");
    await expect(c).toHaveAttribute("title", "x-axis of the four per-turn charts");
    await expect(c).toContainText("Chart x-axis");
    await expect(c.locator(".el")).toHaveText("ChartAxisToggle");
    await expect(c.getByRole("group", { name: "chart x-axis" })).toBeVisible();
    await expect(segment(page, "per turn")).toBeVisible();
    await expect(segment(page, "per session-log line")).toBeVisible();
    await expect(c).toContainText("turn starts are marked");
  });

  for (const mode of ["turn", "line"] as const) {
    test(`marks the ${mode} segment as selected`, async ({ mount, page }) => {
      await mount(<ChartAxisToggle mode={mode} onChange={() => {}} />);
      const on = root(page).locator('[data-state="on"]');
      await expect(on).toHaveCount(1);
      await expect(on).toHaveText(mode === "turn" ? "per turn" : "per session-log line");
    });
  }

  test("clicking the other segment calls onChange with its mode", async ({ mount, page }) => {
    const calls: AxisMode[] = [];
    await mount(<ChartAxisToggle mode="turn" onChange={(m) => calls.push(m)} />);
    await segment(page, "per session-log line").click();
    await expect.poll(() => calls).toEqual(["line"]);
  });

  test("clicking the selected segment reports nothing; the other one reports its mode", async ({ mount, page }) => {
    const calls: AxisMode[] = [];
    await mount(<ChartAxisToggle mode="line" onChange={(m) => calls.push(m)} />);
    await segment(page, "per session-log line").click();
    await segment(page, "per turn").click();
    await expect.poll(() => calls).toEqual(["turn"]);
  });

  test("is controlled: the selection follows the mode prop", async ({ mount, page }) => {
    const c = await mount(<ChartAxisToggle mode="turn" onChange={() => {}} />);
    await c.update(<ChartAxisToggle mode="line" onChange={() => {}} />);
    await expect(root(page).locator('[data-state="on"]')).toHaveText("per session-log line");
  });

  test("keyboard: a focused segment switches on Space", async ({ mount, page }) => {
    const calls: AxisMode[] = [];
    await mount(<ChartAxisToggle mode="turn" onChange={(m) => calls.push(m)} />);
    await segment(page, "per session-log line").focus();
    await page.keyboard.press("Space");
    await expect.poll(() => calls).toEqual(["line"]);
  });

  for (const mode of ["light", "dark"] as const) {
    test(`${mode}: the selected segment is painted differently from the other`, async ({ mount, page }) => {
      await mount<HooksConfig>(<ChartAxisToggle mode="turn" onChange={() => {}} />, { hooksConfig: { mode } });
      const bg = (state: string) =>
        root(page)
          .locator(`[data-state="${state}"]`)
          .evaluate((el) => getComputedStyle(el).backgroundColor);
      expect(await bg("on")).not.toBe(await bg("off"));
    });
  }

  test("wraps at a narrow width instead of overflowing", async ({ mount, page }) => {
    await page.setViewportSize({ width: 360, height: 700 });
    await mount(<ChartAxisToggle mode="turn" onChange={() => {}} />);
    const c = root(page);
    expect(await c.evaluate((el) => el.scrollWidth - el.clientWidth)).toBeLessThanOrEqual(1);
    expect((await c.boundingBox())!.width).toBeLessThanOrEqual(360);
    // the gloss drops to its own row beneath the control
    const group = (await c.getByRole("group").boundingBox())!;
    const gloss = (await c.getByText("turn starts are marked", { exact: false }).boundingBox())!;
    expect(gloss.y).toBeGreaterThanOrEqual(group.y + group.height - 1);
  });
});
