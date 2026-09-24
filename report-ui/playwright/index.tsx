/**
 * What every mounted component stands inside: the page's stylesheet, its Tamagui provider and
 * theme, its tooltip provider, and — per test — the route, the theme and any inline data.
 *
 * A component on this page reads three things from outside its props: the URL (`useRoute`),
 * the theme tokens on `:root` (`applyTokens`) and, for the data hooks, `window.__XH_DATA__`.
 * `hooksConfig` sets each of them *before* mount, so a spec states its whole input in one place.
 */
import { beforeMount } from "@playwright/experimental-ct-react/hooks";
import { TamaguiProvider, Theme } from "tamagui";
import "../src/index.css";
import { config } from "../src/tamagui.config";
import { TooltipProvider } from "../src/components/ui/tooltip";
import { applyTokens, type Mode } from "../src/lib/tokens";
import type { DesignTokens, InlineData } from "../src/lib/types";
import tokens from "../../src/pytest_xharness_eval/assets/report.tokens.json";

export interface HooksConfig {
  /** The query string the component mounts under (`?sort=turns&effort=high`); default `?`. */
  search?: string;
  mode?: Mode;
  /** Served to the data hooks as if `report.py --inline` had embedded it. */
  inline?: InlineData;
}

beforeMount<HooksConfig>(async ({ App, hooksConfig }) => {
  const mode = hooksConfig?.mode ?? "light";
  history.replaceState(null, "", `${location.pathname}${hooksConfig?.search ?? ""}`);
  if (hooksConfig?.inline) window.__XH_DATA__ = hooksConfig.inline;
  else delete window.__XH_DATA__;
  applyTokens(tokens as unknown as DesignTokens, mode);
  document.body.style.background = "var(--xh-bg)";
  // Measure against settled metrics: a layout read before a late font swaps in is a different
  // layout on every platform (CI's Linux fonts load after mount; macOS's are already there).
  await document.fonts.ready;
  return (
    <TamaguiProvider config={config} defaultTheme={mode}>
      <Theme name={mode}>
        <TooltipProvider delayDuration={0}>
          <App />
        </TooltipProvider>
      </Theme>
    </TamaguiProvider>
  );
});
