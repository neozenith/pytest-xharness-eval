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
  test: {
    environment: "jsdom",
    globals: true,
    css: false,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    server: { deps: { inline: [/tamagui/] } },
  },
}));
