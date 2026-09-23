/**
 * `Prose`: plain text as wrapped prose, or, when the text opens with a tag, XML-tagged sections.
 * ANSI colour in prose renders as colour.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import { Prose } from "../src/components/records/blocks";
import { ANSI_TEXT, UNBROKEN } from "./fixtures";

test("plain text keeps its line breaks", async ({ mount }) => {
  const c = await mount(<Prose text={"line one\nline two"} />);
  await expect(c.locator('[data-el="V.text"]')).toHaveCount(1);
  await expect(c.locator(".txt")).toHaveCSS("white-space", "pre-wrap");
  await expect(c.locator(".txt")).toHaveText("line one\nline two");
});

test("text that opens with a tag becomes titled sections", async ({ mount }) => {
  const c = await mount(<Prose text={'<system-reminder kind="x">\nbe brief\n</system-reminder>\ntrailing'} />);
  await expect(c.locator('[data-el="V.xmlish"]')).toHaveCount(1);
  await expect(c.locator(".bhead .tag")).toHaveText("<system-reminder>");
  await expect(c.locator(".bhead code")).toHaveText('kind="x"');
  await expect(c).toContainText("trailing");
});

test("text that merely contains a tag later stays prose", async ({ mount }) => {
  const c = await mount(<Prose text={"see <b>this</b>"} />);
  await expect(c.locator('[data-el="V.text"]')).toHaveCount(1);
});

test("ANSI prose renders in colour", async ({ mount }) => {
  const c = await mount(<Prose text={ANSI_TEXT} />);
  await expect(c.locator('[data-el="V.ansi"]')).toHaveCount(1);
  await expect(c).not.toContainText("\u001b[");
});

test("a very long unbroken word wraps inside the card instead of widening the page", async ({ mount, page }) => {
  const c = await mount(<Prose text={UNBROKEN} />);
  await expect(c).toBeVisible();
  const box = await c.locator(".txt").boundingBox();
  expect(box!.width).toBeLessThanOrEqual(1280);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
});
