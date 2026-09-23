/**
 * `Card` and its parts (src/components/ui/card.tsx): a `<section>` surface on `--xh-panel` with a
 * hairline and a shadow, a `<header>`, an `<h2>` title in ink, a `<p>` description in muted, and
 * a padded content column.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import type { Locator } from "@playwright/test";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../src/components/ui/card";
import type { HooksConfig } from "../playwright/index";

const resolved = (el: Locator, token: string) =>
  el.evaluate((_, t) => {
    const probe = document.createElement("span");
    probe.style.color = `var(--xh-${t})`;
    document.body.append(probe);
    const out = getComputedStyle(probe).color;
    probe.remove();
    return out;
  }, token);

/** WCAG contrast of the element's text over every ancestor background, composited on a canvas. */
const contrast = (el: Locator) =>
  el.evaluate((node) => {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 1;
    const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
    const paint = (colour: string) => {
      ctx.fillStyle = colour;
      ctx.fillRect(0, 0, 1, 1);
    };
    const chain: string[] = [];
    for (let n: Element | null = node; n; n = n.parentElement) chain.push(getComputedStyle(n).backgroundColor);
    paint("#ffffff");
    for (const bg of chain.reverse()) paint(bg);
    const [br, bgc, bb] = ctx.getImageData(0, 0, 1, 1).data;
    paint(getComputedStyle(node).color);
    const [fr, fg, fb] = ctx.getImageData(0, 0, 1, 1).data;
    const lum = (r = 0, g = 0, b = 0) =>
      [r, g, b]
        .map((v) => v / 255)
        .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
        .reduce((acc, c, i) => acc + c * [0.2126, 0.7152, 0.0722][i]!, 0);
    const [a, b] = [lum(fr, fg, fb), lum(br, bgc, bb)].sort((x, y) => y - x);
    return (a! + 0.05) / (b! + 0.05);
  });

const full = (
  <Card id="Panel" aria-labelledby="PanelTitle">
    <CardHeader>
      <CardTitle id="PanelTitle">Cost by tier</CardTitle>
      <CardDescription>What each token tier cost across the sweep.</CardDescription>
    </CardHeader>
    <CardContent>
      <span>body</span>
    </CardContent>
  </Card>
);

test("Card renders semantic section > header > h2 + p, and a content column", async ({ page, mount }) => {
  await mount(full);
  const section = page.locator("section#Panel");
  await expect(section).toBeVisible();
  await expect(section.locator("> header > h2")).toHaveText("Cost by tier");
  await expect(section.locator("> header > p")).toHaveText("What each token tier cost across the sweep.");
  await expect(page.getByRole("heading", { level: 2, name: "Cost by tier" })).toBeVisible();
  // A labelled section is a landmark region named by its title.
  await expect(page.getByRole("region", { name: "Cost by tier" })).toBeVisible();
  await expect(section.getByText("body")).toBeVisible();
});

test("Card frame: panel fill, 1px line border, 12px radius, 20px vertical padding, 16px gap, shadow", async ({ page, mount }) => {
  await mount(full);
  const s = page.locator("section#Panel");
  await expect(s).toHaveCSS("background-color", await resolved(s, "panel"));
  await expect(s).toHaveCSS("border-top-color", await resolved(s, "line"));
  await expect(s).toHaveCSS("border-top-width", "1px");
  await expect(s).toHaveCSS("border-top-left-radius", "12px");
  await expect(s).toHaveCSS("padding-top", "20px");
  await expect(s).toHaveCSS("padding-bottom", "20px");
  await expect(s).toHaveCSS("row-gap", "16px");
  await expect(s).toHaveCSS("flex-direction", "column");
  expect(await s.evaluate((n) => getComputedStyle(n).boxShadow)).not.toBe("none");
});

test("Card settles fully opaque after its enter transition", async ({ page, mount }) => {
  await mount(full);
  await expect(page.locator("section#Panel")).toHaveCSS("opacity", "1");
});

test("CardHeader and CardContent inset their children 20px", async ({ page, mount }) => {
  await mount(full);
  const header = page.locator("section#Panel > header");
  await expect(header).toHaveCSS("padding-left", "20px");
  await expect(header).toHaveCSS("padding-right", "20px");
  await expect(header).toHaveCSS("row-gap", "3px");
  const content = page.getByText("body").locator("..");
  await expect(content).toHaveCSS("padding-left", "20px");
  await expect(content).toHaveCSS("flex-direction", "column");
});

test("CardTitle and CardDescription typography", async ({ page, mount }) => {
  await mount(full);
  const title = page.getByRole("heading", { name: "Cost by tier" });
  await expect(title).toHaveCSS("font-size", "15px");
  await expect(title).toHaveCSS("font-weight", "600");
  await expect(title).toHaveCSS("margin-top", "0px");
  const desc = page.locator("section#Panel p");
  await expect(desc).toHaveCSS("font-size", "12.5px");
  await expect(desc).toHaveCSS("margin-top", "0px");
  // 78ch cap, measured rather than read back, since the unit is resolved to px.
  const [max, ch] = await desc.evaluate((n) => {
    const probe = document.createElement("span");
    probe.style.cssText = "position:absolute;visibility:hidden;width:78ch;font:inherit";
    n.append(probe);
    const w = probe.getBoundingClientRect().width;
    probe.remove();
    return [Number.parseFloat(getComputedStyle(n).maxWidth), w];
  });
  expect(max).toBeCloseTo(ch, 0);
});

for (const mode of ["light", "dark"] as const) {
  test(`Card colours come from the ${mode} tokens and its text clears AA`, async ({ page, mount }) => {
    await mount(full, { hooksConfig: { mode } satisfies HooksConfig });
    const s = page.locator("section#Panel");
    await expect(s).toHaveCSS("background-color", mode === "light" ? "rgb(255, 255, 255)" : "rgb(23, 26, 35)");
    const title = page.getByRole("heading", { name: "Cost by tier" });
    const desc = page.locator("section#Panel p");
    await expect(title).toHaveCSS("color", await resolved(title, "ink"));
    await expect(desc).toHaveCSS("color", await resolved(desc, "muted"));
    expect(await contrast(title)).toBeGreaterThanOrEqual(4.5);
    expect(await contrast(desc)).toBeGreaterThanOrEqual(4.5);
  });
}

test("Card does not slide in under prefers-reduced-motion", async ({ page, mount }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mount(full);
  const d = await page.locator("section#Panel").evaluate((n) => getComputedStyle(n).transitionDuration);
  expect(d.split(",").every((x) => Number.parseFloat(x) < 0.001)).toBe(true);
});
