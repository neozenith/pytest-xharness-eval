/** `Kvs`: a key/value grid; a pair with no value is dropped, and a grid with no pairs is nothing. */
import { expect, test } from "./test";
import { Kvs } from "../src/components/records/values";
import { UNBROKEN } from "./fixtures";

test("keys in the muted column, values beside them, empty values dropped", async ({ mount }) => {
  const c = await mount(
    <Kvs
      pairs={[
        ["model", "gpt-5.6-sol"],
        ["cwd", undefined],
        ["stop", null],
        ["id", ""],
        ["effort", "xhigh"],
      ]}
    />,
  );
  await expect(c.locator('[data-el="V.kvs"]')).toHaveCount(1);
  await expect(c.locator(".kvs > div > b")).toHaveText(["model", "effort"]);
  await expect(c.locator(".kvs .val")).toHaveText(["gpt-5.6-sol", "xhigh"]);
  await expect(c.locator(".kvs")).toHaveCSS("display", "grid");
});

test("a 0 value is kept (it is present)", async ({ mount }) => {
  const c = await mount(<Kvs pairs={[["exit", "0"]]} />);
  await expect(c.locator(".val")).toHaveText("0");
});

test("no pairs, no grid", async ({ mount, page }) => {
  await mount(<Kvs pairs={[["a", undefined]]} />);
  await expect(page.locator("#root")).toBeEmpty();
});

test("an unbroken value wraps within its column", async ({ mount, page }) => {
  const c = await mount(<Kvs pairs={[["cwd", `/${UNBROKEN}`]]} />);
  await expect(c.locator(".val")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
});
