/**
 * `App`: the whole page shell. The index comes from `hooksConfig.inline` (as `report.py --inline`
 * embeds it), the route from `hooksConfig.search`; navigation is `pushState`, so the browser's own
 * back and forward walk it. Without an inline payload the page fetches `index.json` from beside
 * itself, and a failed fetch must say so rather than spin.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import type { Page } from "@playwright/test";
import { App } from "../src/App";
import { cell, inline, sweep } from "./fixtures";

const search = (page: Page) => page.evaluate(() => location.search);
const isDark = (page: Page) => page.evaluate(() => document.documentElement.classList.contains("dark"));
const row = (page: Page, sid: string) => page.locator(`#SessionTable tr[data-sid='${sid}'] td[data-k='case']`);

test("with an inline index the overview renders under the report header", async ({ mount, page }) => {
  await mount(<App />, { hooksConfig: { inline: inline() } });
  await expect(page.locator("#SweepOverview")).toBeVisible();
  await expect(page.locator("#SessionTable tbody tr.SessionRow")).toHaveCount(7);
  await expect(page.locator("#ReportTitle")).toContainText("xharness eval report");
  await expect(page.locator("#ReportTitleEffort")).toHaveCount(0);
  await expect(page.locator("#ReportMeta")).toContainText("7 session(s)");
  await expect(page.locator("#ReportMeta")).toContainText("2 skills: discovery, mermaidjs-diagrams");
  await expect(page.locator("#ReportMeta")).toContainText("· inline");
  await expect(page.locator("[data-xh-loading='index']")).toHaveCount(0);
});

test("a row click pushes the session; back and forward walk between the two views", async ({ mount, page }) => {
  await mount(<App />, { hooksConfig: { inline: inline() } });
  await row(page, "aaaaaaaa-0001").click();
  await expect.poll(() => search(page)).toBe("?session=aaaaaaaa-0001");
  await expect(page.locator("#SessionView")).toBeVisible();
  await expect(page.locator("#SweepOverview")).toHaveCount(0);
  await expect(page.locator("#SessionTitle")).toContainText("eval_dual_density · claude/claude-opus-5 · max");
  // The header tuple carries the rung.
  await expect(page.locator("#ReportTitle")).toContainText("xharness");
  await expect(page.locator("#ReportTitle")).toContainText("aaaaaaaa");
  await expect(page.locator("#ReportTitleEffort")).toHaveText("max");

  await page.goBack();
  await expect.poll(() => search(page)).toBe("");
  await expect(page.locator("#SweepOverview")).toBeVisible();
  await expect(page.locator("#SessionView")).toHaveCount(0);
  await expect(page.locator("#ReportTitle")).toContainText("xharness eval report");

  await page.goForward();
  await expect.poll(() => search(page)).toBe("?session=aaaaaaaa-0001");
  await expect(page.locator("#SessionView")).toBeVisible();
  await expect(page.locator("#ReportTitleEffort")).toHaveText("max");
});

test("a session control replaces, so back from a refined session still lands on the overview", async ({ mount, page }) => {
  await mount(<App />, { hooksConfig: { inline: inline() } });
  await row(page, "bbbbbbbb-0001").click();
  await expect(page.locator("#SessionTurnTable tbody tr.SessionTurnRow")).toHaveCount(3);
  await page.locator("#SessionTurnTable tr.SessionTurnRow[data-n='2']").click();
  await expect.poll(() => search(page)).toBe("?session=bbbbbbbb-0001&turn=2&view=summary");
  await page.locator("#ChartAxisToggle").getByText("per session-log line").click();
  await expect.poll(() => search(page)).toBe("?session=bbbbbbbb-0001&turn=2&view=summary&axis=line");
  await page.goBack();
  await expect.poll(() => search(page)).toBe("");
  await expect(page.locator("#SweepOverview")).toBeVisible();
});

test("← all sessions navigates back to the overview", async ({ mount, page }) => {
  await mount(<App />, { hooksConfig: { inline: inline(), search: "?session=cccccccc-0001" } });
  await expect(page.locator("#SessionTitle")).toContainText("eval_dual_density · codex/gpt-5.6-sol · xhigh");
  await page.locator("#SessionHeader").getByRole("link", { name: "← all sessions" }).click();
  await expect.poll(() => search(page)).toBe("");
  await expect(page.locator("#SweepOverview")).toBeVisible();
  await page.goBack();
  await expect(page.locator("#SessionView")).toBeVisible();
});

test("a rung-less session deeplink: no rung in the header or title", async ({ mount, page }) => {
  await mount(<App />, { hooksConfig: { inline: inline(), search: "?session=aaaaaaaa-0004" } });
  await expect(page.locator("#SessionView")).toBeVisible();
  await expect(page.locator("#ReportTitleEffort")).toHaveCount(0);
  const title = await page.locator("#SessionTitle").innerText();
  expect(title).not.toMatch(/claude-opus-5 · /);
  await expect(page.locator("#SessionMetaTable")).toContainText("not named: the CLI's default");
});

test("an unknown session id says so; the header keeps the report title", async ({ mount, page }) => {
  await mount(<App />, { hooksConfig: { inline: inline(), search: "?session=deadbeef" } });
  await expect(page.locator("#SessionView")).toContainText("No captured session deadbeef in this index.");
  await expect(page.locator("#ReportTitle")).toContainText("xharness eval report");
});

test("?effort=high deeplinks a filtered overview", async ({ mount, page }) => {
  const cells = [...sweep(), cell({ session_id: "aaaaaaaa-0005", effort: "high" })];
  await mount(<App />, { hooksConfig: { inline: inline(cells), search: "?effort=high" } });
  await expect(page.locator("#SessionTable tbody tr.SessionRow")).toHaveCount(2);
  await expect(page.locator("#SessionCount")).toHaveText("(2 of 8)");
  await expect(page.locator("#SummaryCount")).toHaveText("(1 group)");
  // The header counts the report, never the selection.
  await expect(page.locator("#ReportMeta")).toContainText("8 session(s)");
});

test("the theme toggle flips the page and remembers the choice", async ({ mount, page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await mount(<App />, { hooksConfig: { inline: inline() } });
  await expect(page.locator("#SweepOverview")).toBeVisible();
  await expect.poll(() => isDark(page)).toBe(false);
  await page.locator("#ThemeToggle").click();
  await expect.poll(() => isDark(page)).toBe(true);
  expect(await page.evaluate(() => localStorage.getItem("xharness-report-theme"))).toBe("dark");
  // An unforced theme stays out of the URL.
  expect(await search(page)).toBe("");
  await page.locator("#ThemeToggle").click();
  await expect.poll(() => isDark(page)).toBe(false);
  expect(await page.evaluate(() => localStorage.getItem("xharness-report-theme"))).toBe("light");
});

test("?theme=dark forces the theme, and toggling rewrites the param", async ({ mount, page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await mount(<App />, { hooksConfig: { inline: inline(), search: "?theme=dark" } });
  await expect.poll(() => isDark(page)).toBe(true);
  await page.locator("#ThemeToggle").click();
  await expect.poll(() => isDark(page)).toBe(false);
  await expect.poll(() => search(page)).toBe("?theme=light");
});

test("a forced theme rides the navigation into a session", async ({ mount, page }) => {
  await mount(<App />, { hooksConfig: { inline: inline(), search: "?theme=dark" } });
  await row(page, "aaaaaaaa-0003").click();
  await expect.poll(() => search(page)).toBe("?session=aaaaaaaa-0003&theme=dark");
  await expect.poll(() => isDark(page)).toBe(true);
  await expect(page.locator("#ReportTitleEffort")).toHaveText("high");
});

test("with no inline payload and no index.json beside the page, the error is stated", async ({ mount, page }) => {
  await page.route("**/index.json", (r) => r.fulfill({ status: 404, body: "not found" }));
  await page.route("**/report.tokens.json", (r) => r.fulfill({ status: 404, body: "not found" }));
  await mount(<App />);
  const err = page.locator("main p", { hasText: "index.json" });
  await expect(err).toContainText("index.json: Error: index.json: HTTP 404");
  await expect(err).toContainText("--xharness-report-inline");
  await expect(page.locator("[data-xh-loading='index']")).toHaveCount(0);
  await expect(page.locator("#SweepOverview")).toHaveCount(0);
  await expect(page.locator("#ReportMeta")).toHaveText("loading…");
});

test("?line= scrolls to the record inside the full page", async ({ mount, page }) => {
  await mount(<App />, { hooksConfig: { inline: inline(), search: `?session=aaaaaaaa-0001&line=8` } });
  await expect(page.locator("#SessionTurnTable tr.detail-row")).toHaveAttribute("data-n", "3");
  await expect(page.locator("#L8")).toHaveClass(/xh-target/);
  await expect(page.locator("#L8")).toBeInViewport();
});

test("a control used under ?line= keeps the turn the line opened", async ({ mount, page }) => {
  // Regression: `write` used to drop `line` and write the stored `openTurn`, which is null for a
  // turn `line=` opened, so the rewritten URL carried neither and the turn closed under the reader.
  await mount(<App />, { hooksConfig: { inline: inline(), search: `?session=aaaaaaaa-0001&line=5` } });
  const detail = page.locator("#SessionTurnTable tr.detail-row");
  await expect(detail).toHaveAttribute("data-n", "2");
  await page.locator("#RecordViewToggle").getByText("raw JSON").click();
  await expect.poll(() => search(page)).toContain("rec=raw");
  // The reader was looking at turn 2's records; switching how they render must not close them.
  await expect(detail).toHaveCount(1);
  await expect(detail).toHaveAttribute("data-n", "2");
  await expect.poll(() => search(page)).toContain("turn=2");
});

/*
 * A capture from before ADR 0049: `index.json` rows carry no `effort` key at all, and ADR 0049
 * lets a later emitter write `""` for "none named". The page folds both to null where it reads
 * the index, so neither reaches a chip, a cell, a label or the header as a value.
 */
test("a pre-axis capture (no effort key, or an empty one) renders with no rung anywhere", async ({ mount, page }) => {
  const data = inline();
  data.index.cells = data.index.cells.map((c, i) => {
    const rest: Partial<typeof c> = { ...c };
    delete rest.effort;
    return (i % 2 ? { ...rest, effort: "" } : rest) as typeof c;
  });
  await mount(<App />, { hooksConfig: { inline: data } });
  await expect(page.locator("#SessionTable tbody tr.SessionRow")).toHaveCount(7);
  await expect(page.locator(".filter-chip[data-facet='effort']")).toHaveCount(0);
  await expect(page.locator("#SweepOverview")).not.toContainText("undefined");
  const sid = data.index.cells[0]!.session_id;
  await row(page, sid).click();
  await expect.poll(() => search(page)).toBe(`?session=${sid}`);
  await expect(page.locator("#ReportTitleEffort")).toHaveCount(0);
  await expect(page.locator("#SessionTitle")).not.toContainText(" · undefined");
  await expect(page.locator("#SessionMetaTable")).toContainText("not named: the CLI's default");
});
