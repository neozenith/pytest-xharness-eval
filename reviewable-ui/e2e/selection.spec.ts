/**
 * Selection. The fixture's `TargetFn` node is the only one with leverage >= 2 (band
 * "high"), with exactly 3 distinct callers and 2 callees wired in as real edges. Every
 * other node is leverage 1 ("low") or 0 ("none"), so "high" identifies exactly one node.
 * It is also, being the highest-leverage node under the default "leverage" metric, the
 * single largest glyph on screen -- locatable purely by scanning canvas pixels for its
 * unique fill colour, with no dependency on cytoscape's internal layout math.
 *
 * Two selection paths are exercised: a literal canvas tap, and the app's own
 * accessible alternative to it -- `[data-testid=graph-table]`'s per-row "Select"
 * button (GraphCanvas.tsx) -- which a keyboard or screen-reader user relies on instead.
 */
import { expect, test } from "@playwright/test";
import { bandRgb, findNodeCenterByColor, loadFixtureGraph, routeFixtureGraph, waitForCanvasSettled } from "./helpers";

/**
 * Derived from the palette, never copied from it. An earlier revision of this file held
 * the literal `#047857`; when the palette was re-derived for AAA contrast the two
 * drifted, `tsc` stayed clean, and the only symptom was a pixel scan returning null.
 * Importing the source of truth turns an uncheckable cross-file dependency into a
 * checked one -- the same reason a shared vocabulary is an enum, not a string.
 *
 * Which band it reads is deliberately NOT derived, though: that TargetFn is the
 * fixture's only "high"-band node is a fact about the fixture, and stating it here is
 * what makes this spec fail loudly if the metric's polarity ever flips again.
 */
const TARGET_FILL = bandRgb("high");

test("selecting a node (via the accessible table) populates the detail panel", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");
  await expect(page.getByTestId("header")).toBeVisible();

  await page.getByRole("button", { name: "View graph as table" }).click();
  const targetRow = page.locator("[data-testid=graph-table] tbody tr", { hasText: "TargetFn" });
  await targetRow.getByRole("button", { name: "Select" }).click();

  const detail = page.getByTestId("detail");
  await expect(detail).toContainText("TargetFn");
  await expect(detail).toContainText("3 callers, 3 sites");
  await expect(detail).toContainText("fixture_py/pkg_a/mod1.py:1");
  await expect(detail).toContainText("Called by (3)");
  await expect(detail).toContainText("Calls (2)");
  await expect(detail).toContainText("CallerA");
  await expect(detail).toContainText("CallerB");
  await expect(detail).toContainText("CallerC");
  await expect(detail).toContainText("CalleeX");
  await expect(detail).toContainText("CalleeY");

  // A caller/callee entry in the detail panel jumps the selection there too.
  await detail.getByRole("button", { name: "CallerA" }).click();
  await expect(detail).toContainText("CallerA");
  await expect(detail.locator("h3")).toHaveText("CallerA");
});

test("deselecting (toggling the table's Select button off) clears the detail panel", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");
  await expect(page.getByTestId("header")).toBeVisible();

  await page.getByRole("button", { name: "View graph as table" }).click();
  const targetRow = page.locator("[data-testid=graph-table] tbody tr", { hasText: "TargetFn" });
  await targetRow.getByRole("button", { name: "Select" }).click();
  await expect(page.getByTestId("detail")).toContainText("TargetFn");

  await targetRow.getByRole("button", { name: "Selected" }).click();
  // The empty state keeps the same `data-testid="detail"` as the populated one
  // (Panels.tsx's `Detail`), so the inspector stays addressable either way.
  await expect(page.getByTestId("detail")).toHaveText("Tap a node to inspect it.");
});

test("tapping a node on the canvas populates the detail panel", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");
  await expect(page.getByTestId("header")).toBeVisible();

  const canvas = page.getByTestId("graph-canvas");
  await waitForCanvasSettled(canvas);

  const point = await findNodeCenterByColor(canvas, TARGET_FILL);
  expect(point, "TargetFn's uniquely high-band node should be visible on the canvas").not.toBeNull();
  await page.mouse.click(point!.x, point!.y);
  await expect(page.getByTestId("detail")).toContainText("TargetFn");
});
