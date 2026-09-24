/** `Text`: prose that wraps; ANSI prose in colour; nothing at all for empty text. */
import { expect, test } from "./test";
import { Text } from "../src/components/records/values";
import { ANSI_TEXT, UNBROKEN } from "./fixtures";

test("wraps and keeps line breaks", async ({ mount }) => {
  const c = await mount(<Text text={"a\nb"} />);
  await expect(c.locator('[data-el="V.text"]')).toHaveCount(1);
  await expect(c.locator(".txt")).toHaveText("a\nb");
  await expect(c.locator(".txt")).toHaveCSS("word-break", "break-word");
});

test("a non-string value is stringified", async ({ mount }) => {
  const c = await mount(<Text text={42} />);
  await expect(c.locator(".txt")).toHaveText("42");
});

test("empty or missing text renders nothing", async ({ mount, page }) => {
  await mount(<Text text="" />);
  await expect(page.locator("#root")).toBeEmpty();
});

test("ANSI text becomes an Ansi block", async ({ mount }) => {
  const c = await mount(<Text text={ANSI_TEXT} />);
  await expect(c.locator('[data-el="V.ansi"]')).toHaveCount(1);
});

test("an unbroken 4,000-character token wraps inside its box", async ({ mount, page }) => {
  const c = await mount(<Text text={UNBROKEN} />);
  const height = (await c.locator(".txt").boundingBox())!.height;
  expect(height).toBeGreaterThan(40);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
});
