/**
 * `Badge` (src/components/ui/badge.tsx): a pill whose `tone` is ink-on-tint of one `--xh-*`
 * token. The file's own promise is that ink-on-tint "clears AA in both themes for every
 * semantic colour", so contrast is measured here, composited the way the browser paints it.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import type { Locator } from "@playwright/test";
import { Badge } from "../src/components/ui/badge";
import type { HooksConfig } from "../playwright/index";

const TONES = ["good", "bad", "warn", "accent", "outline"] as const;
const MODES = ["light", "dark"] as const;

/** A tone's ink token; `outline` inks with `--xh-muted`. */
const INK: Record<(typeof TONES)[number], string> = { good: "good", bad: "bad", warn: "warn", accent: "accent", outline: "muted" };

/**
 * Contrast of the element's text against what is actually painted behind it: every ancestor
 * background composited bottom-up on a canvas (so `color-mix(… transparent)` tints resolve
 * exactly as the browser blends them), then the WCAG relative-luminance ratio.
 */
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

/** What `var(--xh-<token>)` resolves to on this page, in the same serialisation `color` uses. */
const resolved = (el: Locator, token: string) =>
  el.evaluate((_, t) => {
    const probe = document.createElement("span");
    probe.style.color = `var(--xh-${t})`;
    document.body.append(probe);
    const out = getComputedStyle(probe).color;
    probe.remove();
    return out;
  }, token);

test("Badge renders a span with its text, outline by default", async ({ mount }) => {
  const root = await mount(<Badge>pass</Badge>);
  const c = root.getByText("pass", { exact: true });
  await expect(c).toHaveText("pass");
  expect(await c.evaluate((n) => n.tagName)).toBe("SPAN");
  await expect(c).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
  await expect(c).toHaveCSS("color", await resolved(c, "muted"));
  await expect(c).toHaveCSS("border-top-color", await resolved(c, "line"));
});

test("Badge is a 20px pill that does not wrap", async ({ mount }) => {
  const c = await mount(
    <div style={{ width: 40 }}>
      <Badge tone="accent">a long badge label</Badge>
    </div>,
  );
  const badge = c.getByText("a long badge label");
  await expect(badge).toHaveCSS("white-space", "nowrap");
  await expect(badge).toHaveCSS("height", "20px");
  await expect(badge).toHaveCSS("font-size", "11px");
  await expect(badge).toHaveCSS("font-weight", "600");
  await expect(badge).toHaveCSS("display", "inline-flex");
  const box = await badge.boundingBox();
  expect(box!.height).toBeCloseTo(20, 0);
  expect(Number.parseFloat(await badge.evaluate((n) => getComputedStyle(n).borderTopLeftRadius))).toBeGreaterThanOrEqual(10);
});

for (const mode of MODES) {
  for (const tone of TONES) {
    test(`Badge tone=${tone} in ${mode}: ink is --xh-${INK[tone]}, and the fill is a tint`, async ({ mount }) => {
      const root = await mount(<Badge tone={tone}>{tone}</Badge>, { hooksConfig: { mode } satisfies HooksConfig });
      const c = root.getByText(tone, { exact: true });
      await expect(c).toHaveText(tone);
      await expect(c).toHaveCSS("color", await resolved(c, INK[tone]));
      if (tone === "outline") {
        await expect(c).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
      } else {
        // A tint, never a solid slab: the background carries alpha.
        const bg = await c.evaluate((n) => getComputedStyle(n).backgroundColor);
        expect(bg).not.toBe("rgba(0, 0, 0, 0)");
        expect(bg).toMatch(/\/ 0\.1|, 0\.1|0\.13/);
      }
    });

    for (const surface of ["bg", "panel"] as const) {
      test(`Badge tone=${tone} in ${mode} on --xh-${surface}: text contrast >= 4.5:1`, async ({ mount }) => {
        // Regression: the 13% self-tint once dragged light `good` to 4.30:1 on --xh-bg and `warn` to
        // 3.95:1 / 4.21:1; the light tokens were darkened (same hue) until every tone clears AA.
        const root = await mount(
          <div style={{ background: `var(--xh-${surface})`, padding: 8 }}>
            <Badge tone={tone}>{tone}</Badge>
          </div>,
          { hooksConfig: { mode } satisfies HooksConfig },
        );
        expect(await contrast(root.getByText(tone, { exact: true }))).toBeGreaterThanOrEqual(4.5);
      });
    }
  }
}

test("Badge tones differ between light and dark (tokens, not constants)", async ({ mount }) => {
  const light = await mount(<Badge tone="good">good</Badge>, { hooksConfig: { mode: "light" } satisfies HooksConfig });
  const lightInk = await light.getByText("good").evaluate((n) => getComputedStyle(n).color);
  await light.unmount();
  const dark = await mount(<Badge tone="good">good</Badge>, { hooksConfig: { mode: "dark" } satisfies HooksConfig });
  const darkInk = await dark.getByText("good").evaluate((n) => getComputedStyle(n).color);
  expect(lightInk).toBe("rgb(4, 111, 81)");
  expect(darkInk).toBe("rgb(52, 211, 153)");
});
