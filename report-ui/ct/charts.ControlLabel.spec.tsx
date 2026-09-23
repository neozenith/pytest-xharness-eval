/** The label on a chart control: description size and measure, heading weight, full ink. */
import { expect, test } from "@playwright/experimental-ct-react";
import { ControlLabel } from "../src/components/charts/common";
import type { HooksConfig } from "../playwright";
import { rgb, tokens } from "./charts.helpers";

test.describe("ControlLabel", () => {
  for (const mode of ["light", "dark"] as const) {
    test(`a 12.5/18 semibold span in the ${mode} ink`, async ({ mount }) => {
      const m = await mount<HooksConfig>(<ControlLabel>Chart x-axis</ControlLabel>, { hooksConfig: { mode } });
      const c = m.getByText("Chart x-axis");
      await expect(c).toHaveText("Chart x-axis");
      expect(await c.evaluate((el) => el.tagName)).toBe("SPAN");
      await expect(c).toHaveCSS("font-size", "12.5px");
      await expect(c).toHaveCSS("line-height", "18px");
      await expect(c).toHaveCSS("font-weight", "600");
      await expect(c).toHaveCSS("color", rgb(tokens.themes[mode].ink));
    });
  }
});
