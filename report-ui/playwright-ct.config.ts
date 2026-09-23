/**
 * Playwright Component Testing (https://playwright.dev/docs/test-components): each component
 * mounted on its own in a real Chromium, with the page's real stylesheet, Tamagui provider and
 * design tokens around it (`playwright/index.tsx`). The layer between Vitest's jsdom unit tests
 * (no layout, no CSS, no canvas) and the e2e matrix (whole page, needs a captured cache).
 *
 * No captured directory is needed: every spec builds its data with `ct/fixtures.ts`, so
 * `make ui-ct` runs on a clean checkout. The component's own props and route are the whole
 * input, which is what makes each one reviewable in isolation.
 */
import path from "node:path";
import { defineConfig, devices } from "@playwright/experimental-ct-react";
import react from "@vitejs/plugin-react";

export default defineConfig({
  testDir: "./ct",
  snapshotDir: "./ct/__snapshots__",
  outputDir: process.env.XH_CT_CACHE ? `${process.env.XH_CT_CACHE}-results` : "./test-results/ct",
  timeout: 30_000,
  fullyParallel: true,
  reporter: [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    viewport: { width: 1280, height: 800 },
    // Overridable so several suites can build and serve side by side without sharing a port or
    // a bundle directory; the defaults are what `make ui-ct` uses.
    ctPort: Number(process.env.XH_CT_PORT ?? 3199),
    ctCacheDir: process.env.XH_CT_CACHE ?? "./playwright/.cache",
    // The same resolution and defines the app build uses (vite.config.ts), so a mounted
    // component resolves `@/…` and tamagui's `process.env.*` exactly as it does in the page.
    ctViteConfig: {
      plugins: [react()],
      define: { "process.env.NODE_ENV": JSON.stringify("development"), "process.env": "({})" },
      resolve: {
        alias: {
          "@": path.resolve(import.meta.dirname, "./src"),
          "react-native-web": path.resolve(import.meta.dirname, "./src/shims/react-native-web.ts"),
        },
      },
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
