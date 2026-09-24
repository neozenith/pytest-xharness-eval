/**
 * ReconciliationPanel: the ledger built from the session log beside the harness's own
 * aggregate, row by row, with `=` where they agree and `Δ` where they do not. The tier rows
 * compare the primary thread's share; spawned subagents are their own row
 * (docs/token-accounting.md §5).
 */
import { expect, test } from "./test";
import type { Locator } from "@playwright/test";
import { ReconciliationPanel } from "../src/components/panels/ReconciliationPanel";
import type { RunResult } from "../src/lib/types";
import { PHONE, pageOverflowX, resolveColour, result, subagent, usage } from "./panels.data";

const rows = (c: Locator) => c.locator("#ReconciliationPanel tr");
const texts = async (c: Locator) => rows(c).evaluateAll((trs) => trs.map((tr) => [...tr.querySelectorAll("td")].map((td) => (td.textContent ?? "").trim())));
const row = (c: Locator, key: string) => rows(c).filter({ has: c.page().locator("td.key", { hasText: new RegExp(`^${key.replace(/[()]/g, "\\$&")}$`) }) });
const verdict = (c: Locator, key: string) => row(c, key).locator("td").nth(3);

test("every row of a claude result: ledger, harness aggregate, and the verdict", async ({ mount }) => {
  const c = await mount(<ReconciliationPanel result={result()} />);
  expect(await texts(c)).toEqual([
    ["", "ledger", "harness aggregate", ""],
    ["turns (model calls)", "2", "23", "Δ 21"],
    ["input (uncached)", "32", "32", "="],
    ["output", "37,009", "37,009", "="],
    ["cache read", "1,371,238", "1,371,238", "="],
    ["cache write", "95,811", "95,811", "="],
    ["of which 1h / 5m", "95,811 / 0", "", ""],
    ["reasoning (inside output)", "28,719", "–", ""],
    ["accumulative_billed_tokens", "1,504,090", "–", ""],
    ["baseline_tokens", "35,599", "", ""],
    ["estimated / harness reported cost", "$1.0276", "$1.0288", "Δ $0.0011"],
  ]);
  await expect(rows(c).first().locator("b")).toHaveText(["ledger", "harness aggregate"]);
});

for (const mode of ["light", "dark"] as const) {
  test(`${mode}: agreement is the good colour, a difference the warn colour`, async ({ mount, page }) => {
    const c = await mount(<ReconciliationPanel result={result()} />, { hooksConfig: { mode } });
    const eq = verdict(c, "input (uncached)").locator(".good");
    const delta = verdict(c, "turns (model calls)").locator(".warn");
    await expect(eq).toHaveText("=");
    await expect(delta).toHaveText("Δ 21");
    expect(await eq.evaluate((el) => getComputedStyle(el).color)).toBe(await resolveColour(page, "var(--xh-good)"));
    expect(await delta.evaluate((el) => getComputedStyle(el).color)).toBe(await resolveColour(page, "var(--xh-warn)"));
    const expectedGood = mode === "dark" ? "rgb(52, 211, 153)" : await resolveColour(page, "var(--xh-good)");
    expect(await eq.evaluate((el) => getComputedStyle(el).color)).toBe(expectedGood);
  });
}

test("a ledger above the harness figure is a negative Δ", async ({ mount }) => {
  const c = await mount(
    <ReconciliationPanel
      result={result({ reported_usage: { input_tokens: 27, output_tokens: 37_009, cache_read_input_tokens: 1_371_238, cache_creation_input_tokens: 95_811 } })}
    />,
  );
  await expect(verdict(c, "input (uncached)")).toHaveText("Δ -5");
});

test("vendor total_tokens and reasoning sit beside the ledger's, without a verdict", async ({ mount }) => {
  const c = await mount(
    <ReconciliationPanel
      result={result({ reported_usage: { input_tokens: 32, output_tokens: 37_009, reasoning_output_tokens: 28_000, total_tokens: 1_504_090 } })}
    />,
  );
  expect(await row(c, "reasoning (inside output)").locator("td").allTextContents()).toEqual(["reasoning (inside output)", "28,719", "28,000", ""]);
  expect(await row(c, "accumulative_billed_tokens").locator("td").allTextContents()).toEqual(["accumulative_billed_tokens", "1,504,090", "1,504,090", ""]);
  // the harness never reported the cache tiers here: no figure, no verdict
  expect(await row(c, "cache read").locator("td").allTextContents()).toEqual(["cache read", "1,371,238", "–", ""]);
});

test("no reported_usage at all: every harness cell is the no-value glyph and nothing is judged", async ({ mount }) => {
  const c = await mount(<ReconciliationPanel result={result({ reported_usage: undefined })} />);
  for (const key of ["input (uncached)", "output", "cache read", "cache write"]) {
    await expect(row(c, key).locator("td").nth(2)).toHaveText("–");
    await expect(verdict(c, key)).toHaveText("");
  }
  // turns still compare: reported_turns is on the result itself
  await expect(verdict(c, "turns (model calls)")).toHaveText("Δ 21");
});

test("no harness cost: the cost row shows the dash and no Δ", async ({ mount }) => {
  const c = await mount(<ReconciliationPanel result={result({ harness_reported_cost_usd: null })} />);
  expect(await row(c, "estimated / harness reported cost").locator("td").allTextContents()).toEqual(["estimated / harness reported cost", "$1.0276", "–", ""]);
});

test("matching turns read =", async ({ mount }) => {
  const c = await mount(<ReconciliationPanel result={result({ reported_turns: 2 })} />);
  await expect(verdict(c, "turns (model calls)")).toHaveText("=");
});

test.describe("codex", () => {
  const codex = (over: Partial<RunResult> = {}) =>
    result({
      harness: "codex",
      reported_usage: { input_tokens: 517_418, cached_input_tokens: 471_552, output_tokens: 10_383, reasoning_output_tokens: 3006, total_tokens: 527_801 },
      ...over,
    });

  test("the vendor's inclusive input has its cached share subtracted; cached is the read tier", async ({ mount }) => {
    const c = await mount(<ReconciliationPanel result={codex()} />);
    await expect(row(c, "input (uncached)").locator("td").nth(2)).toHaveText("45,866");
    await expect(row(c, "cache read").locator("td").nth(2)).toHaveText("471,552");
    await expect(row(c, "cache write").locator("td").nth(2)).toHaveText("–");
    await expect(row(c, "accumulative_billed_tokens").locator("td").nth(2)).toHaveText("527,801");
    await expect(row(c, "reasoning (inside output)").locator("td").nth(2)).toHaveText("3,006");
  });

  test("a codex ledger that matches the vendor reads = on every tier it reports", async ({ mount }) => {
    const c = await mount(
      <ReconciliationPanel
        result={codex({
          usage: usage({
            input_tokens: 45_866,
            output_tokens: 10_383,
            cache_read_tokens: 471_552,
            cache_write_tokens: 0,
            cache_write_1h_tokens: 0,
            reasoning_tokens: 3006,
          }),
        })}
      />,
    );
    for (const key of ["input (uncached)", "output", "cache read"]) await expect(verdict(c, key)).toHaveText("=");
  });

  test("cached_input_tokens of 0 subtracts nothing", async ({ mount }) => {
    const c = await mount(<ReconciliationPanel result={codex({ reported_usage: { input_tokens: 32, cached_input_tokens: 0, output_tokens: 1 } })} />);
    await expect(row(c, "input (uncached)").locator("td").nth(2)).toHaveText("32");
    await expect(verdict(c, "input (uncached)")).toHaveText("=");
  });
});

test.describe("subagents", () => {
  test("one thread: the tier rows compare the primary share, the thread's bill is its own row", async ({ mount }) => {
    const c = await mount(
      <ReconciliationPanel
        result={result({ usage: usage({ input_tokens: 132, output_tokens: 314, accumulative_billed_tokens: undefined }), subagents: [subagent()] })}
      />,
    );
    await expect(row(c, "input (uncached)").locator("td").nth(1)).toHaveText("32");
    await expect(row(c, "output").locator("td").nth(1)).toHaveText("264");
    expect(await row(c, "subagents (1 spawned thread)").locator("td").allTextContents()).toEqual([
      "subagents (1 spawned thread)",
      "150",
      "not in the harness figure",
      "",
    ]);
    await expect(row(c, "subagents (1 spawned thread)").locator("td").nth(2).locator(".muted")).toHaveText("not in the harness figure");
  });

  test("several threads: plural, the bills summed, the fallback bill for a thread with no total", async ({ mount }) => {
    const subs = [
      subagent(),
      subagent({
        id: "b",
        usage: usage({ input_tokens: 10, output_tokens: 20, cache_read_tokens: 30, cache_write_tokens: 40, cache_write_1h_tokens: 0, reasoning_tokens: 0 }),
      }),
    ];
    const c = await mount(<ReconciliationPanel result={result({ subagents: subs })} />);
    await expect(row(c, "subagents (2 spawned threads)").locator("td").nth(1)).toHaveText("250");
  });

  test("the subagent row sits between reasoning and the billed total", async ({ mount }) => {
    const c = await mount(<ReconciliationPanel result={result({ subagents: [subagent()] })} />);
    const keys = (await texts(c)).map(([k]) => k);
    expect(keys.indexOf("subagents (1 spawned thread)")).toBe(keys.indexOf("reasoning (inside output)") + 1);
    expect(keys.indexOf("accumulative_billed_tokens")).toBe(keys.indexOf("subagents (1 spawned thread)") + 1);
  });

  test("no subagents: no subagent row", async ({ mount }) => {
    const c = await mount(<ReconciliationPanel result={result({ subagents: [] })} />);
    expect((await texts(c)).map(([k]) => k).some((k) => k?.startsWith("subagents"))).toBe(false);
  });
});

test("the description explains the primary-thread scope and the title side call", async ({ mount }) => {
  const c = await mount(<ReconciliationPanel result={result()} />);
  await expect(c.getByText(/^Reconciliation/).first()).toBeVisible();
  await expect(c.locator('.el[data-el="ReconciliationPanel"]')).toHaveText("ReconciliationPanel");
  await expect(c).toContainText("The harness figure covers only the primary thread");
  await expect(c).toContainText("~$0.001 session-title side call");
});

test("the description wraps and the page holds at phone width", async ({ mount, page }) => {
  await page.setViewportSize(PHONE);
  const c = await mount(<ReconciliationPanel result={result()} />);
  await expect(rows(c)).toHaveCount(11);
  expect(await pageOverflowX(page)).toBeLessThanOrEqual(0);
});
