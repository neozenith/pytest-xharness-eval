/**
 * `SessionTable`: one row per captured session. Its whole input is `cells` and the URL, so every
 * test states a sweep (from `ct/fixtures.ts`) and, where the order matters, a `hooksConfig.search`.
 * A sort click writes the URL through `replaceRoute`; a row click pushes a session route. Both
 * are asserted on `location.search`, which is what a reader shares.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import type { Page } from "@playwright/test";
import { SessionTable } from "../src/components/SessionTable";
import { cell, sweep } from "./fixtures";

// The `when` column prints local time; pin the zone so `07:18` is `07:18` on every machine.
test.use({ timezoneId: "UTC" });

const MUTED = { light: "rgb(91, 96, 112)", dark: "rgb(154, 160, 176)" };
const NONE = "–";
const NO_MATCH = "No session matches the current filters.";

/** Every column the table can show, in order: identity, then metrics. */
const ALL_KEYS = [
  "verdict",
  "at",
  "skill",
  "case",
  "harness",
  "model",
  "effort",
  "estimated_cost_usd",
  "accumulative_billed_tokens",
  "context_window_pct",
  "turns",
  "tool_calls",
  "coverage",
  "output_tokens_per_sec",
  "wall_ms",
];

const rows = (page: Page) => page.locator("#SessionTable tbody tr.SessionRow");
const sids = (page: Page) => rows(page).evaluateAll((trs) => trs.map((tr) => tr.getAttribute("data-sid")));
const column = (page: Page, key: string) => page.locator(`#SessionTable tbody td[data-k="${key}"]`).allInnerTexts();
const heads = (page: Page) => page.locator("#SessionTable thead th").evaluateAll((ths) => ths.map((th) => th.getAttribute("data-k")));
const head = (page: Page, key: string) => page.locator(`#SessionTable thead th[data-k="${key}"]`);
const search = (page: Page) => page.evaluate(() => location.search);

/**
 * Count the History API writes from here on. `history.length` cannot tell a push from a replace
 * once a worker page has reached Chromium's 50-entry cap, so the calls themselves are counted;
 * each still runs, so the route the component reads is the real one.
 */
const spyHistory = (page: Page) =>
  page.evaluate(() => {
    const w = window as unknown as { __pushes: number; __replaces: number };
    w.__pushes = 0;
    w.__replaces = 0;
    const push = history.pushState.bind(history);
    const replace = history.replaceState.bind(history);
    history.pushState = (...args) => {
      w.__pushes += 1;
      push(...args);
    };
    history.replaceState = (...args) => {
      w.__replaces += 1;
      replace(...args);
    };
  });
const historyWrites = (page: Page) =>
  page.evaluate(() => {
    const w = window as unknown as { __pushes: number; __replaces: number };
    return { pushes: w.__pushes, replaces: w.__replaces };
  });

/** Four sessions an hour apart, listed out of time order, so the default sort has work to do. */
const timeline = () => [
  cell({ session_id: "t-2", at: "2026-09-23T02:00:00Z" }),
  cell({ session_id: "t-4", at: "2026-09-23T04:00:00Z" }),
  cell({ session_id: "t-1", at: "2026-09-23T01:00:00Z" }),
  cell({ session_id: "t-3", at: "2026-09-23T03:00:00Z" }),
];

test.describe("SessionTable: rendering", () => {
  test("renders one focusable row per cell, keyed by session id", async ({ mount, page }) => {
    await mount(<SessionTable cells={sweep()} />);
    await expect(rows(page)).toHaveCount(7);
    expect(await sids(page)).toEqual(sweep().map((c) => c.session_id));
    for (const tr of await rows(page).all()) await expect(tr).toHaveAttribute("tabindex", "0");
  });

  test("a varied sweep shows every column, identity half then metrics half", async ({ mount, page }) => {
    await mount(<SessionTable cells={sweep()} />);
    expect(await heads(page)).toEqual(ALL_KEYS);
    await expect(page.locator("#SessionTable caption")).toHaveCount(0);
  });

  test("the metrics half opens on the cost column, which draws the dividing rule", async ({ mount, page }) => {
    await mount(<SessionTable cells={sweep()} />);
    const grouped = page.locator('#SessionTable thead th[data-group="metrics"]');
    await expect(grouped).toHaveCount(1);
    await expect(grouped).toHaveAttribute("data-k", "estimated_cost_usd");
    await expect(grouped).toHaveCSS("border-left-width", "1px");
    await expect(page.locator('#SessionTable tbody td[data-group="metrics"]')).toHaveCount(7);
  });

  test("numeric columns are right-aligned; identity columns are not", async ({ mount, page }) => {
    await mount(<SessionTable cells={sweep()} />);
    await expect(page.locator('#SessionTable tbody td[data-k="turns"]').first()).toHaveCSS("text-align", "right");
    await expect(page.locator('#SessionTable tbody td[data-k="wall_ms"]').first()).toHaveClass(/num/);
    await expect(page.locator('#SessionTable tbody td[data-k="model"]').first()).not.toHaveCSS("text-align", "right");
  });

  test("prints each cell in its short form, the exact value on its title", async ({ mount, page }) => {
    await mount(
      <SessionTable cells={[cell({ session_id: "one-a" }), cell({ session_id: "one-b", case: "eval_other", harness: "codex", model: "gpt-5.6-sol" })]} />,
    );
    const first = rows(page).first();
    await expect(first.locator('td[data-k="verdict"]')).toContainText("pass");
    await expect(first.locator('td[data-k="at"] span')).toHaveText(/^23 Sept? 07:18$/);
    await expect(first.locator('td[data-k="case"] span')).toHaveText("dual_density");
    await expect(first.locator('td[data-k="case"] span')).toHaveAttribute("title", "eval_dual_density · skills/mermaidjs-diagrams/evals/eval_mermaid.py");
    await expect(first.locator('td[data-k="model"] code')).toHaveText("opus-5");
    await expect(first.locator('td[data-k="model"] code')).toHaveAttribute("title", "claude-opus-5");
    await expect(rows(page).nth(1).locator('td[data-k="model"] code')).toHaveText("5.6-sol");
    await expect(first.locator('td[data-k="accumulative_billed_tokens"] span')).toHaveText("1.5M");
    await expect(first.locator('td[data-k="accumulative_billed_tokens"] span')).toHaveAttribute("title", "1,504,090");
    await expect(first.locator('td[data-k="context_window_pct"]')).toContainText("· 12.0%");
    await expect(first.locator('td[data-k="turns"]')).toHaveText("3");
    await expect(first.locator('td[data-k="tool_calls"]')).toHaveText("14");
    await expect(first.locator('td[data-k="coverage"]')).toHaveText("2/5 · 1/2");
    await expect(first.locator('td[data-k="output_tokens_per_sec"]')).toHaveText("61.20");
    await expect(first.locator('td[data-k="wall_ms"]')).toHaveText("83.0s");
  });

  test("cost prints the estimate and the CLI's own figure as a signed drift from it", async ({ mount, page }) => {
    await mount(
      <SessionTable
        cells={[
          cell({ session_id: "drift-up" }),
          cell({ session_id: "drift-same", estimated_cost_usd: 2, harness_reported_cost_usd: 2.0005 }),
          cell({ session_id: "drift-down", estimated_cost_usd: 1, harness_reported_cost_usd: 0.9 }),
          cell({ session_id: "drift-none", harness: "codex", estimated_cost_usd: 0.5, harness_reported_cost_usd: null }),
        ]}
      />,
    );
    const cost = (sid: string) => page.locator(`#SessionTable tr[data-sid="${sid}"] td[data-k="estimated_cost_usd"]`);
    await expect(cost("drift-up")).toHaveText("$1.028+0.1%");
    await expect(cost("drift-up").locator("> span")).toHaveAttribute("title", "estimated $1.0276 · harness reported $1.0288");
    await expect(cost("drift-same").locator(".qual")).toHaveText("=");
    await expect(cost("drift-down").locator(".qual")).toHaveText("−10.0%");
    await expect(cost("drift-none")).toHaveText("$0.500");
    await expect(cost("drift-none").locator(".qual")).toHaveCount(0);
  });

  test("a missing value is the muted glyph, never zero", async ({ mount, page }) => {
    await mount(
      <SessionTable
        cells={[
          cell({ session_id: "full" }),
          cell({
            session_id: "sparse",
            skill: null,
            estimated_cost_usd: null,
            accumulative_billed_tokens: null,
            peak_context_tokens: null,
            turns: null,
            output_tokens_per_sec: null,
            wall_ms: null,
            skill_coverage: {},
          }),
        ]}
      />,
    );
    const sparse = page.locator('#SessionTable tr[data-sid="sparse"]');
    for (const key of [
      "skill",
      "estimated_cost_usd",
      "accumulative_billed_tokens",
      "context_window_pct",
      "turns",
      "coverage",
      "output_tokens_per_sec",
      "wall_ms",
    ]) {
      const glyph = sparse.locator(`td[data-k="${key}"] > span.muted`);
      await expect(glyph, key).toHaveText(NONE);
      await expect(glyph, key).toHaveCSS("color", MUTED.light);
    }
  });

  test("an empty sweep keeps the head and says why the body is empty", async ({ mount, page }) => {
    await mount(<SessionTable cells={[]} />);
    expect(await heads(page)).toEqual(ALL_KEYS);
    await expect(rows(page)).toHaveCount(0);
    const empty = page.locator("#SessionTable td.empty");
    await expect(empty).toHaveText(NO_MATCH);
    await expect(empty).toHaveAttribute("colspan", String(ALL_KEYS.length));
    await expect(empty).toHaveCSS("color", MUTED.light);
    await expect(page.locator("#SessionTable caption")).toHaveCount(0);
  });

  test("the head is pinned to the top of its own scroll box", async ({ mount, page }) => {
    await mount(<SessionTable cells={sweep()} />);
    await expect(head(page, "at")).toHaveCSS("position", "sticky");
    await expect(head(page, "at")).toHaveCSS("top", "0px");
  });

  test("renders in dark mode with the dark tokens", async ({ mount, page }) => {
    await mount(<SessionTable cells={sweep()} />, { hooksConfig: { mode: "dark" } });
    await expect(rows(page)).toHaveCount(7);
    await expect(page.locator("body")).toHaveCSS("background-color", "rgb(15, 17, 23)");
    const glyph = page.locator('#SessionTable tr[data-sid="aaaaaaaa-0004"] td[data-k="effort"] > span.muted');
    await expect(glyph).toHaveText(NONE);
    await expect(glyph).toHaveCSS("color", MUTED.dark);
    await expect(head(page, "at")).toHaveCSS("color", MUTED.dark);
  });
});

test.describe("SessionTable: layout", () => {
  test("at 1440px the whole column budget fits: no horizontal scroll, no edge fade", async ({ mount, page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    // The card's own 20px padding, which the scroll box's -20px margins bleed into.
    await mount(
      <div style={{ padding: 20 }}>
        <SessionTable cells={sweep()} />
      </div>,
    );
    const box = page.locator("[data-slot='table-container']");
    await expect(box).toHaveAttribute("data-edge-end", "false");
    await expect(box).toHaveAttribute("data-edge-start", "false");
    const { scroll, client } = await box.evaluate((el) => ({ scroll: el.scrollWidth, client: el.clientWidth }));
    expect(scroll).toBeLessThanOrEqual(client + 1);
  });

  test("a narrow viewport clips the metrics half and fades only the clipped edge", async ({ mount, page }) => {
    await page.setViewportSize({ width: 700, height: 800 });
    await mount(
      <div style={{ padding: 20 }}>
        <SessionTable cells={sweep()} />
      </div>,
    );
    const box = page.locator("[data-slot='table-container']");
    await expect(box).toHaveAttribute("data-edge-end", "true");
    await expect(box).toHaveAttribute("data-edge-start", "false");
  });

  test("a sorted link to an off-screen column scrolls that head into view", async ({ mount, page }) => {
    await page.setViewportSize({ width: 700, height: 800 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await mount(
      <div style={{ padding: 20 }}>
        <SessionTable cells={sweep()} />
      </div>,
      { hooksConfig: { search: "?sort=wall_ms&dir=desc" } },
    );
    const box = page.locator("[data-slot='table-container']");
    await expect.poll(() => box.evaluate((el) => el.scrollLeft)).toBeGreaterThan(0);
    const inView = await page.evaluate(() => {
      const view = document.querySelector("[data-slot='table-container']")!.getBoundingClientRect();
      const th = document.querySelector('#SessionTable thead th[data-k="wall_ms"]')!.getBoundingClientRect();
      return th.left >= view.left && th.right <= view.right;
    });
    expect(inView).toBe(true);
  });

  test("a sort on a visible head never moves the table", async ({ mount, page }) => {
    await page.setViewportSize({ width: 700, height: 800 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await mount(
      <div style={{ padding: 20 }}>
        <SessionTable cells={sweep()} />
      </div>,
    );
    await head(page, "harness").locator("button").click();
    await expect.poll(() => search(page)).toBe("?sort=harness&dir=asc");
    expect(await page.locator("[data-slot='table-container']").evaluate((el) => el.scrollLeft)).toBe(0);
  });

  test("the case column truncates with an ellipsis rather than widening the table", async ({ mount, page }) => {
    const long = "eval_" + "a_very_long_case_name_".repeat(4);
    await mount(<SessionTable cells={[cell({ session_id: "long-a", case: long }), cell({ session_id: "long-b" })]} />);
    const span = page.locator('#SessionTable tr[data-sid="long-a"] td[data-k="case"] > span');
    await expect(span).toHaveCSS("text-overflow", "ellipsis");
    const { scroll, client } = await span.evaluate((el) => ({ scroll: el.scrollWidth, client: el.clientWidth }));
    expect(scroll).toBeGreaterThan(client);
  });
});

test.describe("SessionTable: sorting", () => {
  test("with no sort in the URL, rows run newest first and `when` is the sorted head", async ({ mount, page }) => {
    await mount(<SessionTable cells={timeline()} />);
    expect(await sids(page)).toEqual(["t-4", "t-3", "t-2", "t-1"]);
    await expect(head(page, "at")).toHaveAttribute("aria-sort", "descending");
    await expect(head(page, "at").locator("svg.sort-ico")).toHaveAttribute("data-active", "true");
    await expect(head(page, "at").locator("svg.sort-ico")).toHaveClass(/lucide-arrow-down/);
    const shown = (await heads(page)).length;
    await expect(page.locator('#SessionTable thead th[aria-sort="none"]')).toHaveCount(shown - 1);
  });

  test("inactive arrows point where a click goes: up, except `when`, which opens descending", async ({ mount, page }) => {
    await mount(<SessionTable cells={timeline()} />, { hooksConfig: { search: "?sort=turns&dir=asc" } });
    await expect(head(page, "at").locator("svg.sort-ico")).toHaveClass(/lucide-arrow-down/);
    await expect(head(page, "effort").locator("svg.sort-ico")).toHaveClass(/lucide-arrow-up/);
    await expect(head(page, "wall_ms").locator("svg.sort-ico")).toHaveClass(/lucide-arrow-up/);
  });

  test("a click on a fresh head sorts ascending and writes it to the URL; a second flips it", async ({ mount, page }) => {
    await mount(<SessionTable cells={timeline()} />);
    const button = head(page, "at").locator("button");
    await head(page, "turns").locator("button").click();
    await expect.poll(() => search(page)).toBe("?sort=turns&dir=asc");
    await expect(head(page, "turns")).toHaveAttribute("aria-sort", "ascending");
    await button.click();
    await expect.poll(() => search(page)).toBe("?sort=at&dir=desc");
    expect(await sids(page)).toEqual(["t-4", "t-3", "t-2", "t-1"]);
    await button.click();
    await expect.poll(() => search(page)).toBe("?sort=at&dir=asc");
    expect(await sids(page)).toEqual(["t-1", "t-2", "t-3", "t-4"]);
    await expect(head(page, "at")).toHaveAttribute("aria-sort", "ascending");
    await expect(head(page, "at").locator("svg.sort-ico")).toHaveClass(/lucide-arrow-up/);
  });

  test("a sort click replaces the history entry rather than pushing one", async ({ mount, page }) => {
    await mount(<SessionTable cells={timeline()} />);
    await spyHistory(page);
    await head(page, "turns").locator("button").click();
    await head(page, "turns").locator("button").click();
    await expect.poll(() => search(page)).toBe("?sort=turns&dir=desc");
    expect(await historyWrites(page)).toEqual({ pushes: 0, replaces: 2 });
  });

  test("a sort click carries every sibling param through: facets, theme and the summary's order", async ({ mount, page }) => {
    await mount(<SessionTable cells={sweep()} />, { hooksConfig: { search: "?ssort=cost&sdir=desc&effort=high,low&model=claude-opus-5&theme=dark" } });
    await head(page, "effort").locator("button").click();
    await expect.poll(() => search(page)).toBe("?sort=effort&dir=asc&ssort=cost&sdir=desc&model=claude-opus-5&effort=high,low&theme=dark");
  });

  test("the route's sort is the initial order: cost descending, a null cost last", async ({ mount, page }) => {
    await mount(
      <SessionTable
        cells={[
          cell({ session_id: "c-null", estimated_cost_usd: null }),
          cell({ session_id: "c-1", estimated_cost_usd: 1 }),
          cell({ session_id: "c-3", estimated_cost_usd: 3 }),
          cell({ session_id: "c-2", estimated_cost_usd: 2 }),
        ]}
      />,
      { hooksConfig: { search: "?sort=estimated_cost_usd&dir=desc" } },
    );
    expect(await sids(page)).toEqual(["c-3", "c-2", "c-1", "c-null"]);
    await expect(head(page, "estimated_cost_usd")).toHaveAttribute("aria-sort", "descending");
  });

  test("a null sorts last ascending too", async ({ mount, page }) => {
    await mount(
      <SessionTable
        cells={[
          cell({ session_id: "c-null", estimated_cost_usd: null }),
          cell({ session_id: "c-2", estimated_cost_usd: 2 }),
          cell({ session_id: "c-1", estimated_cost_usd: 1 }),
        ]}
      />,
      { hooksConfig: { search: "?sort=estimated_cost_usd&dir=asc" } },
    );
    expect(await sids(page)).toEqual(["c-1", "c-2", "c-null"]);
  });

  test("coverage ranks by the loaded share, not the raw count", async ({ mount, page }) => {
    await mount(
      <SessionTable
        cells={[
          cell({ session_id: "cov-half", skill_coverage: { files: 18, loaded: 9, run: 0, scripts: 0 } }),
          cell({ session_id: "cov-all", skill_coverage: { files: 2, loaded: 2, run: 0, scripts: 0 } }),
          cell({ session_id: "cov-none", skill_coverage: {} }),
          cell({ session_id: "cov-tenth", skill_coverage: { files: 10, loaded: 1, run: 0, scripts: 0 } }),
        ]}
      />,
      { hooksConfig: { search: "?sort=coverage&dir=desc" } },
    );
    expect(await sids(page)).toEqual(["cov-all", "cov-half", "cov-tenth", "cov-none"]);
  });

  test("peak context ranks by share of the window, not by raw tokens", async ({ mount, page }) => {
    await mount(
      <SessionTable
        cells={[
          cell({ session_id: "big-window", peak_context_tokens: 60_000, context_window: 1_000_000, context_window_pct: 6 }),
          cell({ session_id: "small-window", peak_context_tokens: 68_000, context_window: 200_000, context_window_pct: 34 }),
          cell({ session_id: "mid", peak_context_tokens: 100_000, context_window: 1_000_000, context_window_pct: 10 }),
        ]}
      />,
      { hooksConfig: { search: "?sort=context_window_pct&dir=desc" } },
    );
    expect(await sids(page)).toEqual(["small-window", "mid", "big-window"]);
  });

  test("an unknown sort key falls back to the default column, newest first", async ({ mount, page }) => {
    // Regression: an unknown key used to keep the bogus pair's `asc` and open oldest first.
    await mount(<SessionTable cells={timeline()} />, { hooksConfig: { search: "?sort=bogus" } });
    await expect(head(page, "at")).toHaveAttribute("aria-sort", "descending");
    expect(await sids(page)).toEqual(["t-4", "t-3", "t-2", "t-1"]);
  });

  test("Enter and Space on a focused head sort it, from the keyboard alone", async ({ mount, page }) => {
    await mount(<SessionTable cells={timeline()} />);
    await head(page, "turns").locator("button").focus();
    await page.keyboard.press("Enter");
    await expect.poll(() => search(page)).toBe("?sort=turns&dir=asc");
    await page.keyboard.press("Space");
    await expect.poll(() => search(page)).toBe("?sort=turns&dir=desc");
  });

  test("the first Tab stop is the first head, and heads come before rows", async ({ mount, page }) => {
    await mount(<SessionTable cells={timeline()} />);
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "verdict", exact: true })).toBeFocused();
    const shown = (await heads(page)).length;
    for (let i = 1; i < shown; i++) await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "wall — wall_ms" })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(rows(page).first()).toBeFocused();
  });

  test("every head answers to its canonical field name and is described by its definition", async ({ mount, page }) => {
    await mount(<SessionTable cells={sweep()} />);
    await expect(page.getByRole("button", { name: "cost — estimated_cost_usd" })).toBeVisible();
    await expect(page.getByRole("button", { name: "billed — accumulative_billed_tokens (billed)" })).toBeVisible();
    await expect(page.getByRole("button", { name: "peak ctx — peak_context_tokens" })).toBeVisible();
    await expect(page.getByRole("button", { name: "when — at" })).toBeVisible();
    const effort = page.getByRole("button", { name: "effort", exact: true });
    await expect(effort).toHaveAttribute("aria-describedby", "SessionTable-def-effort");
    await expect(effort).toHaveAccessibleDescription(/^effort — the reasoning rung the CLI was asked for/);
    // One definition per head, each id unique on the page.
    const ids = await page.locator("#SessionTable thead .sr-only").evaluateAll((els) => els.map((el) => el.id));
    expect(ids).toHaveLength(ALL_KEYS.length);
    expect(new Set(ids).size).toBe(ALL_KEYS.length);
  });
});

test.describe("SessionTable: the effort axis (ADR 0049)", () => {
  test("the effort column sits after model and prints each rung as sent", async ({ mount, page }) => {
    await mount(<SessionTable cells={sweep()} />);
    const keys = await heads(page);
    expect(keys.indexOf("effort")).toBe(keys.indexOf("model") + 1);
    expect(await column(page, "effort")).toEqual(["max", "low", "high", NONE, "medium", "xhigh", "low"]);
  });

  test("a cell that named no rung shows the muted glyph, not a word the CLI was never sent", async ({ mount, page }) => {
    await mount(<SessionTable cells={sweep()} />);
    const glyph = page.locator('#SessionTable tr[data-sid="aaaaaaaa-0004"] td[data-k="effort"] > span');
    await expect(glyph).toHaveClass("muted");
    await expect(glyph).toHaveText(NONE);
    await expect(glyph).toHaveCSS("color", MUTED.light);
  });

  test("ascending, rungs follow the ladder (low < medium < high < xhigh < max), a null last", async ({ mount, page }) => {
    await mount(<SessionTable cells={sweep()} />, { hooksConfig: { search: "?sort=effort&dir=asc" } });
    expect(await column(page, "effort")).toEqual(["low", "low", "medium", "high", "xhigh", "max", NONE]);
    await expect(head(page, "effort")).toHaveAttribute("aria-sort", "ascending");
  });

  test("descending, the ladder reverses but a null still sorts last", async ({ mount, page }) => {
    await mount(<SessionTable cells={sweep()} />, { hooksConfig: { search: "?sort=effort&dir=desc" } });
    expect(await column(page, "effort")).toEqual(["max", "xhigh", "high", "medium", "low", "low", NONE]);
  });

  test("clicking the effort head sorts by rung position, never alphabetically", async ({ mount, page }) => {
    await mount(<SessionTable cells={sweep()} />);
    await head(page, "effort").locator("button").click();
    await expect.poll(() => search(page)).toBe("?sort=effort&dir=asc");
    const asc = await column(page, "effort");
    // Alphabetically this would read high, low, low, max, medium, xhigh.
    expect(asc).not.toEqual(["high", "low", "low", "max", "medium", "xhigh", NONE]);
    expect(asc).toEqual(["low", "low", "medium", "high", "xhigh", "max", NONE]);
    await head(page, "effort").locator("button").click();
    await expect.poll(() => search(page)).toBe("?sort=effort&dir=desc");
    expect(await column(page, "effort")).toEqual(["max", "xhigh", "high", "medium", "low", "low", NONE]);
  });

  test("a rung this page has never heard of sorts after the ladder and before a null", async ({ mount, page }) => {
    await mount(
      <SessionTable
        cells={[
          cell({ session_id: "u-null", effort: null }),
          cell({ session_id: "u-turbo", effort: "turbo" }),
          cell({ session_id: "u-max", effort: "max" }),
          cell({ session_id: "u-low", effort: "low" }),
        ]}
      />,
      { hooksConfig: { search: "?sort=effort&dir=asc" } },
    );
    expect(await column(page, "effort")).toEqual(["low", "max", "turbo", NONE]);
  });

  test("the row's accessible name names the rung when one was sent and omits it when none was", async ({ mount, page }) => {
    await mount(<SessionTable cells={sweep()} />);
    await expect(page.locator('#SessionTable tr[data-sid="aaaaaaaa-0003"]')).toHaveAttribute(
      "aria-label",
      "eval_dual_density · claude/claude-opus-5 · high · pass",
    );
    await expect(page.locator('#SessionTable tr[data-sid="aaaaaaaa-0002"]')).toHaveAttribute(
      "aria-label",
      "eval_dual_density · claude/claude-opus-5 · low · fail",
    );
    await expect(page.locator('#SessionTable tr[data-sid="aaaaaaaa-0004"]')).toHaveAttribute(
      "aria-label",
      "eval_dual_density · claude/claude-opus-5 · no history",
    );
    await expect(page.getByRole("row", { name: "eval_map · codex/gpt-5.6-luna · low · pass" })).toBeVisible();
  });

  test("one rung on every row collapses the effort column into the caption", async ({ mount, page }) => {
    await mount(<SessionTable cells={[cell({ session_id: "h-1", effort: "high" }), cell({ session_id: "h-2", effort: "high", model: "claude-sonnet-5" })]} />);
    expect(await heads(page)).not.toContain("effort");
    await expect(page.locator("#SessionTable caption")).toContainText("effort high");
  });

  test("a sweep with no rungs at all keeps the effort column, every cell the muted glyph", async ({ mount, page }) => {
    await mount(<SessionTable cells={[cell({ session_id: "n-1" }), cell({ session_id: "n-2", model: "claude-sonnet-5" })]} />);
    expect(await heads(page)).toContain("effort");
    expect(await column(page, "effort")).toEqual([NONE, NONE]);
    await expect(page.locator("#SessionTable caption")).not.toContainText("effort");
  });
});

test.describe("SessionTable: constant columns", () => {
  const same = () => [cell({ session_id: "s-1", effort: "high", turns: 3 }), cell({ session_id: "s-2", effort: "high", turns: 3, verdict: "fail" })];

  test("identity columns constant on every row collapse into one caption, in order", async ({ mount, page }) => {
    await mount(<SessionTable cells={same()} />);
    const caption = page.locator("#SessionTable caption");
    await expect(caption).toHaveText("every row: skill mermaidjs-diagrams · case dual_density · harness claude · model opus-5 · effort high");
    expect(await heads(page)).toEqual(ALL_KEYS.filter((k) => !["skill", "case", "harness", "model", "effort"].includes(k)));
    await expect(rows(page).first().locator("td")).toHaveCount(ALL_KEYS.length - 5);
  });

  test("the caption reads above the table, in the muted caption ink", async ({ mount, page }) => {
    await mount(<SessionTable cells={same()} />);
    const caption = page.locator("#SessionTable caption");
    await expect(caption).toHaveCSS("caption-side", "top");
    const captionBottom = await caption.evaluate((el) => el.getBoundingClientRect().bottom);
    const headTop = await page.locator("#SessionTable thead").evaluate((el) => el.getBoundingClientRect().top);
    expect(captionBottom).toBeLessThanOrEqual(headTop + 1);
    await expect(caption).toHaveCSS("color", MUTED.light);
  });

  test("the caption's constant values stand out from its muted words", async ({ mount, page }) => {
    // Regression: the rule once read an undefined `--xh-color` and inherited the muted ink.
    await mount(<SessionTable cells={same()} />);
    await expect(page.locator("#SessionTable caption .const").first()).not.toHaveCSS("color", MUTED.light);
  });

  test("a measure equal on every row is a finding, and never collapses", async ({ mount, page }) => {
    await mount(<SessionTable cells={same()} />);
    expect(await heads(page)).toContain("turns");
    expect(await heads(page)).toContain("verdict");
    expect(await column(page, "turns")).toEqual(["3", "3"]);
  });

  test("one row is one row: nothing collapses", async ({ mount, page }) => {
    await mount(<SessionTable cells={[cell({ effort: "high" })]} />);
    expect(await heads(page)).toEqual(ALL_KEYS);
    await expect(page.locator("#SessionTable caption")).toHaveCount(0);
  });

  test("a skill that is null on every row never collapses", async ({ mount, page }) => {
    await mount(<SessionTable cells={[cell({ session_id: "ns-1", skill: null }), cell({ session_id: "ns-2", skill: null, harness: "codex" })]} />);
    expect(await heads(page)).toContain("skill");
    await expect(page.locator("#SessionTable caption")).toHaveText("every row: case dual_density · model opus-5");
  });

  test("the empty-state cell spans exactly the columns that remain", async ({ mount, page }) => {
    await mount(<SessionTable cells={[]} />);
    await expect(page.locator("#SessionTable td.empty")).toHaveAttribute("colspan", String(ALL_KEYS.length));
  });
});

test.describe("SessionTable: opening a session", () => {
  test("a row click pushes the session route, carrying the theme", async ({ mount, page }) => {
    await mount(<SessionTable cells={sweep()} />, { hooksConfig: { search: "?sort=turns&dir=asc&theme=dark" } });
    await spyHistory(page);
    await page.locator('#SessionTable tr[data-sid="aaaaaaaa-0003"] td[data-k="turns"]').click();
    await expect.poll(() => search(page)).toBe("?session=aaaaaaaa-0003&theme=dark");
    expect(await historyWrites(page)).toEqual({ pushes: 1, replaces: 0 });
  });

  for (const key of ["Enter", "Space"]) {
    test(`${key} on a focused row opens its session`, async ({ mount, page }) => {
      await mount(<SessionTable cells={sweep()} />);
      await page.locator('#SessionTable tr[data-sid="cccccccc-0001"]').focus();
      await page.keyboard.press(key);
      await expect.poll(() => search(page)).toBe("?session=cccccccc-0001");
    });
  }

  test("another key on a focused row does nothing", async ({ mount, page }) => {
    await mount(<SessionTable cells={sweep()} />);
    await page.locator('#SessionTable tr[data-sid="cccccccc-0001"]').focus();
    await page.keyboard.press("a");
    await page.keyboard.press("ArrowDown");
    expect(await search(page)).toBe("");
  });

  test("a click on a head sorts and does not open anything", async ({ mount, page }) => {
    await mount(<SessionTable cells={sweep()} />);
    await head(page, "harness").locator("button").click();
    await expect.poll(() => search(page)).toBe("?sort=harness&dir=asc");
  });

  test("Tab walks the rows in their sorted order", async ({ mount, page }) => {
    await mount(<SessionTable cells={timeline()} />);
    await rows(page).first().focus();
    await expect(page.locator('#SessionTable tr[data-sid="t-4"]')).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.locator('#SessionTable tr[data-sid="t-3"]')).toBeFocused();
  });
});
