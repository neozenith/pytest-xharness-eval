/**
 * FinalMessagePanel: the agent's final message verbatim in a scrolling `pre`, or `(empty)`.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import type { Locator } from "@playwright/test";
import { FinalMessagePanel } from "../src/components/panels/FinalMessagePanel";
import { PHONE, pageOverflowX, resolveColour } from "./panels.data";

const pre = (c: Locator) => c.locator("#FinalMessage");

test("the final text, under the panel's heading and glossary name", async ({ mount }) => {
  const c = await mount(<FinalMessagePanel text="Both gates pass clean." />);
  await expect(pre(c)).toHaveText("Both gates pass clean.");
  await expect(c.getByText(/^Final message/)).toBeVisible();
  await expect(c.locator('.el[data-el="FinalMessagePanel"]')).toHaveText("FinalMessagePanel");
  await expect(c.locator("#FinalMessagePanel")).toBeVisible();
});

for (const [name, text] of [
  ["empty string", ""],
  ["null", null],
  ["undefined", undefined],
] as const) {
  test(`${name} reads (empty)`, async ({ mount }) => {
    const c = await mount(<FinalMessagePanel text={text} />);
    await expect(pre(c)).toHaveText("(empty)");
  });
}

test("line breaks and indentation are kept verbatim", async ({ mount }) => {
  const text = "Summary:\n  - gate one: pass\n  - gate two: pass\n\nDone.";
  const c = await mount(<FinalMessagePanel text={text} />);
  expect(await pre(c).evaluate((el) => el.textContent)).toBe(text);
  expect(await pre(c).innerText()).toContain("\n  - gate one: pass\n");
  await expect(pre(c)).toHaveCSS("white-space", "pre-wrap");
});

test("markup in the message is text, never HTML", async ({ mount }) => {
  const c = await mount(<FinalMessagePanel text={'<img src=x onerror="window.__pwned=1"><b>bold</b>'} />);
  await expect(pre(c)).toHaveText('<img src=x onerror="window.__pwned=1"><b>bold</b>');
  await expect(pre(c).locator("img, b")).toHaveCount(0);
  expect(await c.page().evaluate(() => (window as unknown as { __pwned?: number }).__pwned)).toBeUndefined();
});

test("long prose wraps inside the block: no sideways scroll in the pre or the page", async ({ mount, page }) => {
  await page.setViewportSize(PHONE);
  const c = await mount(<FinalMessagePanel text={"The contrast gate passed on every diagram in the repository. ".repeat(30)} />);
  expect(await pre(c).evaluate((el) => el.scrollWidth - el.clientWidth)).toBeLessThanOrEqual(0);
  expect(await pageOverflowX(page)).toBeLessThanOrEqual(0);
});

test("an unbroken token (a hash, a URL) never pushes the page sideways", async ({ mount, page }) => {
  await page.setViewportSize(PHONE);
  const token = `https://example.com/${"a1b2c3d4".repeat(60)}`;
  const c = await mount(<FinalMessagePanel text={token} />);
  await expect(pre(c)).toHaveText(token);
  expect(await pageOverflowX(page)).toBeLessThanOrEqual(0);
  // the pre stays within its card
  const [preBox, cardBox] = await Promise.all([pre(c).boundingBox(), c.locator("#FinalMessagePanel").boundingBox()]);
  expect(preBox!.x + preBox!.width).toBeLessThanOrEqual(cardBox!.x + cardBox!.width + 0.5);
});

test("a long message is capped at 480px and scrolls inside the block", async ({ mount }) => {
  const c = await mount(<FinalMessagePanel text={Array.from({ length: 200 }, (_, i) => `line ${i + 1}`).join("\n")} />);
  const box = await pre(c).boundingBox();
  expect(box!.height).toBeLessThanOrEqual(480);
  expect(await pre(c).evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true);
  await expect(pre(c)).toHaveCSS("overflow-y", "auto");
});

for (const mode of ["light", "dark"] as const) {
  test(`${mode}: the block sits on the code surface in the theme's ink`, async ({ mount, page }) => {
    const c = await mount(<FinalMessagePanel text="done" />, { hooksConfig: { mode } });
    expect(await pre(c).evaluate((el) => getComputedStyle(el).backgroundColor)).toBe(await resolveColour(page, "var(--xh-code)"));
    const expected = mode === "dark" ? "rgb(31, 35, 48)" : "rgb(241, 242, 246)";
    expect(await pre(c).evaluate((el) => getComputedStyle(el).backgroundColor)).toBe(expected);
    expect(await pre(c).evaluate((el) => getComputedStyle(el).color)).toBe(await resolveColour(page, "var(--xh-ink)"));
  });
}
