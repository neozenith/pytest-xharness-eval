/**
 * Shared e2e plumbing.
 *
 * The app draws its whole graph to `<canvas>` elements (cytoscape's canvas renderer),
 * so there is no per-node or per-edge DOM to assert on directly. These helpers close
 * that gap by reading pixel data back out of the canvas: locating a node by its
 * data-driven fill colour (a metric band, never a theme colour, see
 * `src/lib/metrics.ts`), counting non-background "ink" pixels as a proxy for how much
 * is drawn, and waiting for two consecutive screenshots to match as the signal that a
 * layout/re-render has settled (cytoscape exposes no DOM/testid hook for that).
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import type { Locator, Page } from "@playwright/test";
import { BAND, type BandKey } from "../src/lib/metrics";
import type { Graph } from "../src/lib/types";

/**
 * The RGB triple a metric band is drawn in, read from the app's own palette.
 *
 * A spec that finds a node by its fill colour must not spell that colour itself:
 * `src/lib/metrics.ts` owns the palette, and a copy here is a cross-file dependency no
 * compiler checks. Deriving it means a palette change either keeps the test correct or
 * breaks the import -- never leaves it silently scanning for a colour that has moved.
 */
export const bandRgb = (band: BandKey): readonly [number, number, number] => {
  const n = Number.parseInt(BAND[band].replace("#", ""), 16);
  return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff];
};

/** The canvas background colour set in `src/styles.css` (`--bg: #0b1120`). */
export const CANVAS_BG: readonly [number, number, number] = [0x0b, 0x11, 0x20];

/** The tiny, hand-authored, fully-deterministic fixture graph (see its own header). */
export const loadFixtureGraph = (): Graph =>
  JSON.parse(
    readFileSync(path.resolve(import.meta.dirname, "fixtures/graph.tiny.json"), "utf-8"),
  ) as Graph;

/**
 * Serve `graph` for every `graph.json` fetch the page makes (loadGraph busts cache with
 * a `?v=` query param, hence the wildcard). This is request interception controlling
 * the app's input, not a mock of application code.
 */
export const routeFixtureGraph = async (page: Page, graph: Graph): Promise<void> => {
  await page.route("**/graph.json*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(graph),
    });
  });
};

interface RGB {
  0: number;
  1: number;
  2: number;
}

/**
 * Wait until the container's rendered pixels stop changing between two samples. Used
 * instead of a blind `waitForTimeout`: cytoscape's layout/fit cycle has no DOM signal to
 * assert on, so this polls a bounded number of times and returns as soon as the canvas
 * is visually stable (or after the last attempt, whichever comes first).
 */
export const waitForCanvasSettled = async (
  container: Locator,
  opts: { attempts?: number; intervalMs?: number } = {},
): Promise<Buffer> => {
  // Fail fast (and with a diagnosis) instead of burning the whole test timeout inside
  // `.screenshot()`'s own visibility-wait: a zero-size container never becomes visible.
  const box = await container.boundingBox();
  if (!box || box.width === 0 || box.height === 0) {
    throw new Error(
      `[data-testid=graph-canvas] has zero size (${JSON.stringify(box)}). The canvas is not rendering ` +
        "at all: its parent `.graph-panel` has no defined height, so the child `.canvas{height:100%}` " +
        "collapses to 0 (src/components/GraphCanvas.tsx + src/styles.css). This looks like an app defect, not a test bug.",
    );
  }
  const attempts = opts.attempts ?? 30;
  const intervalMs = opts.intervalMs ?? 100;
  let prev: Buffer | null = null;
  for (let i = 0; i < attempts; i++) {
    const shot = await container.screenshot({ timeout: 5_000 });
    if (prev && prev.equals(shot)) return shot;
    prev = shot;
    await container.page().waitForTimeout(intervalMs);
  }
  return prev!;
};

/**
 * Find the on-screen centre of the (assumed unique) node rendered in `rgb`, by scanning
 * every canvas inside `container` for matching pixels and averaging their positions.
 * Coordinates are returned in CSS/viewport pixels, ready for `page.mouse.click`.
 *
 * Requires near-opaque alpha (>= `minAlpha`), not just a colour match: a compound
 * cluster's tint (`"background-opacity": 0.1` in GraphCanvas.tsx) is drawn in the same
 * BAND colour as a node's solid fill, over an otherwise-transparent canvas, so its
 * pixels carry that same RGB at low alpha across a much bigger area. Matching colour
 * alone finds that wash, not the node; requiring near-full opacity finds the node.
 */
export const findNodeCenterByColor = async (
  container: Locator,
  rgb: RGB,
  tol = 20,
  minAlpha = 200,
): Promise<{ x: number; y: number } | null> =>
  container.evaluate(
    (el, { rgb, tol, minAlpha }) => {
      const canvases = Array.from(el.querySelectorAll("canvas"));
      let sx = 0;
      let sy = 0;
      let count = 0;
      for (const c of canvases) {
        const rect = c.getBoundingClientRect();
        const ctx = c.getContext("2d");
        if (!ctx || c.width === 0 || c.height === 0) continue;
        const scaleX = rect.width / c.width;
        const scaleY = rect.height / c.height;
        const data = ctx.getImageData(0, 0, c.width, c.height).data;
        const step = 2;
        for (let y = 0; y < c.height; y += step) {
          for (let x = 0; x < c.width; x += step) {
            const i = (y * c.width + x) * 4;
            const r = data[i] ?? 0;
            const g = data[i + 1] ?? 0;
            const b = data[i + 2] ?? 0;
            const a = data[i + 3] ?? 0;
            if (a < minAlpha) continue;
            if (Math.abs(r - rgb[0]) > tol || Math.abs(g - rgb[1]) > tol || Math.abs(b - rgb[2]) > tol) continue;
            sx += rect.left + x * scaleX;
            sy += rect.top + y * scaleY;
            count += 1;
          }
        }
      }
      if (count === 0) return null;
      return { x: sx / count, y: sy / count };
    },
    { rgb, tol, minAlpha },
  );

/**
 * Sum every alpha byte across every canvas inside `container`. Cytoscape's canvas
 * renderer draws edges, arrowheads and node fills all onto the same layer with partial
 * opacity and anti-aliasing (edges here are 0.8-3.5px wide, `opacity: 0.75`), so a
 * naive "count pixels that differ from the background colour by some tolerance" is too
 * coarse: a sub-pixel-wide line can fall entirely between sample points, or blend into
 * a colour that still reads as "close enough to background". Total alpha coverage does
 * not have that blind spot -- removing a drawn edge strictly lowers the total alpha
 * ink in its footprint, confirmed empirically (see this file's git history / the final
 * report) even where the exact same *set* of touched pixels stays identical.
 */
export const canvasAlphaSum = async (container: Locator): Promise<number> =>
  container.evaluate((el) => {
    const canvases = Array.from(el.querySelectorAll("canvas"));
    let sum = 0;
    for (const c of canvases) {
      const ctx = c.getContext("2d");
      if (!ctx || c.width === 0 || c.height === 0) continue;
      const data = ctx.getImageData(0, 0, c.width, c.height).data;
      for (let i = 3; i < data.length; i += 4) sum += data[i] ?? 0;
    }
    return sum;
  });

/**
 * Set a native `<input type="range">`'s value through its property setter (bypassing
 * the instance setter React installs) and fire `input`/`change`, so a controlled range
 * slider actually re-renders. Playwright's `fill()` does not reliably drive range
 * inputs; this is the standard workaround for a React-controlled range element.
 */
export const setRangeValue = async (locator: Locator, value: number): Promise<void> => {
  await locator.evaluate((el, v) => {
    const input = el as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    setter?.call(input, String(v));
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }, value);
};
