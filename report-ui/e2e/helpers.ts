/**
 * Shared e2e plumbing: load the captured data the way the page does, wait for a route to
 * fully settle, and persist one permutation's evidence (screenshot, console log, network
 * timings) under `tmp/e2e/<test>/<slug>/` — the concise, precise artifact trail a human and
 * an agent can both point at when naming a bug ("look at matrix/<slug>").
 */
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import type { APIRequestContext, Page } from "@playwright/test";
import type { Index, RunResult } from "../src/lib/types";

export const OUT_ROOT = process.env.XH_E2E_OUT ?? path.resolve(import.meta.dirname, "../../tmp/e2e");

export interface ConsoleEntry {
  type: string;
  text: string;
  location: string;
}

/** Everything the page would fetch: the index plus every cell's result. */
export async function loadCaptured(request: APIRequestContext, baseURL: string): Promise<{ index: Index; results: Record<string, RunResult> }> {
  const indexRes = await request.get("index.json");
  if (!indexRes.ok()) throw new Error(`index.json: HTTP ${indexRes.status()} — is XH_CAPTURED set to the cache directory?`);
  const index = (await indexRes.json()) as Index;
  const results: Record<string, RunResult> = {};
  // Rows carry paths relative to <cache>/report/ (ADR 0032), where the shipped page sits.
  const reportBase = new URL("report/", baseURL);
  for (const cell of index.cells) {
    const res = await request.get(new URL(cell.result, reportBase).toString());
    if (res.ok()) results[cell.session_id] = (await res.json()) as RunResult;
  }
  return { index, results };
}

/** Attach console + page-error collectors; the returned array grows as the page logs. */
export function collectConsole(page: Page): ConsoleEntry[] {
  const entries: ConsoleEntry[] = [];
  page.on("console", (msg) => {
    const loc = msg.location();
    entries.push({ type: msg.type(), text: msg.text(), location: `${loc.url}:${loc.lineNumber}:${loc.columnNumber}` });
  });
  page.on("pageerror", (err) => {
    entries.push({ type: "pageerror", text: String(err), location: "" });
  });
  return entries;
}

/**
 * The page is settled when the route's view is mounted, every started data load has
 * finished (`window.__XH_PENDING__ === 0`), and no `[data-xh-loading]` placeholder is
 * left. Two animation frames then flush the final paint.
 */
export async function settle(page: Page): Promise<void> {
  await page.waitForFunction(() => {
    const pending = window.__XH_PENDING__ ?? 0;
    const mounted = document.querySelector("[data-el='SweepOverview'], [data-el='SessionView']");
    const loading = document.querySelector("[data-xh-loading]");
    return pending === 0 && mounted !== null && loading === null;
  });
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve(null)))));
}

/** Navigation + resource timings, plus the headline durations a human scans first. */
export async function networkTimings(page: Page): Promise<Record<string, unknown>> {
  return page.evaluate(() => {
    const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
    const resources = performance.getEntriesByType("resource") as PerformanceResourceTiming[];
    return {
      summary: {
        dom_content_loaded_ms: nav ? Math.round(nav.domContentLoadedEventEnd - nav.startTime) : null,
        load_event_ms: nav ? Math.round(nav.loadEventEnd - nav.startTime) : null,
        resource_count: resources.length,
        resource_transfer_bytes: resources.reduce((sum, r) => sum + (r.transferSize || 0), 0),
        slowest_resources: [...resources]
          .sort((a, b) => b.duration - a.duration)
          .slice(0, 5)
          .map((r) => ({ name: r.name, duration_ms: Math.round(r.duration) })),
      },
      navigation: nav ? nav.toJSON() : null,
      resources: resources.map((r) => r.toJSON()),
    };
  });
}

export function writeArtifacts(dir: string, files: Record<string, unknown>): void {
  mkdirSync(dir, { recursive: true });
  for (const [name, value] of Object.entries(files)) {
    writeFileSync(path.join(dir, name), typeof value === "string" ? value : JSON.stringify(value, null, 1));
  }
}
