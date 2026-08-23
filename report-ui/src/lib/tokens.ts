/**
 * Design tokens -> CSS custom properties (ADR 0024). The shadcn semantic variables in
 * index.css alias the `--xh-*` names set here, so one JSON file themes every component.
 */
import type { DesignTokens, ThemeTokens } from "./types";

export type Mode = "light" | "dark";

const SCALARS: (keyof ThemeTokens)[] = ["bg", "panel", "ink", "muted", "line", "accent", "good", "bad", "warn", "code", "grid", "plot"];

export function applyTokens(tokens: DesignTokens, mode: Mode, root: HTMLElement = document.documentElement) {
  const theme = tokens.themes[mode];
  for (const key of SCALARS) {
    const value = theme[key];
    if (typeof value === "string") root.style.setProperty(`--xh-${key}`, value);
  }
  theme.series.forEach((c, i) => root.style.setProperty(`--xh-series-${i + 1}`, c));
  for (const [name, colour] of Object.entries(theme.waterfall ?? {})) root.style.setProperty(`--xh-waterfall-${name}`, colour);
  for (const [name, colour] of Object.entries(tokens.categories ?? {})) root.style.setProperty(`--xh-category-${name}`, colour);
  if (tokens.fonts?.body) root.style.setProperty("--xh-font-body", tokens.fonts.body);
  if (tokens.fonts?.mono) root.style.setProperty("--xh-font-mono", tokens.fonts.mono);
  root.classList.toggle("dark", mode === "dark");
  root.style.colorScheme = mode;
}

const STORAGE_KEY = "xharness-report-theme";

export function initialMode(): Mode {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* storage unavailable: fall through to the system preference */
  }
  return typeof matchMedia !== "undefined" && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function rememberMode(mode: Mode) {
  try {
    localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    /* a remembered theme is a convenience, never a requirement */
  }
}
