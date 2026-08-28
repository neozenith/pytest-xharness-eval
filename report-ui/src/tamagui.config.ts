/**
 * Tamagui is the page's base UI and animation framework; its themes do not own any colour.
 * Every semantic key resolves to a `--xh-*` custom property (ADR 0024), so `report.tokens.json`
 * themes Tamagui components exactly as it themes everything else, and light/dark is the same
 * `.dark` class flip `lib/tokens.ts` already performs — both Tamagui themes carry the same
 * `var()` references on purpose.
 */
import { defaultConfig } from "@tamagui/config/v4";
import { createTamagui } from "tamagui";

const xh = {
  background: "var(--xh-panel)",
  backgroundHover: "var(--xh-code)",
  backgroundPress: "var(--xh-code)",
  backgroundFocus: "var(--xh-code)",
  backgroundStrong: "var(--xh-bg)",
  backgroundTransparent: "transparent",
  color: "var(--xh-ink)",
  colorHover: "var(--xh-ink)",
  colorPress: "var(--xh-ink)",
  colorFocus: "var(--xh-ink)",
  borderColor: "var(--xh-line)",
  borderColorHover: "var(--xh-muted)",
  borderColorPress: "var(--xh-accent)",
  borderColorFocus: "var(--xh-accent)",
  placeholderColor: "var(--xh-muted)",
  outlineColor: "var(--xh-accent)",
  // report vocabulary, usable as `$panel`, `$muted`, … on any Tamagui component
  panel: "var(--xh-panel)",
  pageBg: "var(--xh-bg)",
  code: "var(--xh-code)",
  muted: "var(--xh-muted)",
  accent: "var(--xh-accent)",
  good: "var(--xh-good)",
  bad: "var(--xh-bad)",
  warn: "var(--xh-warn)",
  line: "var(--xh-line)",
  axis: "var(--xh-axis)",
  shadow: "var(--xh-shadow)",
};

export const config = createTamagui({
  ...defaultConfig,
  settings: {
    ...defaultConfig.settings,
    disableSSR: true,
    // `var(--xh-*)` strings are the whole theming model here: longhand CSS names and
    // arbitrary values must both be legal styled() inputs.
    onlyAllowShorthands: false,
    allowedStyleValues: false,
  },
  fonts: {
    body: { ...defaultConfig.fonts.body, family: "var(--xh-font-body)" },
    heading: { ...defaultConfig.fonts.heading, family: "var(--xh-font-body)" },
    mono: { ...defaultConfig.fonts.body, family: "var(--xh-font-mono)" },
  },
  themes: {
    light: { ...defaultConfig.themes.light, ...xh },
    dark: { ...defaultConfig.themes.dark, ...xh },
  },
});

export type AppConfig = typeof config;

declare module "tamagui" {
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type -- the documented Tamagui type-registration pattern
  interface TamaguiCustomConfig extends AppConfig {}
}
