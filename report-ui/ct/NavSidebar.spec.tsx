/**
 * `NavSidebar`: the sweep as a tree, skill → suite → harness → arm (model, split by rung, ADR
 * 0049) → session. Every level starts collapsed; the active session's ancestors open themselves;
 * the sidebar's own collapse is a viewer preference remembered in localStorage, never the route.
 *
 * The sweep (`chrome.data.sweep()`): under mermaidjs-diagrams / eval_mermaid.py / claude, one
 * model (claude-opus-5) at max, low, high and no rung, plus claude-sonnet-5 at medium; under
 * codex, gpt-5.6-sol at xhigh. The discovery skill holds one codex gpt-5.6-luna · low session.
 */
import { expect, test } from "./test";
import type { Locator, Page } from "@playwright/test";
import type { HooksConfig } from "../playwright/index";
import { NavSidebar } from "../src/components/NavSidebar";
import type { Route } from "../src/lib/route";
import { cell, index, sweep } from "./fixtures";

const OVERVIEW: Route = { view: "overview", sort: null, summarySort: null, facets: { skill: null, harness: null, model: null, effort: null }, theme: null };
const session = (sessionId: string, theme: "light" | "dark" | null = null): Route => ({
  view: "session",
  sessionId,
  turn: null,
  turnView: null,
  axis: null,
  rec: null,
  line: null,
  theme,
});

const search = (page: Page) => page.evaluate(() => location.search);
const sidebar = (page: Page) => page.locator("aside#NavSidebar");
const group = (page: Page, label: string) => sidebar(page).locator("button.nav-group", { has: page.locator(`span.truncate:text-is("${label}")`) });
const branch = (page: Page, label: string) =>
  sidebar(page).locator(".nav-branch", { has: page.locator(`> button.nav-group:has(span.truncate:text-is("${label}"))`) });
const labelsUnder = async (scope: Locator): Promise<string[]> =>
  scope.locator("button.nav-group span.truncate").evaluateAll((els) => els.map((e) => e.textContent ?? ""));

/** Open skill → suite → harness for the claude arms of the main skill. */
const openToHarness = async (page: Page, harness = "claude") => {
  await group(page, "mermaidjs-diagrams").click();
  await group(page, "eval_mermaid.py").click();
  await branch(page, "eval_mermaid.py").locator("button.nav-group", { hasText: harness }).first().click();
};

const armLabels = async (page: Page, harness = "claude"): Promise<string[]> => {
  const h = branch(page, "eval_mermaid.py").locator(".nav-branch", { has: page.locator(`> button.nav-group:has(span.truncate:text-is("${harness}"))`) });
  const all = await labelsUnder(h);
  return all.slice(1); // drop the harness's own label
};

test.describe("rendering", () => {
  test("header, glossary name, Overview link active on the overview", async ({ mount, page }) => {
    await mount(<NavSidebar index={index()} route={OVERVIEW} />);
    await expect(sidebar(page)).toHaveAttribute("data-el", "NavSidebar");
    await expect(sidebar(page)).toHaveAttribute("data-state", "open");
    await expect(sidebar(page)).toContainText("Navigate");
    await expect(sidebar(page).locator('.el[data-el="NavSidebar"]')).toHaveText("NavSidebar");
    const overview = sidebar(page).locator("a.nav-link", { hasText: "Overview" });
    await expect(overview).toHaveAttribute("href", "?");
    await expect(overview).toHaveAttribute("data-active", "true");
    expect((await sidebar(page).boundingBox())!.width).toBe(264);
  });

  test("every level starts collapsed: only the skills show", async ({ mount, page }) => {
    await mount(<NavSidebar index={index()} route={OVERVIEW} />);
    const groups = sidebar(page).locator("button.nav-group");
    expect(await labelsUnder(sidebar(page))).toEqual(["mermaidjs-diagrams", "discovery"]); // first-seen order
    for (const g of await groups.all()) await expect(g).toHaveAttribute("aria-expanded", "false");
    await expect(group(page, "mermaidjs-diagrams").locator(".count")).toHaveText("6");
    await expect(group(page, "discovery").locator(".count")).toHaveText("1");
    await expect(sidebar(page).locator("a.nav-link")).toHaveCount(1); // Overview only
  });

  test("no index: just the Overview link", async ({ mount, page }) => {
    await mount(<NavSidebar index={null} route={OVERVIEW} />);
    await expect(sidebar(page).locator("a.nav-link")).toHaveText(["Overview"]);
    await expect(sidebar(page).locator("button.nav-group")).toHaveCount(0);
  });

  test("a null skill and a null suite get placeholder branches", async ({ mount, page }) => {
    await mount(<NavSidebar index={index([cell({ skill: null, suite: null })])} route={OVERVIEW} />);
    await group(page, "(no skill)").click();
    await expect(group(page, "(no suite)")).toBeVisible();
  });

  test("a suite is named by its file, not its path", async ({ mount, page }) => {
    await mount(<NavSidebar index={index()} route={OVERVIEW} />);
    await group(page, "mermaidjs-diagrams").click();
    await expect(group(page, "eval_mermaid.py")).toBeVisible();
    await expect(sidebar(page)).not.toContainText("skills/mermaidjs-diagrams/evals");
  });

  test("the chevron rotates when a group opens", async ({ mount, page }) => {
    await mount(<NavSidebar index={index()} route={OVERVIEW} />);
    const g = group(page, "mermaidjs-diagrams");
    await expect(g.locator(".chev")).toHaveCSS("transform", "none");
    await g.click();
    await expect(g).toHaveAttribute("aria-expanded", "true");
    await expect(g.locator(".chev")).not.toHaveCSS("transform", "none");
    await g.click();
    await expect(g).toHaveAttribute("aria-expanded", "false");
  });

  test("dark mode renders on the dark theme", async ({ mount, page }) => {
    await mount<HooksConfig>(<NavSidebar index={index()} route={OVERVIEW} />, { hooksConfig: { mode: "dark" } });
    await expect(page.locator("body")).toHaveCSS("background-color", "rgb(15, 17, 23)");
    await expect(group(page, "mermaidjs-diagrams")).toHaveCSS("color", "rgb(154, 160, 176)");
  });
});

test.describe("the arm level (ADR 0049)", () => {
  test("one branch per rung, labelled `model · rung`, ladder-ordered, rung-less last", async ({ mount, page }) => {
    await mount(<NavSidebar index={index()} route={OVERVIEW} />);
    await openToHarness(page);
    // cells ran max, low, high, (none): the tree reads low, high, max, then the bare model
    expect(await armLabels(page)).toEqual(["claude-opus-5 · low", "claude-opus-5 · high", "claude-opus-5 · max", "claude-opus-5", "claude-sonnet-5 · medium"]);
    for (const label of ["claude-opus-5 · low", "claude-opus-5 · high", "claude-opus-5 · max", "claude-opus-5"]) {
      await expect(group(page, label).locator(".count")).toHaveText("1");
      await expect(group(page, label)).toHaveAttribute("aria-expanded", "false");
    }
  });

  test("models keep first-seen order; only rungs within a model are ladder-sorted", async ({ mount, page }) => {
    const cells = [
      cell({ session_id: "s1", model: "zz-model", effort: "max" }),
      cell({ session_id: "s2", model: "aa-model", effort: "high" }),
      cell({ session_id: "s3", model: "zz-model", effort: "low" }),
      cell({ session_id: "s4", model: "aa-model", effort: "xhigh" }),
      cell({ session_id: "s5", model: "zz-model", effort: "medium" }),
    ];
    await mount(<NavSidebar index={index(cells)} route={OVERVIEW} />);
    await openToHarness(page);
    expect(await armLabels(page)).toEqual(["zz-model · low", "zz-model · medium", "zz-model · max", "aa-model · high", "aa-model · xhigh"]);
  });

  test("an unknown rung sorts after the ladder and before the rung-less branch", async ({ mount, page }) => {
    const cells = [cell({ session_id: "s1", effort: null }), cell({ session_id: "s2", effort: "turbo" }), cell({ session_id: "s3", effort: "max" })];
    await mount(<NavSidebar index={index(cells)} route={OVERVIEW} />);
    await openToHarness(page);
    expect(await armLabels(page)).toEqual(["claude-opus-5 · max", "claude-opus-5 · turbo", "claude-opus-5"]);
  });

  test("two sessions at one rung share one branch", async ({ mount, page }) => {
    const cells = [cell({ session_id: "s1", effort: "high" }), cell({ session_id: "s2", effort: "high", case: "eval_other" })];
    await mount(<NavSidebar index={index(cells)} route={OVERVIEW} />);
    await openToHarness(page);
    expect(await armLabels(page)).toEqual(["claude-opus-5 · high"]);
    await expect(group(page, "claude-opus-5 · high").locator(".count")).toHaveText("2");
    await group(page, "claude-opus-5 · high").click();
    await expect(branch(page, "claude-opus-5 · high").locator("a.nav-link")).toHaveCount(2);
  });

  test("a rung-less (pre-axis) sweep keeps the bare model branch", async ({ mount, page }) => {
    await mount(<NavSidebar index={index(sweep().map((c) => ({ ...c, effort: null })))} route={OVERVIEW} />);
    await openToHarness(page);
    expect(await armLabels(page)).toEqual(["claude-opus-5", "claude-sonnet-5"]);
    await expect(sidebar(page)).not.toContainText(" · ");
  });

  test("codex arms carry their rung too", async ({ mount, page }) => {
    await mount(<NavSidebar index={index()} route={OVERVIEW} />);
    await group(page, "mermaidjs-diagrams").click();
    await group(page, "eval_mermaid.py").click();
    await group(page, "codex").click();
    await expect(group(page, "gpt-5.6-sol · xhigh")).toBeVisible();
    await group(page, "discovery").click();
    await group(page, "discovery").locator("xpath=..").locator("button.nav-group").nth(1).click();
    await group(page, "discovery").locator("xpath=..").locator("button.nav-group", { hasText: "codex" }).click();
    await expect(group(page, "gpt-5.6-luna · low")).toBeVisible();
  });

  test("a session link's title names the arm with its rung, or without one", async ({ mount, page }) => {
    await mount(<NavSidebar index={index()} route={OVERVIEW} />);
    await openToHarness(page);
    await group(page, "claude-opus-5 · low").click();
    await expect(branch(page, "claude-opus-5 · low").locator("a.nav-link")).toHaveAttribute(
      "title",
      "mermaidjs-diagrams · eval_dual_density · claude/claude-opus-5 · low · aaaaaaaa-0002",
    );
    await group(page, "claude-opus-5").click();
    await expect(branch(page, "claude-opus-5").locator("a.nav-link")).toHaveAttribute(
      "title",
      "mermaidjs-diagrams · eval_dual_density · claude/claude-opus-5 · aaaaaaaa-0004",
    );
  });
});

test.describe("the active session", () => {
  test("its ancestors, down to its rung's branch, open themselves", async ({ mount, page }) => {
    await mount(<NavSidebar index={index()} route={session("aaaaaaaa-0003")} />);
    for (const label of ["mermaidjs-diagrams", "eval_mermaid.py", "claude", "claude-opus-5 · high"]) {
      await expect(group(page, label)).toHaveAttribute("aria-expanded", "true");
    }
    for (const label of ["claude-opus-5 · low", "claude-opus-5 · max", "claude-opus-5", "claude-sonnet-5 · medium", "codex", "discovery"]) {
      await expect(group(page, label)).toHaveAttribute("aria-expanded", "false");
    }
    const link = sidebar(page).locator('a.nav-link[data-active="true"]');
    await expect(link).toHaveCount(1);
    await expect(link).toContainText("eval_dual_density");
    await expect(link.locator("code.sid")).toHaveText("aaaaaaaa");
    // the Overview link is not active inside a session
    await expect(sidebar(page).locator("a.nav-link", { hasText: "Overview" })).not.toHaveAttribute("data-active", /.*/);
  });

  test("a rung-less active session opens the bare model branch, not a rung's", async ({ mount, page }) => {
    await mount(<NavSidebar index={index()} route={session("aaaaaaaa-0004")} />);
    await expect(group(page, "claude-opus-5")).toHaveAttribute("aria-expanded", "true");
    for (const label of ["claude-opus-5 · low", "claude-opus-5 · high", "claude-opus-5 · max"]) {
      await expect(group(page, label)).toHaveAttribute("aria-expanded", "false");
    }
    await expect(sidebar(page).locator('a.nav-link[data-active="true"] code.sid')).toHaveText("aaaaaaaa");
  });

  test("a session in another skill opens that skill's path only", async ({ mount, page }) => {
    await mount(<NavSidebar index={index()} route={session("cccccccc-0002")} />);
    await expect(group(page, "discovery")).toHaveAttribute("aria-expanded", "true");
    await expect(group(page, "gpt-5.6-luna · low")).toHaveAttribute("aria-expanded", "true");
    await expect(group(page, "mermaidjs-diagrams")).toHaveAttribute("aria-expanded", "false");
  });

  test("an unknown session id opens nothing", async ({ mount, page }) => {
    await mount(<NavSidebar index={index()} route={session("does-not-exist")} />);
    for (const g of await sidebar(page).locator("button.nav-group").all()) await expect(g).toHaveAttribute("aria-expanded", "false");
  });

  test("the reader can close an auto-opened ancestor", async ({ mount, page }) => {
    await mount(<NavSidebar index={index()} route={session("aaaaaaaa-0003")} />);
    await group(page, "claude-opus-5 · high").click();
    await expect(group(page, "claude-opus-5 · high")).toHaveAttribute("aria-expanded", "false");
    await expect(sidebar(page).locator('a.nav-link[data-active="true"]')).toHaveCount(0);
    await group(page, "claude-opus-5 · high").click();
    await expect(sidebar(page).locator('a.nav-link[data-active="true"]')).toHaveCount(1);
  });

  test("lists the in-page sections, and a section click scrolls without touching the route", async ({ mount, page }) => {
    await mount<HooksConfig>(<NavSidebar index={index()} route={session("aaaaaaaa-0003")} />, { hooksConfig: { search: "?session=aaaaaaaa-0003" } });
    const sections = sidebar(page).locator("button.nav-section");
    await expect(sections).toHaveText([
      "Metadata",
      "Token waterfall",
      "Context window",
      "Reconciliation",
      "Cost by tier",
      "Skill coverage",
      "Record kinds",
      "Turns & records",
      "Final message",
    ]);
    await page.evaluate(() => {
      const spacer = document.createElement("div");
      spacer.style.height = "3000px";
      const target = document.createElement("div");
      target.id = "CostByTierPanel";
      target.style.height = "40px";
      document.body.append(spacer, target);
    });
    await expect(page.locator("#CostByTierPanel")).not.toBeInViewport();
    await sections.filter({ hasText: "Cost by tier" }).click();
    await expect(page.locator("#CostByTierPanel")).toBeInViewport();
    await expect.poll(() => search(page)).toBe("?session=aaaaaaaa-0003");
  });
});

test.describe("navigation", () => {
  test("a session link pushes ?session=<id>", async ({ mount, page }) => {
    await mount(<NavSidebar index={index()} route={OVERVIEW} />);
    await openToHarness(page);
    await group(page, "claude-opus-5 · max").click();
    const link = branch(page, "claude-opus-5 · max").locator("a.nav-link");
    await expect(link).toHaveAttribute("href", "?session=aaaaaaaa-0001");
    await link.click();
    await expect.poll(() => search(page)).toBe("?session=aaaaaaaa-0001");
    // a real history entry (push): Back returns to the page the link was clicked on
    await page.evaluate(() => history.back());
    await expect.poll(() => search(page)).toBe("");
  });

  test("links carry a forced theme through", async ({ mount, page }) => {
    await mount(<NavSidebar index={index()} route={session("aaaaaaaa-0002", "dark")} />);
    const overview = sidebar(page).locator("a.nav-link", { hasText: "Overview" });
    await expect(overview).toHaveAttribute("href", "?theme=dark");
    await group(page, "claude-opus-5 · max").click();
    await branch(page, "claude-opus-5 · max").locator("a.nav-link").click();
    await expect.poll(() => search(page)).toBe("?session=aaaaaaaa-0001&theme=dark");
  });

  test("the Overview link returns to the overview", async ({ mount, page }) => {
    await mount<HooksConfig>(<NavSidebar index={index()} route={session("aaaaaaaa-0002")} />, { hooksConfig: { search: "?session=aaaaaaaa-0002" } });
    await sidebar(page).locator("a.nav-link", { hasText: "Overview" }).click();
    await expect.poll(() => search(page)).toBe("");
  });

  test("the verdict dot tone follows the session's verdict", async ({ mount, page }) => {
    await mount(<NavSidebar index={index()} route={OVERVIEW} />);
    await openToHarness(page);
    for (const label of ["claude-opus-5 · low", "claude-opus-5 · high", "claude-opus-5"]) await group(page, label).click();
    const dot = (label: string) => branch(page, label).locator("a.nav-link > span[aria-hidden]").first();
    await expect(dot("claude-opus-5 · low")).toHaveAttribute("title", "fail");
    await expect(dot("claude-opus-5 · low")).toHaveCSS("background-color", "rgb(185, 28, 28)");
    await expect(dot("claude-opus-5 · high")).toHaveAttribute("title", "pass");
    await expect(dot("claude-opus-5 · high")).toHaveCSS("background-color", "rgb(4, 111, 81)");
    await expect(dot("claude-opus-5")).toHaveAttribute("title", "no history");
    await expect(dot("claude-opus-5")).toHaveCSS("background-color", "rgb(226, 228, 234)");
  });
});

test.describe("collapse (a remembered viewer preference)", () => {
  test("collapses to a 36px rail and back, with aria and labels following", async ({ mount, page }) => {
    await mount(<NavSidebar index={index()} route={OVERVIEW} />);
    const toggle = page.locator("#NavToggle");
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await expect(toggle).toHaveAttribute("aria-label", "collapse navigation");
    await toggle.click();
    await expect(sidebar(page)).toHaveAttribute("data-state", "collapsed");
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expect(toggle).toHaveAttribute("aria-label", "expand navigation");
    await expect(toggle).toHaveAttribute("title", "expand navigation");
    await expect(sidebar(page).locator("nav")).toHaveCount(0);
    await expect(sidebar(page)).not.toContainText("Navigate");
    await expect.poll(async () => (await sidebar(page).boundingBox())!.width).toBe(36);
    expect(await page.evaluate(() => localStorage.getItem("xharness-report-nav"))).toBe("collapsed");
    await toggle.click();
    await expect(sidebar(page)).toHaveAttribute("data-state", "open");
    await expect.poll(async () => (await sidebar(page).boundingBox())!.width).toBe(264);
    expect(await page.evaluate(() => localStorage.getItem("xharness-report-nav"))).toBe("open");
  });

  test("never writes the route", async ({ mount, page }) => {
    await mount<HooksConfig>(<NavSidebar index={index()} route={OVERVIEW} />, { hooksConfig: { search: "?effort=high" } });
    await page.locator("#NavToggle").click();
    await expect.poll(() => search(page)).toBe("?effort=high");
  });

  test("a remounted sidebar remembers it was collapsed", async ({ mount, page }) => {
    const first = await mount(<NavSidebar index={index()} route={OVERVIEW} />);
    await page.locator("#NavToggle").click();
    await first.unmount();
    await mount(<NavSidebar index={index()} route={OVERVIEW} />);
    await expect(sidebar(page)).toHaveAttribute("data-state", "collapsed");
    await expect(page.locator("#NavToggle")).toHaveAttribute("aria-expanded", "false");
  });

  test("a stored 'open' (or anything else) mounts open", async ({ mount, page }) => {
    await page.evaluate(() => localStorage.setItem("xharness-report-nav", "open"));
    await mount(<NavSidebar index={index()} route={OVERVIEW} />);
    await expect(sidebar(page)).toHaveAttribute("data-state", "open");
  });

  test("a stored 'collapsed' mounts collapsed", async ({ mount, page }) => {
    await page.evaluate(() => localStorage.setItem("xharness-report-nav", "collapsed"));
    await mount(<NavSidebar index={index()} route={OVERVIEW} />);
    await expect(sidebar(page)).toHaveAttribute("data-state", "collapsed");
  });

  test("keyboard: Enter on the toggle collapses", async ({ mount, page }) => {
    await mount(<NavSidebar index={index()} route={OVERVIEW} />);
    await page.locator("#NavToggle").focus();
    await page.keyboard.press("Enter");
    await expect(sidebar(page)).toHaveAttribute("data-state", "collapsed");
  });
});
