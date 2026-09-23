import { readChartTheme } from "@/components/charts/plotly";
import tokens from "../../../src/pytest_xharness_eval/assets/report.tokens.json";

test("a chart drawn before the tokens load uses the bundled light theme, not a second palette", () => {
  // jsdom sets no `--xh-*` properties, so every value here is the fallback.
  const light = tokens.themes.light;
  const theme = readChartTheme();
  expect({ ink: theme.ink, muted: theme.muted, grid: theme.grid, axis: theme.axis, plot: theme.plot, panel: theme.panel, accent: theme.accent }).toEqual({
    ink: light.ink,
    muted: light.muted,
    grid: light.grid,
    axis: light.axis,
    plot: light.plot,
    panel: light.panel,
    accent: light.accent,
  });
  expect(theme.series).toEqual(light.series);
  expect(theme.waterfall).toEqual(light.waterfall);
});
