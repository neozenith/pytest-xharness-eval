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
import { defineConfig, type Plugin } from "vitest/config";
import type { PreviewServer, ViteDevServer } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";
import sirv from "sirv";

const INLINE_MARKER = "<!--XHARNESS_INLINE_DATA-->";

/**
 * Serve `XH_CAPTURED` — the project's `.xharness_eval_cache` root (ADR 0032) — at `/`
 * under the dev *and* preview servers. The shipped page sits at `<cache>/report/` beside
 * `index.json`, but here the SPA is served at `/`, so its sibling fetches (`index.json`,
 * `report.tokens.json`) are rewritten into `report/`; the index rows' `../results/…`
 * paths resolve to `/results/…`, which the same mount serves. A pre-0032 captured
 * directory (its `index.json` at the top level) still works unrewritten.
 */
function captured(): Plugin {
  const dir = process.env.XH_CAPTURED ? path.resolve(process.env.XH_CAPTURED) : "";
  const SIBLINGS = ["/index.json", "/report.tokens.json", "/XHARNESS-REPORT-GLOSSARY.md"];
  const attach = (server: ViteDevServer | PreviewServer) => {
    if (!dir) {
      server.config.logger.warn("XH_CAPTURED is unset: the page will have no data. `make ui-dev CAPTURED=<cache dir>`.");
      return;
    }
    if (!existsSync(path.join(dir, "report", "index.json")) && !existsSync(path.join(dir, "index.json"))) {
      server.config.logger.warn(`${dir} has no report/index.json; run the evals or the replay first.`);
    }
    server.middlewares.use((req, _res, next) => {
      const url = (req.url ?? "").split("?")[0];
      if (SIBLINGS.includes(url) && !existsSync(path.join(dir, url.slice(1))) && existsSync(path.join(dir, "report", url.slice(1)))) {
        req.url = `/report${url}`;
      }
      next();
    });
    server.middlewares.use(sirv(dir, { dev: true, etag: true, extensions: [] }));
  };
  return {
    name: "xharness-captured",
    configureServer(server) {
      if (process.env.VITEST) return;
      attach(server);
    },
    configurePreviewServer(server) {
      attach(server);
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

export default defineConfig(({ mode }) => ({
  plugins: [react(), captured(), marker(), viteSingleFile({ removeViteModuleLoader: true })],
  // tamagui reads `process.env.*` at module scope; the build replaces those statically but
  // the dev server serves them raw, which threw `process is not defined` on a blank page.
  // The specific NODE_ENV define wins over the catch-all empty object.
  define: {
    "process.env.NODE_ENV": JSON.stringify(mode === "production" ? "production" : "development"),
    "process.env": "({})",
  },
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
      // tamagui's web build touches react-native-web only for `Linking`; the shim keeps RN out of the bundle
      "react-native-web": path.resolve(import.meta.dirname, "./src/shims/react-native-web.ts"),
    },
  },
  build: { outDir: "dist", emptyOutDir: true, assetsInlineLimit: 1e9, cssCodeSplit: false, reportCompressedSize: false },
  // `include` keeps Vitest out of `e2e/` (those *.spec.ts files are Playwright's);
  // tamagui is inlined so the react-native-web alias above applies inside jsdom too.
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-polyfills.ts", "./src/test-setup.ts"],
    css: false,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    server: { deps: { inline: [/tamagui/] } },
  },
}));
