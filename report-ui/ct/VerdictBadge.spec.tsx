import { expect, test } from "@playwright/experimental-ct-react";
import type { HooksConfig } from "../playwright/index";
import { VerdictBadge } from "../src/components/VerdictBadge";

for (const verdict of ["pass", "fail", "error", null]) {
  test(`VerdictBadge renders ${verdict ?? "no history"}`, async ({ mount }) => {
    const c = await mount(<VerdictBadge verdict={verdict} />);
    await expect(c).toBeVisible();
    await expect(c).toContainText(verdict ?? "");
  });
}

/*
 * Tone: pass -> good, fail -> bad, anything else named -> warn, null -> outline "no history".
 * A pass keeps the quiet tint at weight 600; anything not a pass is "loud": a 20% wash, a 58%
 * border and weight 700. Colours are the bundled design tokens (light / dark).
 */
const LIGHT = { good: "rgb(4, 111, 81)", bad: "rgb(185, 28, 28)", warn: "rgb(158, 73, 8)", muted: "rgb(91, 96, 112)", line: "rgb(226, 228, 234)" };
const DARK = { good: "rgb(52, 211, 153)", bad: "rgb(248, 113, 113)", warn: "rgb(251, 191, 36)", muted: "rgb(154, 160, 176)", line: "rgb(42, 46, 58)" };

const CASES: { verdict: string | null; text: string; tone: keyof typeof LIGHT; weight: string }[] = [
  { verdict: "pass", text: "pass", tone: "good", weight: "600" },
  { verdict: "fail", text: "fail", tone: "bad", weight: "700" },
  { verdict: "error", text: "error", tone: "warn", weight: "700" },
  { verdict: "skipped", text: "skipped", tone: "warn", weight: "700" },
  { verdict: null, text: "no history", tone: "muted", weight: "600" },
];

for (const mode of ["light", "dark"] as const) {
  const palette = mode === "light" ? LIGHT : DARK;
  for (const { verdict, text, tone, weight } of CASES) {
    test(`${mode}: ${verdict ?? "null"} is ${tone} ink at weight ${weight}`, async ({ mount, page }) => {
      await mount<HooksConfig>(<VerdictBadge verdict={verdict} />, { hooksConfig: { mode } });
      const badge = page.locator("span", { hasText: text }).last();
      await expect(badge).toHaveText(text);
      await expect(badge).toHaveCSS("color", palette[tone]);
      await expect(badge).toHaveCSS("font-weight", weight);
      await expect(badge).toHaveCSS("text-transform", "uppercase");
    });
  }
}

test("null has an outline pill: transparent fill, $line border", async ({ mount, page }) => {
  await mount(<VerdictBadge verdict={null} />);
  const badge = page.locator("span", { hasText: "no history" }).last();
  await expect(badge).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
  await expect(badge).toHaveCSS("border-top-color", LIGHT.line);
});

test("a fail is washed louder than a pass", async ({ mount, page }) => {
  // computed color-mix() serialises as `color(srgb r g b / a)`; rgba() as a fallback shape
  const alpha = (c: string) => Number(/\/\s*([\d.]+)\)$/.exec(c)?.[1] ?? /rgba\([^)]*,\s*([\d.]+)\)$/.exec(c)?.[1] ?? 1);
  const c = await mount(<VerdictBadge verdict="pass" />);
  const bg = () =>
    page
      .locator("span", { hasText: /^(pass|fail)$/ })
      .last()
      .evaluate((e) => getComputedStyle(e).backgroundColor);
  const passBg = await bg();
  await c.update(<VerdictBadge verdict="fail" />);
  await expect(page.locator("span", { hasText: "fail" }).last()).toHaveCSS("font-weight", "700");
  const failBg = await bg();
  expect(alpha(failBg)).toBeGreaterThan(alpha(passBg));
});

test("every verdict is one width (min 54px) and 20px tall", async ({ mount, page }) => {
  for (const verdict of ["pass", "fail", "error", null]) {
    const c = await mount(<VerdictBadge verdict={verdict} />);
    const box = (await page
      .locator("span", { hasText: verdict ?? "no history" })
      .last()
      .boundingBox())!;
    expect(box.width).toBeGreaterThanOrEqual(54);
    expect(box.height).toBe(20);
    await c.unmount();
  }
  // the short verdicts share the 54px floor exactly, so the column has one right edge
  const widths: number[] = [];
  for (const verdict of ["pass", "fail"]) {
    const c = await mount(<VerdictBadge verdict={verdict} />);
    widths.push((await page.locator("span", { hasText: verdict }).last().boundingBox())!.width);
    await c.unmount();
  }
  expect(widths).toEqual([54, 54]);
});
