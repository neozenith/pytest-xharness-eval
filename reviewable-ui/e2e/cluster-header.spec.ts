/**
 * `table.clusters` (Panels.tsx's `ClusterTable`, rendered in `aside.right` at a fixed
 * 320px per `.body`'s grid-template-columns in src/styles.css) uses `table-layout:
 * fixed`, so a `th`/`td` pair in the same column shares one width -- but only `td` had
 * `white-space: nowrap; overflow: hidden; text-overflow: ellipsis`. A header cell with
 * no such rule, and a column narrower than one of its own header words, lets the
 * browser's default word-preserving wrap do nothing (there is nowhere to break inside
 * "internal") and the word overflows the cell outright, painting over the next column's
 * header text -- "cluster names internal cut phi" rendering as "names internaLcut".
 *
 * This is a real overflow of rendered glyphs past their own box, not a difference in
 * any element's own layout size (table-layout: fixed pins every `th`'s box regardless
 * of its content), so the two `th` boxes never actually intersect -- the assertion has
 * to compare the *rendered text*'s own rect (via a DOM Range) against the cell box that
 * is supposed to contain it, the same shape as the canvas-vs-container check in
 * graph-table-canvas.spec.ts.
 */
import { expect, test } from "@playwright/test";
import { loadFixtureGraph, routeFixtureGraph } from "./helpers";

test("no header word in table.clusters renders past its own column's right edge", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");
  await expect(page.getByTestId("header")).toBeVisible();

  const table = page.getByTestId("cluster-table");
  await expect(table).toBeVisible();
  const headerCells = table.locator("thead th");
  const count = await headerCells.count();
  expect(count, "fixture should produce the full cluster/names/internal/cut/phi header").toBe(5);

  for (let i = 0; i < count; i++) {
    const th = headerCells.nth(i);
    const label = (await th.textContent())?.trim();

    // A Range over the cell's own contents reports where its text actually paints,
    // independent of the `th` box's own (table-layout: fixed) width -- unlike the box,
    // the range's rect grows past the cell's right edge when the word can't wrap.
    const overflowPx = await th.evaluate((el) => {
      const range = document.createRange();
      range.selectNodeContents(el);
      const textRight = range.getBoundingClientRect().right;
      const cellRight = el.getBoundingClientRect().right;
      return textRight - cellRight;
    });

    expect(
      overflowPx,
      `"${label}" header text must not render past its own <th>'s right edge (would bleed into the ` +
        "next column's header, e.g. the historical \"names internaLcut\" collision)",
    ).toBeLessThanOrEqual(1);
  }
});
