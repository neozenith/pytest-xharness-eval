/** `Details`: a collapsed disclosure; opens and closes on its summary, and is nothing when empty. */
import { expect, test } from "./test";
import { Details } from "../src/components/records/values";

test("starts collapsed, opens on click, closes again", async ({ mount }) => {
  const c = await mount(
    <Details summary="rate limits">
      <p id="inside">used 12.5%</p>
    </Details>,
  );
  await expect(c.locator('[data-el="V.details"]')).toHaveCount(1);
  const inside = c.locator("#inside");
  await expect(inside).toBeHidden();
  await c.getByText("rate limits").click();
  await expect(inside).toBeVisible();
  await c.getByText("rate limits").click();
  await expect(inside).toBeHidden();
});

test("the trigger is keyboard-operable", async ({ mount, page }) => {
  const c = await mount(
    <Details summary="all turn context">
      <p id="inside">x</p>
    </Details>,
  );
  await c.locator(".env-trigger").focus();
  await page.keyboard.press("Enter");
  await expect(c.locator("#inside")).toBeVisible();
});

test("the trigger carries a chevron", async ({ mount }) => {
  const c = await mount(
    <Details summary="s">
      <p>x</p>
    </Details>,
  );
  await expect(c.locator(".env-trigger svg.chev")).toHaveCount(1);
});

test("no children, no disclosure", async ({ mount, page }) => {
  await mount(<Details summary="empty" />);
  await expect(page.locator("#root")).toBeEmpty();
});
