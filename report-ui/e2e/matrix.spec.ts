/**
 * The singular matrix sweep: every deeplink permutation of the SPA (from
 * `src/lib/permutations.ts`, driven by the captured data itself) gets a full page load,
 * a settled-state screenshot, a console transcript that must contain no errors, and the
 * network timings of the load — all under `tmp/e2e/matrix/<slug>/`.
 *
 * `XH_E2E_TIER=small|medium|large` (default large) constrains each matrix dimension to a
 * tier of its values — small is the inner loop, large the full covering matrix — and
 * `XH_E2E_SAMPLE=<n>` further downsamples to an evenly spaced sample.
 */
import path from "node:path";
import { expect, test } from "@playwright/test";
import { assertUniqueSlugs, enumeratePermutations, TIERS, type Permutation, type TierName } from "../src/lib/permutations";
import { collectConsole, loadCaptured, networkTimings, OUT_ROOT, settle, writeArtifacts } from "./helpers";

const TEST_NAME = "matrix";

function sample(perms: Permutation[]): Permutation[] {
  const n = Number(process.env.XH_E2E_SAMPLE ?? 0);
  if (!n || n >= perms.length) return perms;
  const step = perms.length / n;
  const picked = new Map<string, Permutation>();
  for (let i = 0; i < n; i++) {
    const p = perms[Math.min(Math.floor(i * step), perms.length - 1)]!;
    picked.set(p.slug, p);
  }
  return [...picked.values()];
}

test("matrix", async ({ page, request, baseURL }) => {
  test.setTimeout(45 * 60_000);
  const { index, results } = await loadCaptured(request, baseURL!);
  const tierName = (process.env.XH_E2E_TIER || "large") as TierName;
  const tier = TIERS[tierName];
  if (!tier) throw new Error(`XH_E2E_TIER must be small, medium or large, not "${tierName}"`);
  const all = enumeratePermutations(index, results, tier);
  assertUniqueSlugs(all);
  const perms = sample(all);

  const consoleEntries = collectConsole(page);
  const failures: { slug: string; errors: string[] }[] = [];
  const runs: { slug: string; search: string; ok: boolean; wall_ms: number; load_event_ms: unknown }[] = [];

  for (const perm of perms) {
    await test.step(perm.slug, async () => {
      consoleEntries.length = 0;
      const started = Date.now();
      const url = `${baseURL}${perm.search}`;
      // a same-URL hash change would not reload the document: blank first, so every
      // permutation is a genuine full page load with its own network timings
      await page.goto("about:blank");
      await page.goto(url, { waitUntil: "load" });
      await settle(page);

      const errors = consoleEntries.filter((e) => e.type === "error" || e.type === "pageerror").map((e) => `${e.type}: ${e.text} (${e.location})`);
      const network = await networkTimings(page);
      const dir = path.join(OUT_ROOT, TEST_NAME, perm.slug);
      await page.screenshot({ path: path.join(dir, "screenshot.png"), fullPage: true, animations: "disabled" });
      // the above-the-fold view at real scale: what a reviewer actually judges
      await page.screenshot({ path: path.join(dir, "viewport.png"), animations: "disabled" });
      writeArtifacts(dir, {
        "console.json": consoleEntries.slice(),
        "network.json": network,
        "info.json": { ...perm, url, errors, wall_ms: Date.now() - started },
      });

      runs.push({
        slug: perm.slug,
        search: perm.search,
        ok: errors.length === 0,
        wall_ms: Date.now() - started,
        load_event_ms: (network as { summary?: { load_event_ms?: unknown } }).summary?.load_event_ms,
      });
      if (errors.length) failures.push({ slug: perm.slug, errors });
      expect.soft(errors, `console errors at ${perm.slug} (${url})`).toEqual([]);
    });
  }

  writeArtifacts(path.join(OUT_ROOT, TEST_NAME), {
    "summary.json": {
      captured: index.captured,
      tier: tier.name,
      permutations_total: all.length,
      permutations_swept: perms.length,
      failures,
      runs,
    },
  });
  expect(failures, `permutations with console errors: ${failures.map((f) => f.slug).join(", ")}`).toEqual([]);
});
