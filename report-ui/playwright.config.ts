/**
 * The e2e suite runs against the *built* single-file page served by `vite preview` with the
 * captured directory mounted beside it (the production contract: sibling `index.json`,
 * `*.result.json`, `*.jsonl` fetches). `XH_E2E_TARGET=dev` swaps in the hot-reloading dev
 * server for fast iteration; both need `XH_CAPTURED=<skill>/evals/captured`.
 */
import { defineConfig, devices } from "@playwright/test";

const target = process.env.XH_E2E_TARGET === "dev" ? "dev" : "preview";
const port = target === "dev" ? 5199 : 4199;

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  fullyParallel: false,
  reporter: [["list"]],
  outputDir: "./test-results",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: `http://localhost:${port}/`,
    viewport: { width: 1440, height: 900 },
  },
  webServer: {
    command: target === "dev" ? `bunx vite --port ${port} --strictPort` : `bunx vite preview --port ${port} --strictPort`,
    url: `http://localhost:${port}/`,
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
