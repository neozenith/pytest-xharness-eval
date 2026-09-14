/**
 * Failure path: `/graph.json` 404s (e.g. `make reviewable-data` was never run). The app
 * must fail loudly with a usable message, never silently render an empty graph.
 */
import { expect, test } from "@playwright/test";

test("a 404 on graph.json renders a usable fatal error", async ({ page }) => {
  await page.route("**/graph.json*", async (route) => {
    await route.fulfill({ status: 404, contentType: "text/plain", body: "not found" });
  });
  await page.goto("/");

  const fatal = page.getByTestId("fatal");
  await expect(fatal).toBeVisible();
  await expect(fatal.locator("h1")).toHaveText("No graph");
  // The thrown message is `${url}: ${status} ${statusText}` (src/lib/graph.ts loadGraph).
  await expect(fatal).toContainText("404");
  await expect(fatal).toContainText("make reviewable-data");
  await expect(fatal).toContainText("RU_GRAPH=path/to/graph.json");

  // Nothing from the normal app shell should be present.
  await expect(page.getByTestId("header")).toHaveCount(0);
  await expect(page.getByTestId("graph-canvas")).toHaveCount(0);
});

test("a network error on graph.json also renders a usable fatal error", async ({ page }) => {
  await page.route("**/graph.json*", async (route) => {
    await route.abort("failed");
  });
  await page.goto("/");

  const fatal = page.getByTestId("fatal");
  await expect(fatal).toBeVisible();
  await expect(fatal).toContainText("make reviewable-data");
});
