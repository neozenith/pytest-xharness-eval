/**
 * `RecordViewToggle`: the page-wide nice/raw control every card follows. It reports a choice,
 * shows which one is current, and never reports an empty choice when the pressed segment is
 * pressed again.
 */
import { expect, test } from "./test";
import { RecordViewToggle } from "../src/components/records/RecordViewToggle";
import type { HooksConfig } from "../playwright/index";

test("both segments are labelled, and the current one is on", async ({ mount }) => {
  const c = await mount(<RecordViewToggle view="nice" onChange={() => {}} />);
  await expect(c.locator("#RecordViewToggle")).toHaveCount(1);
  await expect(c.locator("#RecordViewToggle")).toHaveAttribute("title", "how each log record renders");
  await expect(c.locator('[data-rv="nice"]')).toHaveText("nice records");
  await expect(c.locator('[data-rv="raw"]')).toHaveText("raw JSON");
  await expect(c.locator('[data-rv="nice"]')).toHaveAttribute("data-state", "on");
  await expect(c.locator('[data-rv="raw"]')).toHaveAttribute("data-state", "off");
  await expect(c.locator('[data-el="RecordViewToggle"].el')).toHaveText("RecordViewToggle");
});

test("choosing the other segment reports it", async ({ mount }) => {
  const seen: string[] = [];
  const c = await mount(<RecordViewToggle view="nice" onChange={(v) => seen.push(v)} />);
  await c.getByText("raw JSON").click();
  await expect.poll(() => seen).toEqual(["raw"]);
  await c.update(<RecordViewToggle view="raw" onChange={(v) => seen.push(v)} />);
  await expect(c.locator('[data-rv="raw"]')).toHaveAttribute("data-state", "on");
  await c.getByText("nice records").click();
  await expect.poll(() => seen).toEqual(["raw", "nice"]);
});

test("pressing the current segment again reports nothing (no empty view)", async ({ mount }) => {
  const seen: string[] = [];
  const c = await mount(<RecordViewToggle view="nice" onChange={(v) => seen.push(v)} />);
  await c.getByText("nice records").click();
  await c.getByText("nice records").click();
  // Give any stray callback time to arrive before asserting it never did.
  await c.page().waitForTimeout(200);
  expect(seen).toEqual([]);
  await expect(c.locator('[data-rv="nice"]')).toHaveAttribute("data-state", "on");
});

test("keyboard: the segments are reachable and Enter chooses", async ({ mount, page }) => {
  const seen: string[] = [];
  const c = await mount(<RecordViewToggle view="nice" onChange={(v) => seen.push(v)} />);
  await c.locator('[data-rv="raw"]').focus();
  await page.keyboard.press("Enter");
  await expect.poll(() => seen).toEqual(["raw"]);
});

test("renders in dark mode with the segment text readable on the page", async ({ mount }) => {
  const c = await mount<HooksConfig>(<RecordViewToggle view="raw" onChange={() => {}} />, { hooksConfig: { mode: "dark" } });
  await expect(c.locator('[data-rv="raw"]')).toBeVisible();
  const ink = await c.locator('[data-rv="nice"]').evaluate((el) => getComputedStyle(el.querySelector("span") ?? el).color);
  expect(ink).not.toBe("rgb(0, 0, 0)");
});
