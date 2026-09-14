/**
 * Boundary switching. The fixture graph (`e2e/fixtures/graph.tiny.json`) was built so
 * every level partitions its 60 nodes into a different, exact cluster count: 2
 * languages, 3 folders, 6 files, 12 (file, class) pairs. Switching `[data-testid=level]`
 * must move the cluster table between those exact counts.
 */
import { expect, test } from "@playwright/test";
import { loadFixtureGraph, routeFixtureGraph } from "./helpers";

const EXPECTED_CLUSTER_ROWS: Record<string, number> = {
  language: 2,
  folder: 3,
  file: 6,
  class: 12,
};

test("switching the boundary changes the cluster table", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");
  await expect(page.getByTestId("header")).toBeVisible();

  const rows = page.locator("[data-testid=cluster-table] tbody tr");

  for (const [level, count] of Object.entries(EXPECTED_CLUSTER_ROWS)) {
    await page.getByTestId("level").selectOption(level);
    await expect(rows).toHaveCount(count);
  }
});
