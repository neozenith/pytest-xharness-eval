/**
 * CostByTierPanel (and its RatesApplied block): the `cost_by_tier` rows that sum to
 * `estimated_cost_usd`, the harness's own per-model estimate, its reported total, and the
 * per-tier USD-per-token rates the estimate used (ADR 0019, ADR 0021).
 */
import { expect, test } from "@playwright/experimental-ct-react";
import type { Locator } from "@playwright/test";
import { CostByTierPanel, RatesApplied } from "../src/components/panels/CostByTierPanel";
import { PHONE, pageOverflowX, resolveColour, result } from "./panels.data";

const costRows = (c: Locator) => c.locator("#CostByTierPanel tr");
const rateRows = (c: Locator) => c.locator("#RatesApplied tr");
const texts = async (rows: Locator) =>
  await rows.evaluateAll((trs) => trs.map((tr) => [...tr.querySelectorAll("td")].map((td) => (td.textContent ?? "").trim())));
const usd = (s: string) => Number(s.replace("$", ""));

test("every tier, the estimate, the harness's per-model estimate and its reported total, in order", async ({ mount }) => {
  const c = await mount(<CostByTierPanel result={result()} />);
  expect(await texts(costRows(c))).toEqual([
    ["cache_read", "$0.2742"],
    ["cache_write_1h", "$0.3832"],
    ["cache_write_5m", "$0.0000"],
    ["input", "$0.0001"],
    ["output", "$0.3701"],
    ["estimated_cost_usd", "$1.0276"],
    ["harness estimate · claude-haiku-4-5-20251001", "$0.0011 (1,063 in · 15 out · 0 read · 0 write)"],
    ["harness_reported_cost_usd", "$1.0288"],
  ]);
});

test("the tier rows sum to estimated_cost_usd (to the displayed precision)", async ({ mount }) => {
  const c = await mount(<CostByTierPanel result={result()} />);
  const rows = await texts(costRows(c));
  const tiers = rows.slice(0, 5).map(([, v]) => usd(v!));
  const estimate = usd(rows[5]![1]!);
  expect(Math.abs(tiers.reduce((a, b) => a + b, 0) - estimate)).toBeLessThanOrEqual(0.0005 * tiers.length);
});

test("the estimate and the harness total are bold; the per-model detail is muted", async ({ mount, page }) => {
  const c = await mount(<CostByTierPanel result={result()} />);
  await expect(costRows(c).nth(5).locator("b")).toHaveText("$1.0276");
  await expect(costRows(c).nth(7).locator("b")).toHaveText("$1.0288");
  const detail = costRows(c).nth(6).locator(".muted");
  await expect(detail).toHaveText("(1,063 in · 15 out · 0 read · 0 write)");
  expect(await detail.evaluate((el) => getComputedStyle(el).color)).toBe(await resolveColour(page, "var(--xh-muted)"));
});

test("keys sit left in the mono key style, values right-aligned", async ({ mount }) => {
  const c = await mount(<CostByTierPanel result={result()} />);
  const [key, value] = [costRows(c).first().locator("td").nth(0), costRows(c).first().locator("td").nth(1)];
  await expect(key).toHaveClass(/key/);
  await expect(value).toHaveClass(/num/);
  await expect(value).toHaveCSS("text-align", "right");
  expect(await key.evaluate((el) => getComputedStyle(el).fontFamily)).toMatch(/mono/i);
});

test("one harness-estimate row per model the harness reported, missing counts as the no-value glyph", async ({ mount }) => {
  const c = await mount(
    <CostByTierPanel
      result={result({
        reported_model_usage: {
          "claude-sonnet-5": { costUSD: 1.0277, inputTokens: 32, outputTokens: 37_009, cacheReadInputTokens: 1_371_238, cacheCreationInputTokens: 95_811 },
          "claude-haiku-4-5": { inputTokens: 10 },
        },
      })}
    />,
  );
  const rows = await texts(costRows(c));
  expect(rows).toContainEqual(["harness estimate · claude-sonnet-5", "$1.0277 (32 in · 37,009 out · 1,371,238 read · 95,811 write)"]);
  expect(rows).toContainEqual(["harness estimate · claude-haiku-4-5", "– (10 in · – out · – read · – write)"]);
});

test("no harness_reported_cost_usd: that row is left out, not printed as a dash", async ({ mount }) => {
  const c = await mount(<CostByTierPanel result={result({ harness_reported_cost_usd: null, reported_model_usage: undefined })} />);
  const keys = (await texts(costRows(c))).map(([k]) => k);
  expect(keys).not.toContain("harness_reported_cost_usd");
  expect(keys.at(-1)).toBe("estimated_cost_usd");
});

test("an estimate of null prints the no-value glyph", async ({ mount }) => {
  const c = await mount(<CostByTierPanel result={result({ estimated_cost_usd: null })} />);
  expect(await texts(costRows(c))).toContainEqual(["estimated_cost_usd", "–"]);
});

test("a result from before the ledger points at the replay, for tiers and rates alike", async ({ mount }) => {
  const c = await mount(
    <CostByTierPanel result={result({ cost_by_tier: undefined, rates_applied: {}, reported_model_usage: undefined, harness_reported_cost_usd: null })} />,
  );
  expect(await texts(costRows(c))).toEqual([["no cost_by_tier", "this result predates ADR 0019; replay the captured directory"]]);
  expect(await texts(rateRows(c))).toEqual([["no rates_applied", "this result predates ADR 0021; replay the captured directory"]]);
});

test("an empty cost_by_tier is the same as none, and still shows the harness figures", async ({ mount }) => {
  const c = await mount(<CostByTierPanel result={result({ cost_by_tier: {} })} />);
  const rows = await texts(costRows(c));
  expect(rows[0]).toEqual(["no cost_by_tier", "this result predates ADR 0019; replay the captured directory"]);
  expect(rows.map(([k]) => k)).toContain("harness_reported_cost_usd");
});

test.describe("RatesApplied", () => {
  test("every rate shown per million tokens, with the price row and its source", async ({ mount }) => {
    const c = await mount(<CostByTierPanel result={result()} />);
    expect(await texts(rateRows(c))).toEqual([
      ["price row", "claude-sonnet-5"],
      ["source file", "prices.toml"],
      ["applied at", "2026-08-23T11:47:31+00:00"],
      ["input", "$2.000 /M"],
      ["output", "$10.000 /M"],
      ["cache_read", "$0.200 /M"],
      ["cache_write (5m)", "$2.500 /M"],
      ["cache_write_1h", "$4.000 /M"],
    ]);
    await expect(rateRows(c).nth(0).locator("code")).toHaveText("claude-sonnet-5");
    await expect(c.getByText("rates applied (USD per token)")).toBeVisible();
    await expect(c.locator('.el[data-el="RatesApplied"]')).toHaveText("RatesApplied");
  });

  test("a partial rates row: a missing rate is the no-value glyph, a missing time is blank", async ({ mount }) => {
    const c = await mount(<RatesApplied rates={{ model: "gpt-5.6-sol", source: "pyproject.toml [xharness_prices]", input: 1.25e-6, output: 1e-5 }} />);
    expect(await texts(rateRows(c))).toEqual([
      ["price row", "gpt-5.6-sol"],
      ["source file", "pyproject.toml [xharness_prices]"],
      ["applied at", ""],
      ["input", "$1.250 /M"],
      ["output", "$10.000 /M"],
      ["cache_read", "–"],
      ["cache_write (5m)", "–"],
      ["cache_write_1h", "–"],
    ]);
  });

  for (const [name, rates] of [
    ["null", null],
    ["undefined", undefined],
  ] as const) {
    test(`${name} rates point at the replay`, async ({ mount }) => {
      const c = await mount(<RatesApplied rates={rates} />);
      expect(await texts(rateRows(c))).toEqual([["no rates_applied", "this result predates ADR 0021; replay the captured directory"]]);
    });
  }
});

test("the card names itself and holds at phone width", async ({ mount, page }) => {
  await page.setViewportSize(PHONE);
  const c = await mount(<CostByTierPanel result={result()} />);
  await expect(c.getByText("Cost by tier and rates applied")).toBeVisible();
  await expect(c.locator('.el[data-el="CostByTierPanel"]')).toHaveText("CostByTierPanel");
  expect(await pageOverflowX(page)).toBeLessThanOrEqual(0);
});

test("dark mode: the card is the dark panel and keys are the dark muted ink", async ({ mount, page }) => {
  const c = await mount(<CostByTierPanel result={result()} />, { hooksConfig: { mode: "dark" } });
  const card = c.locator('[data-el="CostByTierPanel"]').first();
  expect(await card.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe(await resolveColour(page, "#171a23"));
  expect(
    await costRows(c)
      .first()
      .locator("td.key")
      .evaluate((el) => getComputedStyle(el).color),
  ).toBe(await resolveColour(page, "#9aa0b0"));
});
