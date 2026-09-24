/**
 * `Tooltip` / `TooltipTrigger` / `TooltipContent` (src/components/ui/tooltip.tsx): Tamagui's
 * tooltip with the page's defaults (200ms delay, 150ms rest, placed on top), inverted colours
 * (`$color` fill, `$panel` ink), a max-content width capped at 280px. `TooltipProvider` is a
 * pass-through; `playwright/index.tsx` mounts every component inside one.
 */
import { expect, test } from "./test";
import type { Locator } from "@playwright/test";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "../src/components/ui/tooltip";
import type { HooksConfig } from "../playwright/index";

const resolved = (el: Locator, token: string) =>
  el.evaluate((_, t) => {
    const probe = document.createElement("span");
    probe.style.color = `var(--xh-${t})`;
    document.body.append(probe);
    const out = getComputedStyle(probe).color;
    probe.remove();
    return out;
  }, token);

/** WCAG contrast of the element's text over every ancestor background, composited on a canvas. */
const contrast = (el: Locator) =>
  el.evaluate((node) => {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 1;
    const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
    const paint = (colour: string) => {
      ctx.fillStyle = colour;
      ctx.fillRect(0, 0, 1, 1);
    };
    const chain: string[] = [];
    for (let n: Element | null = node; n; n = n.parentElement) chain.push(getComputedStyle(n).backgroundColor);
    paint("#ffffff");
    for (const bg of chain.reverse()) paint(bg);
    const [br, bgc, bb] = ctx.getImageData(0, 0, 1, 1).data;
    paint(getComputedStyle(node).color);
    const [fr, fg, fb] = ctx.getImageData(0, 0, 1, 1).data;
    const lum = (r = 0, g = 0, b = 0) =>
      [r, g, b]
        .map((v) => v / 255)
        .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
        .reduce((acc, c, i) => acc + c * [0.2126, 0.7152, 0.0722][i]!, 0);
    const [a, b] = [lum(fr, fg, fb), lum(br, bgc, bb)].sort((x, y) => y - x);
    return (a! + 0.05) / (b! + 0.05);
  });

const LONG = "estimated_cost_usd — the sweep's price at the bundled per-model rates, summed over every billed call including cache reads and writes";

const tip = (text = "the price at bundled rates", props: { open?: boolean } = {}) => (
  <div style={{ padding: 120 }}>
    <Tooltip {...props}>
      <TooltipTrigger asChild>
        <button type="button">cost</button>
      </TooltipTrigger>
      <TooltipContent className="tip-extra">{text}</TooltipContent>
    </Tooltip>
    <button type="button">elsewhere</button>
  </div>
);

test("Tooltip is closed at rest: no role=tooltip, trigger collapsed", async ({ page, mount }) => {
  await mount(tip());
  await expect(page.getByRole("button", { name: "cost" })).toHaveAttribute("data-state", "closed");
  await expect(page.getByRole("tooltip")).toHaveCount(0);
});

test("Tooltip opens on hover and describes its trigger", async ({ page, mount }) => {
  await mount(tip());
  const trigger = page.getByRole("button", { name: "cost" });
  await trigger.hover();
  const t = page.getByRole("tooltip");
  await expect(t).toBeVisible();
  await expect(t).toHaveText("the price at bundled rates");
  const by = (await trigger.getAttribute("aria-describedby"))!;
  await expect(t.locator(`[id="${by}"]`)).toHaveText("the price at bundled rates");
  await expect(trigger).toHaveAccessibleDescription("the price at bundled rates");
});

test("Tooltip closes when the pointer leaves", async ({ page, mount }) => {
  await mount(tip());
  await page.getByRole("button", { name: "cost" }).hover();
  await expect(page.getByRole("tooltip")).toBeVisible();
  await page.mouse.move(5, 5);
  await expect(page.getByRole("tooltip")).toBeHidden();
});

test("Tooltip opens on keyboard focus and closes on blur", async ({ page, mount }) => {
  // Regression: a keyboard user who tabbed to the trigger got no tooltip at all (WCAG 1.4.13 /
  // 2.1.1: content shown on hover must also be reachable by focus).
  await mount(tip());
  await page.keyboard.press("Tab");
  const trigger = page.getByRole("button", { name: "cost" });
  await expect(trigger).toBeFocused();
  await expect(page.getByRole("tooltip")).toBeVisible();
  await expect(page.getByRole("tooltip")).toHaveText("the price at bundled rates");
  await expect(trigger).toHaveAccessibleDescription("the price at bundled rates");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "elsewhere" })).toBeFocused();
  await expect(page.getByRole("tooltip")).toBeHidden();
});

test("Tooltip opened by focus is dismissed with Escape, focus staying on the trigger", async ({ page, mount }) => {
  await mount(tip());
  await page.keyboard.press("Tab");
  await expect(page.getByRole("tooltip")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("tooltip")).toBeHidden();
  await expect(page.getByRole("button", { name: "cost" })).toBeFocused();
});

test("Tooltip does not pop on a pointer click's focus (focus-visible only)", async ({ page, mount }) => {
  await mount(tip());
  const box = (await page.getByRole("button", { name: "cost" }).boundingBox())!;
  await page.mouse.move(box.x + 2, box.y + 2);
  await page.mouse.down();
  await page.mouse.up();
  // The click toggles or leaves it; either way the focus handler must not have forced it open.
  await page.mouse.move(5, 5);
  await expect(page.getByRole("tooltip")).toBeHidden();
});

test("Tooltip controlled: focus reports through onOpenChange, the open prop decides", async ({ page, mount }) => {
  const seen: boolean[] = [];
  await mount(
    <div style={{ padding: 120 }}>
      <Tooltip open={false} onOpenChange={(o) => seen.push(o)}>
        <TooltipTrigger asChild>
          <button type="button">cost</button>
        </TooltipTrigger>
        <TooltipContent>tip</TooltipContent>
      </Tooltip>
    </div>,
  );
  await page.keyboard.press("Tab");
  await expect.poll(() => seen).toContain(true);
  await expect(page.getByRole("tooltip")).toHaveCount(0);
});

test("Tooltip is dismissed with Escape (hover-opened)", async ({ page, mount }) => {
  await mount(tip());
  await page.getByRole("button", { name: "cost" }).hover();
  await expect(page.getByRole("tooltip")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("tooltip")).toBeHidden();
});

test("Tooltip waits for its open delay rather than flashing on a pass-over", async ({ page, mount }) => {
  await mount(tip());
  const box = (await page.getByRole("button", { name: "cost" }).boundingBox())!;
  await page.mouse.move(box.x + 2, box.y + 2);
  // Well inside the 200ms delay: nothing yet.
  await expect(page.getByRole("tooltip")).toHaveCount(0, { timeout: 50 });
  await expect(page.getByRole("tooltip")).toBeVisible();
});

test("Tooltip controlled open renders without interaction", async ({ page, mount }) => {
  await mount(tip("pinned", { open: true }));
  await expect(page.getByRole("tooltip")).toHaveText("pinned");
});

test("TooltipContent sits above its trigger (placement top)", async ({ page, mount }) => {
  await mount(tip("pinned", { open: true }));
  const t = (await page.getByRole("tooltip").boundingBox())!;
  const trigger = (await page.getByRole("button", { name: "cost" }).boundingBox())!;
  expect(t.y + t.height).toBeLessThanOrEqual(trigger.y + 1);
});

test("TooltipContent sizes to one line when short and caps at 280px when long", async ({ page, mount }) => {
  const c = await mount(tip("short tip", { open: true }));
  const short = page.getByRole("tooltip").getByText("short tip");
  // One line: 16px line height.
  expect((await short.boundingBox())!.height).toBeLessThanOrEqual(17);
  await c.update(tip(LONG, { open: true }));
  const panel = page.locator(".tip-extra");
  await expect(panel).toHaveCSS("max-width", "280px");
  expect((await panel.boundingBox())!.width).toBeLessThanOrEqual(280.5);
  expect((await panel.boundingBox())!.width).toBeGreaterThan(200);
  expect((await page.getByRole("tooltip").getByText(LONG).boundingBox())!.height).toBeGreaterThan(17);
});

test("TooltipContent forwards className and its type is 12/16", async ({ page, mount }) => {
  await mount(tip("pinned", { open: true }));
  const panel = page.locator(".tip-extra");
  await expect(panel).toHaveCount(1);
  await expect(panel).toHaveCSS("border-top-left-radius", "7px");
  await expect(panel).toHaveCSS("padding-left", "10px");
  await expect(panel).toHaveCSS("padding-top", "6px");
  const text = page.getByRole("tooltip").getByText("pinned");
  await expect(text).toHaveCSS("font-size", "12px");
  await expect(text).toHaveCSS("line-height", "16px");
});

for (const mode of ["light", "dark"] as const) {
  test(`TooltipContent is inverted: --xh-ink fill, --xh-panel ink, AA contrast (${mode})`, async ({ page, mount }) => {
    await mount(tip("pinned", { open: true }), { hooksConfig: { mode } satisfies HooksConfig });
    const panel = page.locator(".tip-extra");
    await expect(panel).toHaveCSS("background-color", await resolved(panel, "ink"));
    const text = page.getByRole("tooltip").getByText("pinned");
    await expect(text).toHaveCSS("color", await resolved(text, "panel"));
    await expect(panel).toHaveCSS("opacity", "1");
    expect(await contrast(text)).toBeGreaterThanOrEqual(4.5);
  });
}

test("TooltipProvider passes its children straight through", async ({ page, mount }) => {
  await mount(
    <TooltipProvider delayDuration={0}>
      <span id="child">inside</span>
    </TooltipProvider>,
  );
  await expect(page.locator("#child")).toHaveText("inside");
});

test("Tooltip is hoverable: moving the pointer onto it keeps it open (WCAG 1.4.13)", async ({ page, mount }) => {
  await mount(tip(LONG));
  await page.getByRole("button", { name: "cost" }).hover();
  const t = page.getByRole("tooltip");
  await expect(t).toBeVisible();
  const box = (await t.boundingBox())!;
  const trig = (await page.getByRole("button", { name: "cost" }).boundingBox())!;
  // Straight up from the trigger into the tooltip body.
  await page.mouse.move(trig.x + trig.width / 2, box.y + box.height / 2, { steps: 8 });
  await page.waitForTimeout(600);
  await expect(t).toBeVisible();
});

test("TooltipContent does not animate under prefers-reduced-motion", async ({ page, mount }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mount(tip("pinned", { open: true }));
  const d = await page.locator(".tip-extra").evaluate((n) => getComputedStyle(n).transitionDuration);
  expect(d.split(",").every((x) => Number.parseFloat(x) < 0.001)).toBe(true);
});
