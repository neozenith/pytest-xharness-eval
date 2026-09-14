/**
 * Cytoscape draws into layered, absolutely-positioned `<canvas>` elements sized in raw
 * pixels at mount time (GraphCanvas.tsx); `.graph-panel` is a column flexbox where
 * `.canvas` takes `flex: 1` and its sibling `.graph-table-wrap` takes up to `max-height:
 * 42%` once "View graph as table" is toggled on (src/styles.css). Toggling the table
 * open therefore shrinks `.canvas` well after cytoscape has already sized its canvas
 * layers for the taller, table-less box -- and cytoscape's own internal ResizeObserver
 * (see its `extensions/renderer/base/load-listeners.mjs`) only self-corrects on a
 * debounced ~100ms timer, and even then only calls `resize()`, never `fit()`, so the
 * pan/zoom stays calibrated for a box that no longer exists.
 *
 * The DOM can't see any of this (the canvas is `aria-hidden`, and nothing about a
 * mis-sized <canvas> shows up as a text/attribute diff), so this file asserts on the
 * canvas layers' own bounding boxes instead of on visible text.
 */
import { expect, test } from "@playwright/test";
import {
  bandRgb,
  findNodeCenterByColor,
  loadFixtureGraph,
  routeFixtureGraph,
  waitForCanvasSettled,
} from "./helpers";

test("cytoscape's canvas layers do not bleed past the panel once the table shrinks it", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");
  await expect(page.getByTestId("header")).toBeVisible();

  const container = page.getByTestId("graph-canvas");
  await waitForCanvasSettled(container);

  await page.getByRole("button", { name: "View graph as table" }).click();

  // Polling here, rather than after a long or unbounded wait, is what actually pins the
  // regression: measured against the unfixed app, every canvas layer stays at its
  // pre-toggle pixel height through at least an 80ms window after this click, and only
  // self-corrects at cytoscape's own internal ~100ms debounce mark. A check that waited
  // past 100ms would pass even with no fix at all in this repo's own code -- it would
  // only be re-testing cytoscape's bundled behaviour, which still leaves the pan/zoom
  // stale (see the file header, and the second test below). Bounding this poll's
  // timeout below 100ms is what keeps the assertion meaningful.
  await expect
    .poll(
      async () => {
        const containerBox = await container.boundingBox();
        const canvases = await container.locator("canvas").all();
        if (!containerBox || canvases.length === 0) return Number.POSITIVE_INFINITY;
        const boxes = await Promise.all(canvases.map((c) => c.boundingBox()));
        const bottoms = boxes.map((b) => (b ? b.y + b.height : 0));
        return Math.max(...bottoms) - (containerBox.y + containerBox.height);
      },
      {
        message:
          "a cytoscape <canvas> layer's bottom edge must stay within the shrunk .canvas container's " +
          "bottom edge -- instead it is bleeding down over the accessible table and its Select buttons",
        timeout: 80,
        intervals: [5, 10, 15, 20],
      },
    )
    .toBeLessThanOrEqual(1);
});

/**
 * TargetFn is the fixture's only "high"-band node (see selection.spec.ts's own header),
 * which makes it the single largest glyph on screen and locatable purely by scanning
 * canvas pixels for its fill colour -- no dependency on cytoscape's layout math, and
 * no dependency on where the user happened to pan it to.
 */
const TARGET_FILL = bandRgb("high");

test("toggling the accessible table preserves a user's manual pan, rather than silently re-fitting", async ({
  page,
}) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");
  await expect(page.getByTestId("header")).toBeVisible();

  const container = page.getByTestId("graph-canvas");
  await waitForCanvasSettled(container);

  const before = await findNodeCenterByColor(container, TARGET_FILL);
  expect(before, "TargetFn should be visible before panning").not.toBeNull();

  // Drag from the container's empty top-left margin -- away from any node, so this
  // is cytoscape's default "drag the background to pan" gesture, not a node drag --
  // to move the viewport somewhere the last automatic `fit()` did not leave it.
  const box = await container.boundingBox();
  if (!box) throw new Error("graph-canvas has no bounding box");
  await page.mouse.move(box.x + 20, box.y + 20);
  await page.mouse.down();
  await page.mouse.move(box.x + 120, box.y + 110, { steps: 10 });
  await page.mouse.up();

  const afterPan = await findNodeCenterByColor(container, TARGET_FILL);
  expect(afterPan, "TargetFn should still be visible after panning").not.toBeNull();
  // The drag must have actually panned something, or the rest of this test would
  // only be proving a no-op.
  expect(
    Math.hypot(afterPan!.x - before!.x, afterPan!.y - before!.y),
    "the drag should have panned the viewport (and moved TargetFn) noticeably",
  ).toBeGreaterThan(30);

  await page.getByRole("button", { name: "View graph as table" }).click();

  // Give the (undebounced) ResizeObserver callback a full turn of the event loop --
  // long enough that an unconditional `fit()` would already have reframed the
  // viewport back toward the pre-pan framing, well short of cytoscape's own bundled
  // ~100ms-debounced observer (which never calls `fit()` at all -- see the file
  // header) so a pass here is not accidentally that observer's doing instead.
  await page.waitForTimeout(200);

  const afterToggle = await findNodeCenterByColor(container, TARGET_FILL);
  expect(afterToggle, "TargetFn should still be visible after the table toggle").not.toBeNull();
  expect(
    Math.hypot(afterToggle!.x - afterPan!.x, afterToggle!.y - afterPan!.y),
    "opening the table resizes .canvas, which must not re-run fit(): TargetFn should stay " +
      "exactly where the user panned it, not snap back toward the auto-fit framing",
  ).toBeLessThan(15);
});
