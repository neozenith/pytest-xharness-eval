/**
 * e2e suite for reviewable-ui. Drives the real vite dev server against the real
 * `public/graph.json` for the "loads and renders" smoke test, and against a tiny,
 * hand-authored, fully-deterministic graph (`e2e/fixtures/graph.tiny.json`, served via
 * `page.route` interception) for every test that needs an exact node/edge/cluster count.
 * That is controlling the input, not mocking application code.
 *
 * Chromium only: this is a desktop cytoscape-canvas app, not a responsive page.
 */
import { defineConfig, devices } from "@playwright/test";

const port = 5183;

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  reporter: [["list"]],
  outputDir: "./test-results",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: `http://localhost:${port}/`,
    viewport: { width: 1440, height: 900 },
  },
  webServer: {
    command: `bunx vite --port ${port} --strictPort`,
    url: `http://localhost:${port}/`,
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
