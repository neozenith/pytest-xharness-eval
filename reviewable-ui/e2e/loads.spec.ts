/**
 * The one test that drives the REAL graph.json (`public/graph.json`, written by
 * `make reviewable-data`) rather than the deterministic fixture. Every other spec in
 * this suite needs exact counts and uses `e2e/fixtures/graph.tiny.json` instead; this
 * one just proves the real app boots against real, current, project-shaped data.
 */
import { expect, test } from "@playwright/test";

test("loads the real graph and renders header, canvas and cluster table", async ({ page }) => {
  await page.goto("/");

  const header = page.getByTestId("header");
  await expect(header).toBeVisible();
  await expect(header).toContainText("definitions");
  await expect(header).toContainText("edges");
  await expect(header).toContainText("call sites");
  await expect(header).toContainText("orphans");
  await expect(header).toContainText("resolved");
  await expect(header).toContainText("max depth");

  const canvases = page.locator("[data-testid=graph-canvas] canvas");
  await expect(canvases.first()).toBeAttached();
  expect(await canvases.count()).toBeGreaterThan(0);

  const rows = page.locator("[data-testid=cluster-table] tbody tr");
  await expect(rows.first()).toBeAttached();
  expect(await rows.count()).toBeGreaterThan(0);

  // The real graph is bigger than the default node cap, so the note reads as the
  // "N of Total definitions are hidden by the cap" warning rather than "showing X of Y".
  await expect(page.getByTestId("shown")).toContainText(/definitions|showing \d+ of \d+/);
});
