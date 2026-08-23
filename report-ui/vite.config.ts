/**
 * The report is one self-contained HTML file (ADR 0020, ADR 0028): every script, style and
 * font is inlined at build time so `report.py` can copy it beside the captured JSON.
 *
 * Development serves a real `captured/` directory (index.json, *.result.json, *.jsonl,
 * report.tokens.json) from the path in `XH_CAPTURED`, so the page is composed against live
 * data, never against fixtures that drift from the plugin's output.
 */
import path from "node:path";
import { existsSync } from "node:fs";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig, type Plugin } from "vitest/config";
import { viteSingleFile } from "vite-plugin-singlefile";
import sirv from "sirv";

const INLINE_MARKER = "<!--XHARNESS_INLINE_DATA-->";

/** Serve `XH_CAPTURED` at `/` under the dev server so relative fetches (`index.json`) resolve. */
function captured(): Plugin {
  const dir = process.env.XH_CAPTURED ? path.resolve(process.env.XH_CAPTURED) : "";
  return {
    name: "xharness-captured",
    configureServer(server) {
      if (process.env.VITEST) return;
      if (!dir) {
        server.config.logger.warn("XH_CAPTURED is unset: the page will have no data. `make ui-dev CAPTURED=<dir>`.");
        return;
      }
      if (!existsSync(path.join(dir, "index.json"))) {
        server.config.logger.warn(`${dir} has no index.json; run the evals or the replay first.`);
      }
      server.middlewares.use(sirv(dir, { dev: true, etag: true, extensions: [] }));
    },
  };
}

/** Keep the inline-data marker where `report.py` expects it: the first thing in <head>. */
function marker(): Plugin {
  return {
    name: "xharness-inline-marker",
    transformIndexHtml: (html) => (html.includes(INLINE_MARKER) ? html : html.replace("<head>", `<head>\n${INLINE_MARKER}`)),
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), captured(), marker(), viteSingleFile({ removeViteModuleLoader: true })],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  build: { outDir: "dist", emptyOutDir: true, assetsInlineLimit: 1e9, cssCodeSplit: false, reportCompressedSize: false },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/test-setup.ts"], css: false },
});
