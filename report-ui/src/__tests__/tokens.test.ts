import { applyTokens } from "@/lib/tokens";
import type { DesignTokens } from "@/lib/types";

const theme = (accent: string) => ({
  bg: "#000",
  panel: "#111",
  ink: "#fff",
  muted: "#888",
  line: "#222",
  accent,
  good: "#0f0",
  bad: "#f00",
  warn: "#ff0",
  code: "#333",
  grid: "#444",
  plot: "#111",
  series: ["#1", "#2"],
  waterfall: { baseline: "#5" },
});
const tokens: DesignTokens = { themes: { light: theme("#l"), dark: theme("#d") }, categories: { prompt: "#p" }, fonts: { mono: "Menlo" } };

test("tokens land as --xh-* custom properties and the dark class follows the mode", () => {
  const root = document.createElement("div");
  applyTokens(tokens, "dark", root);
  expect(root.style.getPropertyValue("--xh-accent")).toBe("#d");
  expect(root.style.getPropertyValue("--xh-series-2")).toBe("#2");
  expect(root.style.getPropertyValue("--xh-waterfall-baseline")).toBe("#5");
  expect(root.style.getPropertyValue("--xh-category-prompt")).toBe("#p");
  expect(root.style.getPropertyValue("--xh-font-mono")).toBe("Menlo");
  expect(root.classList.contains("dark")).toBe(true);
  applyTokens(tokens, "light", root);
  expect(root.style.getPropertyValue("--xh-accent")).toBe("#l");
  expect(root.classList.contains("dark")).toBe(false);
});
