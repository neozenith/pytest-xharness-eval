/**
 * SessionTurnTable: one row per model call, the harness's own column set, the details row a
 * click opens (or the detailed view opens for all), and the subagent bands under the turn that
 * spawned them.
 *
 * `renderTurnRecords` returns JSX, which CT cannot carry across from Node (a proxied function
 * returns a Promise and React rejects the async component; the first test pins that), so the
 * records path runs through `TurnTableStory`, which wires it in the browser as SessionView does.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import type { Locator } from "@playwright/test";
import { SessionTurnTable } from "../src/components/panels/SessionTurnTable";
import type { TurnView } from "../src/lib/route";
import type { RunResult } from "../src/lib/types";
import { TurnTableStory } from "./panels.SessionTurnTable.story";
import { call, PHONE, pageOverflowX, resolveColour, result, SID, subagent, usage } from "./panels.data";

// `clock()` prints local time; pin the zone so `07:12:14.549` is the same everywhere.
test.use({ timezoneId: "UTC" });

const CLAUDE_HEADS = [
  "SessionTurnId",
  "time",
  "log lines",
  "tools issued",
  "results in",
  "cache_read",
  "cache_write",
  "1h",
  "input",
  "context",
  "ctx %",
  "output",
  "thinking",
  "latency",
  "tok/s",
  "stop",
];
const CODEX_HEADS = [
  "SessionTurnId",
  "time",
  "log lines",
  "tools issued",
  "results in",
  "cached input",
  "input (uncached)",
  "context",
  "ctx %",
  "output",
  "thinking",
  "latency",
  "tok/s",
  "stop",
];

const noop = () => {};
const plain = { view: "summary" as TurnView, openTurn: null, recordView: "nice" as const, onViewChange: noop, onOpenTurn: noop };

const card = (c: Locator) => c.locator("#SessionTurnTablePanel");
const heads = (c: Locator) => c.locator("#SessionTurnTable thead th");
const row = (c: Locator, n: number) => c.locator(`tr.SessionTurnRow[data-n="${n}"]`);
const detail = (c: Locator, n: number) => c.locator(`tr.detail-row[data-n="${n}"]`);
const cellTexts = async (r: Locator) => (await r.locator("td").allInnerTexts()).map((t) => t.replace(/\s+/g, " ").trim());

test.describe("renderTurnRecords across the CT boundary", () => {
  test("a JSX-returning callback passed straight from Node cannot render (why the story exists)", async ({ mount, page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await mount(<SessionTurnTable result={result()} {...plain} view="detailed" renderTurnRecords={(k) => <div>records of t{k.n}</div>} />);
    await expect.poll(() => errors.join("\n")).toContain("async Client Component");
  });
});

test.describe("columns per harness", () => {
  test("claude: the four explicit cache tiers between the core and the context columns", async ({ mount }) => {
    const c = await mount(<SessionTurnTable result={result()} {...plain} />);
    await expect(card(c)).toHaveAttribute("data-harness", "claude");
    await expect(heads(c)).toHaveText(CLAUDE_HEADS);
    await expect(heads(c).filter({ hasText: /^context$/ })).toHaveAttribute("title", /context_tokens/);
  });

  test("codex: implicit caching, so only `cached input` and uncached `input`", async ({ mount }) => {
    const c = await mount(<SessionTurnTable result={result({ harness: "codex" })} {...plain} />);
    await expect(card(c)).toHaveAttribute("data-harness", "codex");
    await expect(heads(c)).toHaveText(CODEX_HEADS);
    await expect(heads(c).filter({ hasText: "cached input" })).toHaveAttribute("title", /cached_input_tokens/);
    // the codex read tier is the ledger's cache_read_tokens under codex's own name
    expect((await cellTexts(row(c, 2)))[5]).toBe("35,865");
    expect((await cellTexts(row(c, 2)))[6]).toBe("2");
  });

  test("an unknown harness gets the full claude column set", async ({ mount }) => {
    const c = await mount(<SessionTurnTable result={result({ harness: "gemini" })} {...plain} />);
    await expect(card(c)).toHaveAttribute("data-harness", "claude");
    await expect(heads(c)).toHaveText(CLAUDE_HEADS);
  });

  test("numeric columns are right-aligned, the rest are not", async ({ mount }) => {
    const c = await mount(<SessionTurnTable result={result()} {...plain} />);
    const align = await row(c, 2)
      .locator("td")
      .evaluateAll((tds) => tds.map((td) => getComputedStyle(td).textAlign));
    const numeric = new Set(["results in", "cache_read", "cache_write", "1h", "input", "context", "ctx %", "output", "thinking", "latency", "tok/s"]);
    expect(align).toEqual(CLAUDE_HEADS.map((h) => (numeric.has(h) ? "right" : expect.not.stringMatching(/^right$/))));
  });
});

test.describe("one row per call", () => {
  test("every column of a turn renders from the ledger", async ({ mount }) => {
    const c = await mount(<SessionTurnTable result={result()} {...plain} />);
    await expect(c.locator("tr.SessionTurnRow")).toHaveCount(2);
    expect(await cellTexts(row(c, 2))).toEqual([
      "1feb573f/t2",
      "07:12:14.549",
      "19, 21, 23-29",
      "BashRead",
      "2 · 7,036 ch",
      "35,865",
      "4,234",
      "4,234",
      "2",
      "40,101",
      "4.0%",
      "264",
      "42",
      "1,716 ms",
      "153.85",
      "tool_use",
    ]);
    // turn 1: its own log lines and nothing in yet
    const t1 = await cellTexts(row(c, 1));
    expect(t1[2]).toBe("1-3");
    expect(t1[4]).toBe("0 · 0 ch");
  });

  test("the SessionTurnId copies the full `<session>/t<n>` and the context figure is emphasised", async ({ mount }) => {
    const c = await mount(<SessionTurnTable result={result()} {...plain} />);
    await expect(row(c, 2).getByRole("button", { name: `Copy ${SID}/t2` })).toHaveAttribute("title", `${SID}/t2`);
    const weight = await row(c, 2)
      .locator(".strong")
      .evaluate((el) => getComputedStyle(el).fontWeight);
    expect(Number(weight)).toBeGreaterThanOrEqual(600);
    await expect(row(c, 2).locator("code.code-chip")).toHaveText(["Bash", "Read"]);
  });

  test("missing per-call values print the one no-value glyph, and a toolless turn is the final reply", async ({ mount }) => {
    const r = result({
      calls: [
        call(1, { at: "", stop_reason: null, latency_ms: null, context_pct: null, output_tokens_per_sec: null, tools: [], records: [], results_in: [] }),
        call(2, { at: "not-a-date" }),
      ],
    });
    const c = await mount(<SessionTurnTable result={r} {...plain} />);
    const t1 = await cellTexts(row(c, 1));
    expect(t1[1]).toBe("–");
    expect(t1[2]).toBe("");
    expect(t1[3]).toBe("(final reply)");
    expect(t1[10]).toBe("–");
    expect(t1[13]).toBe("–");
    expect(t1[14]).toBe("–");
    expect(t1[15]).toBe("–");
    await expect(row(c, 1).locator("td").nth(3).locator(".muted")).toHaveText("(final reply)");
    expect((await cellTexts(row(c, 2)))[1]).toBe("not-a-date");
  });

  for (const [harness, span] of [
    ["claude", CLAUDE_HEADS.length],
    ["codex", CODEX_HEADS.length],
  ] as const) {
    test(`${harness}: a result with no ledger says so across every column`, async ({ mount }) => {
      const c = await mount(<SessionTurnTable result={result({ harness, calls: [] })} {...plain} />);
      const td = c.locator("#SessionTurnTable tbody td.warn");
      await expect(td).toHaveText(/no per-turn ledger \(it predates ADR 0019\)/);
      await expect(td).toHaveAttribute("colspan", String(span));
      await expect(c.locator("tr.SessionTurnRow")).toHaveCount(0);
    });
  }

  test("a result without a `calls` field is the same as an empty ledger", async ({ mount }) => {
    const r = result() as Partial<RunResult>;
    delete r.calls;
    const c = await mount(<SessionTurnTable result={r as RunResult} {...plain} />);
    await expect(c.getByText(/no per-turn ledger/)).toBeVisible();
  });
});

test.describe("opening and closing a turn", () => {
  test("summary view: no details rows, nothing marked open", async ({ mount }) => {
    const c = await mount(<TurnTableStory result={result()} />);
    await expect(c.locator("tr.detail-row")).toHaveCount(0);
    await expect(c.locator("tr.row-open")).toHaveCount(0);
  });

  test("`openTurn` from the URL opens that turn only, with its records under its SessionTurnId", async ({ mount }) => {
    const c = await mount(<TurnTableStory result={result()} openTurn={2} />);
    await expect(c.locator("tr.detail-row")).toHaveCount(1);
    await expect(detail(c, 2)).toContainText("records of t2: 19,21,23,24,25,26,27,28,29");
    await expect(detail(c, 2).locator(`[id="${SID}/t2"]`)).toBeVisible();
    await expect(row(c, 2)).toHaveClass(/row-open/);
    await expect(row(c, 1)).not.toHaveClass(/row-open/);
    // the details row spans the whole table and wraps its prose
    await expect(detail(c, 2).locator("td")).toHaveAttribute("colspan", String(CLAUDE_HEADS.length));
    await expect(detail(c, 2).locator("td")).toHaveCSS("white-space", "normal");
  });

  test("the open row is tinted, a closed row is not", async ({ mount }) => {
    const c = await mount(<TurnTableStory result={result()} openTurn={2} />);
    const open = await row(c, 2).evaluate((el) => getComputedStyle(el).backgroundColor);
    const closed = await row(c, 1).evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(open).not.toBe(closed);
    expect(closed).toBe("rgba(0, 0, 0, 0)");
  });

  test("a click opens a turn, reports it upward, and a second click closes it", async ({ mount }) => {
    const reported: (number | null)[] = [];
    const c = await mount(<TurnTableStory result={result()} onOpenTurnSpy={(n) => reported.push(n)} />);
    await row(c, 1).click();
    await expect(detail(c, 1)).toContainText("records of t1: 1,2,3");
    await row(c, 2).click();
    // one turn open at a time: opening t2 closes t1
    await expect(detail(c, 1)).toHaveCount(0);
    await expect(detail(c, 2)).toBeVisible();
    await row(c, 2).click();
    await expect(c.locator("tr.detail-row")).toHaveCount(0);
    await expect.poll(() => reported).toEqual([1, 2, null]);
  });

  test("the table itself only reports: `onOpenTurn` gets n, or null for the open turn", async ({ mount }) => {
    const calls: (number | null)[] = [];
    const c = await mount(<SessionTurnTable result={result()} {...plain} openTurn={2} onOpenTurn={(n) => calls.push(n)} />);
    await row(c, 1).click();
    await row(c, 2).click();
    await expect.poll(() => calls).toEqual([1, null]);
  });

  test("copying a SessionTurnId does not toggle its turn", async ({ mount }) => {
    const calls: (number | null)[] = [];
    const c = await mount(<SessionTurnTable result={result()} {...plain} onOpenTurn={(n) => calls.push(n)} />);
    await row(c, 2)
      .getByRole("button", { name: `Copy ${SID}/t2` })
      .click();
    await row(c, 1).click();
    await expect.poll(() => calls).toEqual([1]);
  });

  test("without a records renderer the details row still carries the turn's id", async ({ mount }) => {
    const c = await mount(<TurnTableStory result={result()} openTurn={1} records={false} />);
    const placeholder = detail(c, 1).locator(`[id="${SID}/t1"]`);
    await expect(placeholder).toHaveText("no record renderer wired");
    await expect(placeholder).toHaveClass(/muted/);
  });
});

test.describe("summary vs detailed", () => {
  test("the toggle shows the current view and reports a change", async ({ mount }) => {
    const views: TurnView[] = [];
    const c = await mount(<SessionTurnTable result={result()} {...plain} onViewChange={(v) => views.push(v)} />);
    const toggle = c.getByRole("group", { name: "turn table view" }).or(c.locator("#ViewToggle"));
    await expect(toggle.first()).toBeVisible();
    await expect(c.locator('[data-view="summary"]')).toHaveAttribute("data-state", "on");
    await expect(c.locator('[data-view="detailed"]')).not.toHaveAttribute("data-state", "on");
    await c.locator('[data-view="detailed"]').click();
    await expect.poll(() => views).toEqual(["detailed"]);
  });

  test("re-pressing the selected view reports nothing (a single toggle never empties)", async ({ mount }) => {
    const views: TurnView[] = [];
    const c = await mount(<SessionTurnTable result={result()} {...plain} onViewChange={(v) => views.push(v)} />);
    await c.locator('[data-view="summary"]').click();
    await c.locator('[data-view="detailed"]').click();
    await expect.poll(() => views).toEqual(["detailed"]);
  });

  test("detailed opens every turn; back to summary closes them all", async ({ mount }) => {
    const views: TurnView[] = [];
    const c = await mount(<TurnTableStory result={result()} onViewChangeSpy={(v) => views.push(v)} />);
    await c.locator('[data-view="detailed"]').click();
    await expect(c.locator('[data-testid="turn-records"]')).toHaveText(["records of t1: 1,2,3", /records of t2/]);
    await expect(c.locator("tr.SessionTurnRow.row-open")).toHaveCount(2);
    await expect(c.locator('[data-view="detailed"]')).toHaveAttribute("data-state", "on");
    // a click in the detailed view reports, but cannot close a row the view holds open
    await row(c, 1).click();
    await expect(detail(c, 1)).toBeVisible();
    await c.locator('[data-view="summary"]').click();
    await expect(c.locator("tr.detail-row")).toHaveCount(1); // t1, opened by the click above
    await expect.poll(() => views).toEqual(["detailed", "summary"]);
  });

  test("an externally supplied detailed view opens every row on mount", async ({ mount }) => {
    const c = await mount(<TurnTableStory result={result()} view="detailed" />);
    await expect(c.locator("tr.detail-row")).toHaveCount(2);
  });

  test("`toolbarExtra` sits in the toolbar beside the toggle", async ({ mount }) => {
    const c = await mount(<SessionTurnTable result={result()} {...plain} toolbarExtra={<span id="RecordViewToggleStub">raw / nice</span>} />);
    await expect(c.locator("#RecordViewToggleStub")).toHaveText("raw / nice");
  });
});

test.describe("keyboard", () => {
  test("the view toggle is reachable by Tab and switches with the keyboard", async ({ mount, page }) => {
    const views: TurnView[] = [];
    const c = await mount(<TurnTableStory result={result()} onViewChangeSpy={(v) => views.push(v)} />);
    await c.locator('[data-view="summary"]').focus();
    await expect(c.locator('[data-view="summary"]')).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(c.locator('[data-view="detailed"]')).toBeFocused();
    await page.keyboard.press("Enter");
    await expect.poll(() => views).toEqual(["detailed"]);
    await expect(c.locator("tr.detail-row")).toHaveCount(2);
  });

  test("the SessionTurnId copy buttons are tab stops", async ({ mount }) => {
    const c = await mount(<SessionTurnTable result={result()} {...plain} />);
    const copy = row(c, 1).getByRole("button", { name: `Copy ${SID}/t1` });
    await copy.focus();
    await expect(copy).toBeFocused();
  });

  test("a turn row opens from the keyboard (Enter on the focused row)", async ({ mount, page }) => {
    // BUG: SessionTurnTable.tsx:304-310 — the SessionTurnRow is a click-only <tr>: no tabIndex,
    // no role, no onKeyDown. Expected: a keyboard user can focus a turn and open it with Enter,
    // as SessionTable's SessionRow allows (SessionTable.tsx:386 tabIndex, :402 onKeyDown) and as
    // index.css's `tr.SessionRow:focus-visible` ring anticipates. Actual: the row never takes
    // focus, so the details row (the turn's records) is reachable by pointer only (WCAG 2.1.1).
    test.fail();
    const calls: (number | null)[] = [];
    const c = await mount(<SessionTurnTable result={result()} {...plain} onOpenTurn={(n) => calls.push(n)} />);
    await row(c, 1).focus();
    await expect(row(c, 1)).toBeFocused({ timeout: 1000 });
    await page.keyboard.press("Enter");
    await expect.poll(() => calls, { timeout: 1000 }).toEqual([1]);
  });
});

test.describe("subagents", () => {
  const spawned = (): RunResult =>
    result({
      subagents: [
        subagent({
          agent: "Explore",
          id: "11111111-aaaa-bbbb-cccc-000000000001",
          parent_turn: 1,
          turns: 2,
          description: "map the skills tree",
          calls: [call(1, { tools: [{ name: "Grep", input: {} }], stop_reason: "tool_use" }), call(2, { tools: [], stop_reason: null, latency_ms: null })],
        }),
        subagent({ agent: "Plan", id: "22222222-aaaa-bbbb-cccc-000000000002", parent_turn: 1, turns: 1, calls: [] }),
        subagent({
          agent: "general-purpose",
          id: "33333333-aaaa-bbbb-cccc-000000000003",
          parent_turn: 2,
          usage: usage({ input_tokens: 10, output_tokens: 20, cache_read_tokens: 30, cache_write_tokens: 40 }),
        }),
      ],
    });

  test("the toolbar prose counts the spawned threads", async ({ mount }) => {
    const c = await mount(<SessionTurnTable result={spawned()} {...plain} />);
    await expect(c).toContainText("This session spawned 3 parallel subagents; each appears under the turn that spawned it.");
  });

  test("one spawned thread is singular", async ({ mount }) => {
    const c = await mount(<SessionTurnTable result={result({ subagents: [subagent()] })} {...plain} />);
    await expect(c).toContainText("spawned 1 parallel subagent;");
  });

  test("no subagents: no band and no spawn prose", async ({ mount }) => {
    const c = await mount(<SessionTurnTable result={result()} {...plain} />);
    await expect(c.locator('[data-el="SubagentBand"]')).toHaveCount(0);
    await expect(c).not.toContainText("parallel subagent");
  });

  test("each band sits directly under the turn that spawned it, even in the summary view", async ({ mount }) => {
    const c = await mount(<SessionTurnTable result={spawned()} {...plain} />);
    const bands = c.locator("tr.subagent-band-row");
    await expect(bands).toHaveCount(2);
    const order = await c
      .locator("#SessionTurnTable > tbody > tr")
      .evaluateAll((trs) => trs.map((tr) => `${tr.className.split(" ")[0]}:${tr.getAttribute("data-n")}`));
    expect(order).toEqual(["SessionTurnRow:1", "subagent-band-row:1", "SessionTurnRow:2", "subagent-band-row:2"]);
    await expect(bands.nth(0).locator('[data-el="SubagentBand"] > [data-agent]')).toHaveCount(2);
    await expect(bands.nth(1).locator('[data-el="SubagentBand"] > [data-agent]')).toHaveCount(1);
    await expect(bands.nth(0).locator(":scope > td")).toHaveAttribute("colspan", String(CLAUDE_HEADS.length));
  });

  test("a band names the agent, its id, its description and its bill", async ({ mount }) => {
    const c = await mount(<SessionTurnTable result={spawned()} {...plain} />);
    const explore = c.locator('[data-el="SubagentBand"] > [data-agent="Explore"]');
    await expect(explore.locator(".pill")).toHaveText("⑂ Explore");
    await expect(explore.getByRole("button", { name: "Copy 11111111-aaaa-bbbb-cccc-000000000001" })).toContainText("11111111");
    await expect(explore).toContainText("map the skills tree");
    await expect(explore).toContainText("2 turns · 150 billed tokens");
    const plan = c.locator('[data-el="SubagentBand"] > [data-agent="Plan"]');
    await expect(plan).toContainText("1 turn · 150 billed tokens");
    await expect(plan).toContainText("no per-call ledger in this transcript");
    // no accumulative_billed_tokens: the bill is input + output + cache read + cache write
    await expect(c.locator('[data-agent="general-purpose"]').first()).toContainText("1 turn · 100 billed tokens");
  });

  test("a subagent's own per-call ledger renders row by row", async ({ mount }) => {
    const c = await mount(<SessionTurnTable result={spawned()} {...plain} />);
    const rows = c.locator('tr[data-el="SubagentTurnRow"][data-agent="Explore"]');
    await expect(rows).toHaveCount(2);
    await expect(c.locator("table.subagent-turns").first().locator("th")).toHaveText([
      "turn",
      "time",
      "tools issued",
      "cache_read",
      "input",
      "context",
      "output",
      "thinking",
      "latency",
      "stop",
    ]);
    expect(await cellTexts(rows.nth(0))).toEqual(["11111111/t1", "07:12:14.549", "Grep", "35,865", "2", "40,101", "264", "42", "1,716 ms", "tool_use"]);
    const second = await cellTexts(rows.nth(1));
    expect(second[2]).toBe("(final reply)");
    expect(second[8]).toBe("–");
    expect(second[9]).toBe("–");
  });

  test("the band footer names the spawning turn and the band is ruled in the waterfall's `sub` colour", async ({ mount, page }) => {
    const c = await mount(<SessionTurnTable result={spawned()} {...plain} />);
    await expect(c.locator("tr.subagent-band-row").nth(0)).toContainText(`Spawned by turn 1 of 1feb573f`);
    await expect(c.locator("tr.subagent-band-row").nth(1)).toContainText(`Spawned by turn 2 of 1feb573f`);
    const sub = await resolveColour(page, "var(--xh-waterfall-sub)");
    const band = c.locator('[data-el="SubagentBand"]').first();
    expect(await band.evaluate((el) => getComputedStyle(el).borderLeftColor)).toBe(sub);
    expect(
      await band
        .locator(".pill")
        .first()
        .evaluate((el) => getComputedStyle(el).backgroundColor),
    ).toBe(sub);
  });

  test("a subagent with no recorded parent turn is shown under turn 1, its footer saying so is unknown", async ({ mount }) => {
    const c = await mount(<SessionTurnTable result={result({ subagents: [subagent({ parent_turn: null })] })} {...plain} />);
    const band = c.locator('tr.subagent-band-row[data-n="1"]');
    await expect(band).toHaveCount(1);
    await expect(band).toContainText("Spawned by turn ? of 1feb573f");
  });

  test("a subagent whose parent turn is not in the ledger is still shown", async ({ mount }) => {
    // BUG: SessionTurnTable.tsx:249-256 / :299-301 — bands are only rendered inside the
    // `calls.map` loop, keyed by parent_turn. A subagent whose parent_turn matches no call
    // (a ledger truncated, or parent_turn past the last call) is silently dropped, while the
    // toolbar prose (:271-273) still says "each appears under the turn that spawned it".
    // Expected: the thread (and its bill) is visible somewhere. Actual: no band at all.
    test.fail();
    const c = await mount(<SessionTurnTable result={result({ subagents: [subagent({ parent_turn: 7 })] })} {...plain} />);
    await expect(c.locator('[data-el="SubagentBand"]')).toHaveCount(1, { timeout: 1000 });
  });

  test("an orphaned subagent is still counted in the toolbar prose (the claim the test above checks)", async ({ mount }) => {
    const c = await mount(<SessionTurnTable result={result({ subagents: [subagent({ parent_turn: 7 })] })} {...plain} />);
    await expect(c).toContainText("This session spawned 1 parallel subagent; each appears under the turn that spawned it.");
    await expect(c.locator("tr.SessionTurnRow")).toHaveCount(2);
  });
});

test.describe("layout and theme", () => {
  test("at phone width the table scrolls in its own box and the page does not scroll sideways", async ({ mount, page }) => {
    await page.setViewportSize(PHONE);
    const long = "mcp__claude_ai_Atlassian_Rovo__complete_authentication_with_a_very_long_tool_name";
    const r = result({
      calls: [call(1, { tools: [{ name: long, input: {} }], stop_reason: "a_very_long_stop_reason_that_never_breaks_anywhere_at_all" }), call(2)],
      subagents: [subagent({ description: "an unusually long description ".repeat(12) })],
    });
    const c = await mount(<TurnTableStory result={r} view="detailed" />);
    await expect(c.locator("tr.SessionTurnRow")).toHaveCount(2);
    expect(await pageOverflowX(page)).toBeLessThanOrEqual(0);
    const box = c.locator("#SessionTurnTable").locator("xpath=..");
    await expect(box).toHaveClass(/table-scroll/);
    expect(await box.evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(true);
  });

  test("dark mode: the card, ink and open-row tint come from the dark theme", async ({ mount, page }) => {
    const c = await mount(<TurnTableStory result={result()} openTurn={1} />, { hooksConfig: { mode: "dark" } });
    await expect(page.locator("html")).toHaveClass(/dark/);
    const panel = await resolveColour(page, "#171a23");
    const ink = await resolveColour(page, "#e6e8ef");
    expect(await card(c).evaluate((el) => getComputedStyle(el).backgroundColor)).toBe(panel);
    expect(
      await row(c, 2)
        .locator("td")
        .nth(9)
        .evaluate((el) => getComputedStyle(el).color),
    ).toBe(ink);
    const open = await row(c, 1).evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(open).not.toBe("rgba(0, 0, 0, 0)");
  });
});
