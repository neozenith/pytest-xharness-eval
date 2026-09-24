/** `Flag`: true as a green check, false as a muted cross, anything else as its text. */
import { expect, test } from "./test";
import { Flag } from "../src/components/records/values";

test("true, false and other values", async ({ mount, page }) => {
  await mount(<Flag value={true} />);
  await expect(page.locator("#root")).toHaveText("✓ true");
  await expect(page.locator("#root .good")).toHaveText("✓");
});

test("false is a muted cross", async ({ mount, page }) => {
  await mount(<Flag value={false} />);
  await expect(page.locator("#root")).toHaveText("✗ false");
  await expect(page.locator("#root .muted")).toHaveText("✗");
});

test("a non-boolean is its text", async ({ mount, page }) => {
  await mount(<Flag value="restricted" />);
  await expect(page.locator("#root")).toHaveText("restricted");
});
