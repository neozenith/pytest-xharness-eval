/**
 * Metric switching. Node fill/size/value is `data(colour)`/`data(size)`/`data(value)`
 * driven by the selected metric (`src/lib/metrics.ts`). The primary assertion here uses
 * the app's own accessible alternative to the canvas -- `[data-testid=graph-table]`
 * (GraphCanvas.tsx's "View graph as table") -- since it renders the very same per-node
 * `value`/`band` data the canvas draws, as plain DOM text, immune to canvas pixel work.
 *
 * A second test asserts the canvas itself visibly changes too; see its own comment for
 * why that one currently fails.
 */
import { expect, test } from "@playwright/test";
import { loadFixtureGraph, routeFixtureGraph, waitForCanvasSettled } from "./helpers";

test("switching the metric changes each node's value/band in the accessible table", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");
  await expect(page.getByTestId("header")).toBeVisible();
  await expect(page.getByTestId("metric")).toHaveValue("leverage");

  await page.getByRole("button", { name: "View graph as table" }).click();
  const targetRow = page.locator("[data-testid=graph-table] tbody tr", { hasText: "TargetFn" });
  await expect(targetRow).toBeVisible();
  // TargetFn: leverage 3 (fixture's only node above leverage 1) -> nloc 22.
  await expect(targetRow.locator("td").nth(3)).toHaveText("3");
  await expect(targetRow.locator(".band-chip")).toHaveText("high band");

  await page.getByTestId("metric").selectOption("nloc");
  await expect(targetRow.locator("td").nth(3)).toHaveText("22");
  // Asserted on BOTH metrics on purpose: leverage 3 is the top of its range and
  // nloc 22 is the middle of its, so together these pin that every metric bands
  // monotonically in magnitude. Leverage and callSites used to invert -- a large
  // leverage banded "low" -- and no test noticed, because each metric was only ever
  // checked against itself.
  await expect(targetRow.locator(".band-chip")).toHaveText("mid band");
});

test("switching the metric changes the canvas render (node colours/sizes)", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");
  await expect(page.getByTestId("header")).toBeVisible();

  const canvas = page.getByTestId("graph-canvas");
  const before = await waitForCanvasSettled(canvas);

  await page.getByTestId("metric").selectOption("nloc");
  const after = await waitForCanvasSettled(canvas);

  expect(before.equals(after), "canvas pixels should differ once nodes are coloured/sized by a different metric").toBe(false);
});
