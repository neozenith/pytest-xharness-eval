/**
 * `El`: the component's glossary name beside its heading (ADR 0021). A quiet mono tag in `$muted`
 * that never inherits its heading's uppercase or letter-spacing.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import type { HooksConfig } from "../playwright/index";
import { El } from "../src/components/El";

test("renders the name as a tagged span", async ({ mount, page }) => {
  await mount(<El name="SessionTable" />);
  const el = page.locator("span.el");
  await expect(el).toHaveText("SessionTable");
  await expect(el).toHaveAttribute("data-el", "SessionTable");
});

test("is set small, mono and muted", async ({ mount, page }) => {
  await mount(<El name="SessionTable" />);
  const el = page.locator("span.el");
  await expect(el).toHaveCSS("font-size", "11px");
  await expect(el).toHaveCSS("font-weight", "500");
  await expect(el).toHaveCSS("color", "rgb(91, 96, 112)");
  await expect(el).toHaveCSS("margin-left", "8px");
  const family = await el.evaluate((e) => getComputedStyle(e).fontFamily);
  const mono = await el.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--xh-font-mono").trim());
  expect(family.replace(/\s/g, "")).toBe(mono.replace(/\s/g, ""));
});

test("does not inherit an uppercase, letter-spaced heading's casing", async ({ mount, page }) => {
  await mount(
    <h2 style={{ textTransform: "uppercase", letterSpacing: "0.5px" }}>
      Filters
      <El name="OverviewFilters" />
    </h2>,
  );
  const el = page.locator("span.el");
  await expect(el).toHaveCSS("text-transform", "none");
  await expect(el).toHaveCSS("letter-spacing", "normal");
  // innerText honours text-transform: the heading shouts, the tag does not
  expect(await page.locator("h2").evaluate((e) => (e as HTMLElement).innerText)).toMatch(/^FILTERS\s*OverviewFilters$/);
});

test("an empty name still renders the (empty) tag", async ({ mount, page }) => {
  await mount(<El name="" />);
  await expect(page.locator('span.el[data-el=""]')).toHaveCount(1);
});

test("dark mode: muted in the dark palette", async ({ mount, page }) => {
  await mount<HooksConfig>(<El name="NavSidebar" />, { hooksConfig: { mode: "dark" } });
  await expect(page.locator("span.el")).toHaveCSS("color", "rgb(154, 160, 176)");
});
