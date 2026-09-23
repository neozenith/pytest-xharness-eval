/**
 * `CopyId`: a session id rendered short (its `label`), copied whole on click. The glyph rests at a
 * third strength and lights on hover or focus, flips to a tick for 1.2s after a copy, and keeps
 * its box throughout. The click never bubbles (it sits inside clickable table rows).
 */
import { expect, test } from "./test";
import type { HooksConfig } from "../playwright/index";
import { CopyId } from "../src/components/CopyId";

const ID = "1feb573f-ba51-4e77-845f-12c4bcb08252";

test.describe("rendering", () => {
  test("shows the label, titles and labels the button with the whole id", async ({ mount, page }) => {
    await mount(<CopyId id={ID} label="1feb573f" />);
    const button = page.getByRole("button", { name: `Copy ${ID}` });
    await expect(button).toHaveText("1feb573f");
    await expect(button).toHaveAttribute("title", ID);
    await expect(button).toHaveAttribute("type", "button");
    await expect(button.locator("svg.lucide-copy")).toHaveCount(1);
  });

  test("without a label it shows the whole id", async ({ mount, page }) => {
    await mount(<CopyId id={ID} />);
    await expect(page.getByRole("button", { name: `Copy ${ID}` })).toHaveText(ID);
  });

  test("sits on the 20px chip tier, one line, no resting fill", async ({ mount, page }) => {
    await mount(<CopyId id={ID} />);
    const button = page.getByRole("button");
    expect((await button.boundingBox())!.height).toBe(20);
    await expect(button).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
    await expect(button.locator("span").first()).toHaveCSS("white-space", "nowrap");
  });

  test("a long id never wraps, even in a narrow box", async ({ mount, page }) => {
    await page.setViewportSize({ width: 200, height: 400 });
    await mount(<CopyId id={`${ID}-${ID}`} />);
    expect((await page.getByRole("button").boundingBox())!.height).toBe(20);
  });

  test("the glyph rests at a third strength and lights on hover and focus", async ({ mount, page }) => {
    await mount(<CopyId id={ID} label="short" />);
    const button = page.getByRole("button");
    const glyph = button.locator("svg").locator("xpath=..");
    await expect(glyph).toHaveCSS("opacity", "0.35");
    await button.hover();
    await expect(glyph).toHaveCSS("opacity", "1");
    await page.mouse.move(600, 600);
    await expect(glyph).toHaveCSS("opacity", "0.35");
    await button.focus();
    await expect(glyph).toHaveCSS("opacity", "1");
    await button.blur();
    await expect(glyph).toHaveCSS("opacity", "0.35");
  });

  test("hover brings up the $line surface", async ({ mount, page }) => {
    await mount(<CopyId id={ID} />);
    const button = page.getByRole("button");
    await button.hover();
    await expect(button).toHaveCSS("background-color", "rgb(226, 228, 234)");
  });

  test("dark mode: the label inks in the dark theme's colour", async ({ mount, page }) => {
    await mount<HooksConfig>(<CopyId id={ID} label="short" />, { hooksConfig: { mode: "dark" } });
    await expect(page.getByRole("button").locator("span").first()).not.toHaveCSS("color", "rgb(0, 0, 0)");
    await page.getByRole("button").hover();
    await expect(page.getByRole("button")).toHaveCSS("background-color", "rgb(42, 46, 58)");
  });
});

test.describe("copying", () => {
  test.beforeEach(async ({ context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  });

  test("a click copies the whole id, not the label, and flips to a tick", async ({ mount, page }) => {
    await mount(<CopyId id={ID} label="1feb573f" />);
    const button = page.getByRole("button");
    const w0 = (await button.boundingBox())!.width;
    await button.click();
    await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe(ID);
    await expect(button.locator("svg.lucide-check")).toHaveCount(1);
    await expect(button.locator("svg.lucide-copy")).toHaveCount(0);
    // the tick is $good at full strength
    const glyph = button.locator("svg").locator("xpath=..");
    await expect(glyph).toHaveCSS("color", "rgb(4, 111, 81)");
    await expect(glyph).toHaveCSS("opacity", "1");
    // the glyph keeps its box: nothing reflows when it flips
    expect((await button.boundingBox())!.width).toBe(w0);
  });

  test("the tick reverts to the copy glyph after about 1.2s", async ({ mount, page }) => {
    await mount(<CopyId id={ID} />);
    const button = page.getByRole("button");
    await button.click();
    await expect(button.locator("svg.lucide-check")).toHaveCount(1);
    await page.waitForTimeout(700);
    await expect(button.locator("svg.lucide-check")).toHaveCount(1);
    await expect(button.locator("svg.lucide-copy")).toHaveCount(1, { timeout: 2_000 });
  });

  test("keyboard: Enter and Space copy", async ({ mount, page }) => {
    await mount(<CopyId id={ID} label="x" />);
    const button = page.getByRole("button");
    await button.focus();
    await page.keyboard.press("Enter");
    await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe(ID);
    await page.evaluate(() => navigator.clipboard.writeText(""));
    await page.keyboard.press("Space");
    await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe(ID);
  });

  test("the click does not bubble to a clickable row around it", async ({ mount, page }) => {
    let rowClicks = 0;
    await mount(
      <div role="row" onClick={() => (rowClicks += 1)} style={{ padding: 20 }}>
        <CopyId id={ID} label="x" />
      </div>,
    );
    await page.getByRole("button").click();
    await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe(ID);
    await page.getByRole("row").click({ position: { x: 5, y: 5 } });
    await expect.poll(() => rowClicks).toBe(1); // the row itself is live; only the chip's click was stopped
  });

  test("a clipboard that refuses is swallowed: no tick, no error, the title keeps the id", async ({ mount, page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await mount(<CopyId id={ID} label="x" />);
    await page.evaluate(() => {
      Object.defineProperty(navigator, "clipboard", { value: { writeText: () => Promise.reject(new Error("denied")) }, configurable: true });
    });
    const button = page.getByRole("button");
    await button.click();
    await page.waitForTimeout(200);
    await expect(button.locator("svg.lucide-check")).toHaveCount(0);
    await expect(button.locator("svg.lucide-copy")).toHaveCount(1);
    await expect(button).toHaveAttribute("title", ID);
    expect(errors).toEqual([]);
  });
});
