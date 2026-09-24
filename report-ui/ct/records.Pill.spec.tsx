/**
 * `Pill`: the category-coloured kind chip in a card's head. Its colour is the
 * `--xh-category-<category>` token with the catalogue's value behind it, its ink the same in
 * both themes, and its full kind is kept in the tooltip even when a narrow card elides it.
 */
import { expect, test } from "./test";
import { Pill } from "../src/components/records/RecordCard";
import { CATEGORIES, KINDS, categoryOf } from "../src/lib/records";
import type { HooksConfig } from "../playwright/index";

const rgb = (hex: string): string => {
  const n = parseInt(hex.slice(1), 16);
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
};

for (const category of Object.keys(CATEGORIES)) {
  const kind = Object.entries(KINDS).find(([, c]) => c === category)?.[0] ?? "claude/never-seen";
  test(`${category}: ${kind} is painted ${CATEGORIES[category]}`, async ({ mount }) => {
    const c = await mount(<Pill kind={kind} />);
    await expect(c.locator(".pill")).toHaveText(kind);
    await expect(c.locator(".pill")).toHaveAttribute("title", `${kind} · ${categoryOf(kind)}`);
    await expect(c.locator(".pill")).toHaveCSS("background-color", rgb(CATEGORIES[category]!));
    await expect(c.locator(".pill")).toHaveCSS("color", "rgb(255, 255, 255)");
  });
}

test("an unseen kind falls back by prefix, then to unknown", async ({ mount }) => {
  const c = await mount(<Pill kind="claude/attachment/brand_new" />);
  await expect(c.locator(".pill")).toHaveAttribute("title", "claude/attachment/brand_new · harness_meta");
  await expect(c.locator(".pill")).toHaveCSS("background-color", rgb(CATEGORIES.harness_meta!));
  await c.update(<Pill kind="gemini/whatever" />);
  await expect(c.locator(".pill")).toHaveAttribute("title", "gemini/whatever · unknown");
  await expect(c.locator(".pill")).toHaveCSS("background-color", rgb(CATEGORIES.unknown!));
});

test("the token wins over the catalogue literal", async ({ mount, page }) => {
  const c = await mount(<Pill kind="codex/event_msg/token_count" />);
  await page.evaluate(() => document.documentElement.style.setProperty("--xh-category-usage", "rgb(10, 20, 30)"));
  await expect(c.locator(".pill")).toHaveCSS("background-color", "rgb(10, 20, 30)");
});

test("dark mode keeps the category colour and the white ink", async ({ mount }) => {
  const c = await mount<HooksConfig>(<Pill kind="claude/assistant/thinking" />, { hooksConfig: { mode: "dark" } });
  await expect(c.locator(".pill")).toHaveCSS("background-color", rgb(CATEGORIES.thinking!));
  await expect(c.locator(".pill")).toHaveCSS("color", "rgb(255, 255, 255)");
});

test("the kind never wraps inside the chip", async ({ mount }) => {
  const c = await mount(<Pill kind="codex/event_msg/item_completed/UserMessage/injected" />);
  await expect(c.locator(".pill")).toHaveCSS("white-space", "nowrap");
});
