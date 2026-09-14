/**
 * The app's real stylesheet, so stories render with production styling (dark theme,
 * see src/styles.css `:root`). `a11y` is configured for WCAG AAA (7:1 normal text,
 * 4.5:1 large text) via `color-contrast-enhanced` (the AAA rule, tagged `wcag2aaa`,
 * disabled by default in axe-core, enabled below) and every WCAG 2.x/2.1/2.2 tag up to
 * AAA is included in `runOnly` so nothing below AAA is silently skipped.
 *
 * `color-contrast` (the AA rule) stays enabled alongside it -- do NOT disable it. Its
 * check function (axe-core's `colorContrastEvaluate`) has a `minThreshold` escape hatch
 * on `color-contrast-enhanced` only: any computed ratio below 4.5 is treated as an
 * unreliable reading (axe assumes it likely misdetected a background) and the check
 * *passes* rather than flags it -- see `node_modules/axe-core/axe.js`'s
 * `colorContrastEvaluate`, the `isValid = contrast2 > expected` branch immediately
 * followed by the `minThreshold` early return. `color-contrast`'s own options have no
 * `minThreshold`, so it is the only rule that reliably catches a severe, extreme
 * contrast failure (e.g. ~2:1) -- exactly the range AAA-only silently waves through.
 * Proven by mutation: with `color-contrast` disabled, injecting a ~1.97:1-contrast
 * paragraph into BandCaveat.stories.tsx's decorator reported the story a11y status as
 * "passed", axe's own message reading "Element has sufficient color contrast of
 * 1.9668813110341057" -- re-enabling this rule turns that into a real failure.
 */
import type { Preview } from "@storybook/react-vite";
import "../src/styles.css";

const preview: Preview = {
  parameters: {
    backgrounds: {
      default: "app",
      options: {
        app: { name: "app", value: "#0b1120" },
        panel: { name: "panel", value: "#111a2e" },
      },
    },
    a11y: {
      // A violation fails the story instead of only surfacing in the panel.
      test: "error",
      config: {
        rules: [{ id: "color-contrast-enhanced", enabled: true }],
      },
      options: {
        runOnly: {
          type: "tag",
          values: [
            "wcag2a",
            "wcag2aa",
            "wcag2aaa",
            "wcag21a",
            "wcag21aa",
            "wcag22aa",
          ],
        },
      },
    },
  },
};

export default preview;
