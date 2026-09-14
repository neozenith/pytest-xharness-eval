/**
 * Design-review round 3, findings #1 and #2.
 *
 * Both existing lede tests in `review.spec.ts` only ever exercise the default,
 * fully-unfiltered fixture ("showing 60 of 60") -- that coverage SHAPE, not a
 * missing assertion, is what let a whole-graph fact ("most-called definition")
 * read as if it described the current view under a language filter, a
 * zero-match search, or the node cap. This file is the three narrowed states the
 * reviewer used to catch it, kept apart from `review.spec.ts` so the gap in what
 * gets exercised cannot recur by silent omission the same way twice.
 *
 * It also covers finding #2 (the `Detail` panel's 12-row jump-list cap, which the
 * reviewer could not reproduce on this fixture -- its highest real degree is well
 * under 12 -- and flagged as unverified): confirmed real by inspection, verified
 * here by injecting enough synthetic callers to cross it.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { loadFixtureGraph, routeFixtureGraph, setRangeValue } from "./helpers";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag2aaa"];

/** A fresh copy of a GraphNode-shaped filler, so each test mutates its own graph. */
const fillerNode = (id: string, overrides: Partial<import("../src/lib/types").GraphNode> = {}) => ({
  id,
  name: id,
  lang: "python",
  root: "fixture_py",
  folder: "fixture_py/synthetic",
  file: "fixture_py/synthetic/filler.py",
  cls: null,
  line: 1,
  nloc: 5,
  depth: 1,
  isMethod: false,
  leverage: 0,
  callSites: 0,
  fanOut: 0,
  ...overrides,
});

test("a language filter that excludes the most-called definition still names it, scoped to the loaded graph, with a caveat", async ({ page }) => {
  const graph = loadFixtureGraph();
  await routeFixtureGraph(page, graph);
  await page.goto("/");
  await expect(page.getByTestId("shown")).toContainText("showing 60 of 60");

  // TargetFn is python; unticking that language is the reviewer's exact repro.
  await page.getByTestId("controls").getByRole("checkbox", { name: "python" }).uncheck();
  await expect(page.getByTestId("shown")).toContainText("showing 16 of 16");

  // The accessible table -- the reviewer's other observation -- really does drop it.
  await page.getByRole("button", { name: "View graph as table" }).click();
  await expect(
    page.locator("[data-testid=graph-table] tbody tr", { hasText: "TargetFn" }),
  ).toHaveCount(0);

  const lede = page.getByTestId("lede");
  // The whole-graph fact survives the filter -- that is the point of keeping it --
  // but it must say whose scope it is in, not read as a claim about this view.
  await expect(lede).toContainText("Most-called definition in the loaded graph");
  await expect(lede).toContainText("TargetFn");
  await expect(lede).toContainText("3 callers, 3 call sites");

  const notice = page.getByTestId("lede-off-slice");
  await expect(notice).toBeVisible();
  await expect(notice).toContainText("Not drawn in the current view");
  await expect(notice).toContainText("a filter excludes it");

  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

test("a search matching nothing leaves the lede with no numeric claim to make", async ({ page }) => {
  await routeFixtureGraph(page, loadFixtureGraph());
  await page.goto("/");

  await page.getByTestId("search").fill("zzznomatchxyz");
  await expect(page.getByTestId("shown")).toContainText("showing 0 of 0");

  const lede = page.getByTestId("lede");
  // The failure this closes: before the fix, this exact state still rendered
  // "Most-called definition: TargetFn -- 3 callers, 3 call sites" over zero rows,
  // canvas or table. Zero shown must mean zero confident numbers, full stop.
  await expect(lede).not.toContainText("TargetFn");
  await expect(lede).not.toContainText("caller");
  await expect(lede).not.toContainText("call site");
  await expect(lede).toContainText("No definitions are in the current view");
  await expect(lede).toContainText("0 of 0");

  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

test("the node cap excluding the most-called definition names the cap, not a filter", async ({ page }) => {
  const graph = loadFixtureGraph();
  // TargetFn leads every metric already on the graph's own 60 nodes (leverage,
  // callSites and fanOut are all its own personal maximum), so no cap on this
  // fixture can push it out while colouring by any of those -- the cap only ever
  // drops 10 of the 60 (the slider's minimum step), and TargetFn is never among
  // the bottom 10 of anything it already leads. 55 synthetic nodes ranked above it
  // on `fanOut` (a metric TargetFn does NOT lead once these exist) is what makes
  // the cap actually bite on it, the same way `Controls`' own cap slider would if
  // a real codebase had that many higher-fan-out definitions.
  const synthetic = Array.from({ length: 55 }, (_, i) => fillerNode(`synthetic-${i}`, { fanOut: 9 }));
  graph.nodes = [...graph.nodes, ...synthetic];
  await routeFixtureGraph(page, graph);
  await page.goto("/");

  await page.getByTestId("metric").selectOption("fanOut");
  await setRangeValue(page.getByTestId("limit"), 50);
  await expect(page.getByTestId("shown")).toContainText("hidden by the 50-node cap");

  const lede = page.getByTestId("lede");
  await expect(lede).toContainText("Most-called definition in the loaded graph");
  await expect(lede).toContainText("TargetFn");

  const notice = page.getByTestId("lede-off-slice");
  await expect(notice).toBeVisible();
  await expect(notice).toContainText("Not drawn in the current view");
  await expect(notice).toContainText("outside the node cap");

  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

test("a node with more than 12 callers gets a named remainder, not a silent drop", async ({ page }) => {
  const graph = loadFixtureGraph();
  // The fixture's own highest degree is well under 12 (the reviewer's own note on
  // why it could not reproduce this finding); 15 synthetic callers into TargetFn is
  // the minimum needed to cross the render cap and exercise the fix at all.
  const callers = Array.from({ length: 15 }, (_, i) => fillerNode(`caller-synth-${i}`));
  graph.nodes = [...graph.nodes, ...callers];
  graph.edges = [
    ...graph.edges,
    ...callers.map((c) => ({ source: c.id, target: "fixture_py/pkg_a/mod1.py:1", sites: 1 })),
  ];
  await routeFixtureGraph(page, graph);
  await page.goto("/");

  await page.getByRole("button", { name: "View graph as table" }).click();
  await page
    .locator("[data-testid=graph-table] tbody tr", { hasText: "TargetFn" })
    .getByRole("button", { name: "Select" })
    .click();

  const detail = page.getByTestId("detail");
  await expect(detail).toContainText("TargetFn");
  // 3 original callers + 15 synthetic = 18: the heading was already honest about
  // this count before the fix. What was missing is any sign the list below it
  // stops short of it.
  await expect(detail).toContainText("Called by (18)");
  await expect(page.locator("[data-testid=callers-list] > li")).toHaveCount(13); // 12 links + 1 "more" row
  await expect(page.getByTestId("callers-more")).toContainText("+6 more, not shown here");

  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});
