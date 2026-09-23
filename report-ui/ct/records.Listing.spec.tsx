/** `Listing`: `- name: description` lines as a two-column table; anything else as markdown. */
import { expect, test } from "@playwright/experimental-ct-react";
import { Listing } from "../src/components/records/values";
import { UNBROKEN } from "./fixtures";

test("name and description columns", async ({ mount }) => {
  const c = await mount(<Listing text={"- gooddocs: audit docs\n- refactor: restructure code\nnot a row"} />);
  await expect(c.locator('[data-el="V.listing"]')).toHaveCount(1);
  await expect(c.locator("tr")).toHaveCount(2);
  await expect(c.locator("tr td:first-child code")).toHaveText(["gooddocs", "refactor"]);
  await expect(c.locator("tr td:last-child")).toHaveText(["audit docs", "restructure code"]);
});

test("text with no rows is shown as markdown code", async ({ mount }) => {
  const c = await mount(<Listing text={"# Skills\nnone"} />);
  await expect(c.locator('[data-el="V.code"]')).toHaveCount(1);
  await expect(c.locator("code.language-markdown")).toContainText("# Skills");
});

test("a long unbroken description wraps inside the table", async ({ mount, page }) => {
  await mount(<Listing text={`- x: ${UNBROKEN}`} />);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
});
