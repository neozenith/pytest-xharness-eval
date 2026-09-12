/**
 * The app's real stylesheet, so stories render with production styling (dark theme,
 * see src/styles.css `:root`). `a11y` is configured for WCAG AAA (7:1 normal text,
 * 4.5:1 large text): axe-core's `color-contrast` rule only checks AA (4.5:1), so it is
 * disabled in favour of `color-contrast-enhanced` (the AAA rule, tagged `wcag2aaa`,
 * disabled by default in axe-core) and every WCAG 2.x/2.1/2.2 tag up to AAA is included
 * in `runOnly` so nothing below AAA is silently skipped.
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
        rules: [
          { id: "color-contrast", enabled: false },
          { id: "color-contrast-enhanced", enabled: true },
        ],
      },
      options: {
        runOnly: {
          type: "tag",
          values: ["wcag2a", "wcag2aa", "wcag2aaa", "wcag21a", "wcag21aa", "wcag22aa"],
        },
      },
    },
  },
};

export default preview;
