/**
 * reviewable-ui renders the tree-sitter call graph with the maintainability metrics
 * layered over it. Unlike report-ui it is NOT a single inlined file: the graph JSON is
 * hundreds of kilobytes and grows with the codebase, so it is fetched at runtime and
 * the page stays small.
 *
 * `RU_GRAPH` points at a graph.json produced by
 * docs/plans/maintainability/tools/graphdata.py. Without it the app falls back to
 * `public/graph.json`, which is what `make reviewable-data` writes.
 */
import path from "node:path";
import { existsSync, readFileSync } from "node:fs";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vitest/config";
import type { PreviewServer, ViteDevServer } from "vite";
import { storybookTest } from "@storybook/addon-vitest/vitest-plugin";
import { playwright } from "@vitest/browser-playwright";

/** Serve a graph.json from anywhere on disk at /graph.json, ahead of public/. */
function graphFile(): Plugin {
  const file = process.env.RU_GRAPH ? path.resolve(process.env.RU_GRAPH) : "";
  const attach = (server: ViteDevServer | PreviewServer) => {
    if (!file) return;
    if (!existsSync(file)) {
      server.config.logger.warn(
        `RU_GRAPH=${file} does not exist; falling back to public/graph.json`,
      );
      return;
    }
    server.middlewares.use((req, res, next) => {
      if ((req.url ?? "").split("?")[0] !== "/graph.json") return next();
      res.setHeader("Content-Type", "application/json");
      res.setHeader("Cache-Control", "no-store");
      res.end(readFileSync(file));
    });
  };
  return {
    name: "reviewable-graph",
    configureServer(server) {
      if (process.env.VITEST) return;
      attach(server);
    },
    configurePreviewServer: attach,
  };
}

export default defineConfig(({ mode }) => ({
  plugins: [react(), graphFile()],
  // tamagui reads `process.env.*` at module scope; the dev server serves those raw,
  // which throws `process is not defined` on a blank page without these defines.
  define: {
    "process.env.NODE_ENV": JSON.stringify(
      mode === "production" ? "production" : "development",
    ),
    "process.env": "({})",
  },
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
      "react-native-web": path.resolve(
        import.meta.dirname,
        "./src/shims/react-native-web.ts",
      ),
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
  /*
   * Two projects, not one implicit config: Vitest 4 runs every `test.projects`
   * entry unless a project is named on the CLI, so the old single-project shape
   * (`vitest run` == the unit suite) would silently start spinning up a headless
   * browser for `bun run test` the moment a second project appeared here. `test`
   * pins to `--project=unit` and `test:a11y` to `--project=storybook` in
   * package.json so each gate command keeps meaning exactly one thing.
   *
   * "storybook" renders every *.stories.tsx through a real headless Chromium and
   * runs .storybook/preview.ts's a11y `test: "error"` parameters against it —
   * that is what makes `test:a11y` scan something instead of matching zero
   * projects (the bug this config exists to fix).
   */
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: "unit",
          environment: "jsdom",
          globals: true,
          css: false,
          include: ["src/**/*.{test,spec}.{ts,tsx}"],
          server: { deps: { inline: [/tamagui/] } },
        },
      },
      {
        extends: true,
        plugins: [
          storybookTest({
            configDir: path.resolve(import.meta.dirname, ".storybook"),
          }),
        ],
        test: {
          name: "storybook",
          // No custom `setupFiles` here on purpose. `@storybook/addon-vitest` (since
          // Storybook 10.3) auto-provisions project annotations -- composing every
          // configured addon's preview module (including `@storybook/addon-a11y`'s
          // `afterEach`, the hook that actually runs axe and fails the test) with this
          // project's own `.storybook/preview.ts` -- unless it finds a setup file that
          // already calls `setProjectAnnotations`. Adding one here would be pure
          // redundant surface: confirmed by temporarily deleting the custom setup file
          // this project briefly carried and re-running the mutation proof below --
          // the auto-injected path caught it identically, so it was never load-bearing.
          //
          // The real historical bug was in `.storybook/preview.ts`: it disabled the AA
          // `color-contrast` rule in favour of AAA-only `color-contrast-enhanced`, whose
          // `minThreshold` escape hatch silently *passes* any contrast ratio below 4.5
          // (axe-core assumes a reading that low likely misdetected the background) --
          // exactly the range a severe failure lands in. `test:a11y` reported "23 passed
          // (23)" against an injected ~1.97:1-contrast paragraph until `color-contrast`
          // was re-enabled. See `.storybook/preview.ts` for the full account and the
          // axe-core source citation.
          browser: {
            enabled: true,
            headless: true,
            provider: playwright({}),
            instances: [{ browser: "chromium" }],
          },
        },
      },
    ],
  },
}));
