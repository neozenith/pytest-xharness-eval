/**
 * The design tokens themselves (`report.tokens.json`, applied to `:root` by `lib/tokens.ts`), held
 * to WCAG as the page actually resolves them in each theme: every semantic ink clears 4.5:1 as
 * text on both surfaces, and every chart colour clears 1.4.11's 3:1 against the plot it is drawn
 * on. A theme edit that slips under either fails here, before any component spec has to notice.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import type { Page } from "@playwright/test";
import type { HooksConfig } from "../playwright/index";

const MODES = ["light", "dark"] as const;
const INKS = ["ink", "muted", "accent", "good", "bad", "warn"] as const;
const WATERFALL = ["baseline", "read", "context", "thinking", "output", "sub", "total"] as const;
const SERIES = [1, 2, 3, 4, 5, 6, 7, 8] as const;

/** WCAG contrast between two `--xh-*` custom properties as `:root` resolves them. */
const ratio = (page: Page, fg: string, bg: string) =>
  page.evaluate(
    ([f, b]) => {
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 1;
      const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
      const px = (name: string) => {
        const value = getComputedStyle(document.documentElement).getPropertyValue(`--xh-${name}`).trim();
        if (!value) throw new Error(`--xh-${name} is not set`);
        ctx.fillStyle = "#fff";
        ctx.fillRect(0, 0, 1, 1);
        ctx.fillStyle = value;
        ctx.fillRect(0, 0, 1, 1);
        return ctx.getImageData(0, 0, 1, 1).data;
      };
      const lum = (d: Uint8ClampedArray) =>
        [d[0]!, d[1]!, d[2]!]
          .map((v) => v / 255)
          .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
          .reduce((acc, c, i) => acc + c * [0.2126, 0.7152, 0.0722][i]!, 0);
      const [x, y] = [lum(px(f)), lum(px(b))].sort((p, q) => q - p);
      return (x! + 0.05) / (y! + 0.05);
    },
    [fg, bg] as const,
  );

for (const mode of MODES) {
  test(`${mode}: every semantic ink clears 4.5:1 on --xh-bg and --xh-panel`, async ({ page, mount }) => {
    await mount(<div />, { hooksConfig: { mode } satisfies HooksConfig });
    for (const ink of INKS)
      for (const surface of ["bg", "panel"]) expect.soft(await ratio(page, ink, surface), `${ink} on ${surface}`).toBeGreaterThanOrEqual(4.5);
  });

  test(`${mode}: every waterfall and series colour clears 3:1 on --xh-plot`, async ({ page, mount }) => {
    // Regression: the waterfall `read` colour was 2.56:1 (light, #94a3b8) and 2.29:1 (dark,
    // #475569) against the plot, under WCAG 1.4.11's 3:1 for a graphic that carries data.
    await mount(<div />, { hooksConfig: { mode } satisfies HooksConfig });
    for (const name of WATERFALL) expect.soft(await ratio(page, `waterfall-${name}`, "plot"), `waterfall-${name}`).toBeGreaterThanOrEqual(3);
    for (const n of SERIES) expect.soft(await ratio(page, `series-${n}`, "plot"), `series-${n}`).toBeGreaterThanOrEqual(3);
  });
}
