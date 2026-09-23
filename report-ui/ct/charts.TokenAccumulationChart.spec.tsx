/**
 * The overview's accumulation chart: one mean line per suite × harness × model × effort (ADR 0049),
 * a min–max envelope when a group ran more than once, and the two different empty states.
 */
import { expect, test } from "./test";
import { TokenAccumulationChart } from "../src/components/charts/TokenAccumulationChart";
import { NO_MATCH } from "../src/lib/facets";
import type { HooksConfig } from "../playwright";
import type { Cell, RunResult } from "../src/lib/types";
import { call, cell, result, sweep, usage } from "./fixtures";
import { chips, drawnTitles, graph, readGraph, rgb, tokens, type TraceInfo } from "./charts.helpers";

/** Every cell served the default three-turn result under its own identity. */
const resultsFor = (cells: Cell[], over: (c: Cell) => Partial<RunResult> = () => ({})): Record<string, RunResult> =>
  Object.fromEntries(cells.map((c) => [c.session_id, result({ session_id: c.session_id, harness: c.harness, model: c.model, effort: c.effort, ...over(c) })]));

/** A result whose turns re-read `reads[i]` cache tokens and nothing else: billed per turn is exactly that. */
const flat = (reads: number[]): Partial<RunResult> => ({
  calls: reads.map((r, i) => call(i + 1, { usage: usage({ input_tokens: 0, output_tokens: 0, cache_read_tokens: r, cache_write_tokens: 0 }) })),
});
const cumsum = (xs: number[]): number[] => xs.reduce<number[]>((acc, v) => [...acc, (acc.at(-1) ?? 0) + v], []);

const SUITE = "eval_mermaid.py";
const mainLines = (traces: TraceInfo[]) => traces.filter((t) => t.mode === "lines+markers");

test.describe("TokenAccumulationChart", () => {
  test("draws one line per rung, rung-less keeps the pre-axis label, legend matches", async ({ mount }) => {
    const cells = sweep();
    const c = await mount(<TokenAccumulationChart cells={cells} results={resultsFor(cells)} />);
    const g = await readGraph(c);
    const lines = mainLines(g.traces);
    // seven arms, each run once: no envelopes
    expect(g.traces).toHaveLength(7);
    expect(lines).toHaveLength(7);
    const names = lines.map((t) => t.name);
    expect(names).toContain(`${SUITE} · claude/claude-opus-5 · max · n=1`);
    expect(names).toContain(`${SUITE} · claude/claude-opus-5 · low · n=1`);
    expect(names).toContain(`${SUITE} · claude/claude-opus-5 · high · n=1`);
    expect(names).toContain(`${SUITE} · claude/claude-sonnet-5 · medium · n=1`);
    expect(names).toContain(`${SUITE} · codex/gpt-5.6-sol · xhigh · n=1`);
    // the rung-less (pre-ADR 0049) session names no rung at all
    expect(names).toContain(`${SUITE} · claude/claude-opus-5 · n=1`);
    expect(names.filter((n) => n?.includes("null") || n?.includes("undefined"))).toEqual([]);
    await expect(chips(c)).toHaveText(names.map((n) => n!));
    await expect(graph(c).locator(".scatterlayer .trace")).toHaveCount(7);
    // x is the turn number, y the running bill
    expect(lines[0]!.x).toEqual([1, 2, 3]);
    expect(lines[0]!.y).toEqual([39_436, 114_072, 223_908]);
  });

  test("two rungs of one model are never averaged; two runs of one rung are", async ({ mount }) => {
    const cells = [cell({ session_id: "hi-1", effort: "high" }), cell({ session_id: "hi-2", effort: "high" }), cell({ session_id: "max-1", effort: "max" })];
    const reads: Record<string, number[]> = { "hi-1": [100, 100, 100], "hi-2": [300, 300], "max-1": [10_000, 10_000, 10_000] };
    const c = await mount(<TokenAccumulationChart cells={cells} results={resultsFor(cells, (x) => flat(reads[x.session_id]!))} />);
    const g = await readGraph(c);
    const lines = mainLines(g.traces);
    expect(lines.map((t) => t.name)).toEqual([`${SUITE} · claude/claude-opus-5 · high · n=2`, `${SUITE} · claude/claude-opus-5 · max · n=1`]);
    const [high, max] = lines;
    // mean over the runs that reached each turn: turn 3 only hi-1 reached
    expect(high!.x).toEqual([1, 2, 3]);
    expect(high!.y).toEqual([200, 400, 300]);
    expect(max!.y).toEqual(cumsum([10_000, 10_000, 10_000]));
    expect(high!.hovertemplate).toContain("mean after turn");
    expect(max!.hovertemplate).not.toContain("mean");
    // the n=2 group carries an envelope: max edge, then a min edge filled to it
    const band = g.traces.filter((t) => t.showlegend === false);
    expect(band).toHaveLength(2);
    expect(band[0]!.y).toEqual([300, 600, 300]);
    expect(band[1]!.y).toEqual([100, 200, 300]);
    expect(band[1]!.fill).toBe("tonexty");
    // washed in the line's own colour (series 1, #4f46e5) at a low alpha
    expect(band[1]!.fillcolor).toBe("rgba(79,70,229,0.15)");
    expect(high!.lineColor).toBe(tokens.themes.light.series[0]);
    await expect(chips(c)).toHaveCount(2);
  });

  test("a rung-less session and a rung of the same model stay two lines", async ({ mount }) => {
    const cells = [cell({ session_id: "old", effort: null }), cell({ session_id: "new", effort: "high" })];
    const c = await mount(<TokenAccumulationChart cells={cells} results={resultsFor(cells)} />);
    // the rung first: a rung-less line sorts after every rung, as a null does in every column
    await expect(chips(c)).toHaveText([`${SUITE} · claude/claude-opus-5 · high · n=1`, `${SUITE} · claude/claude-opus-5 · n=1`]);
  });

  // effort.ts: "A rung is a position on a ladder, so the page sorts rungs by that position and
  // never by spelling". `accumulationGroups` (lib/series.ts:236) keeps the order cells arrive in,
  // so the legend (and the colour each line is assigned) follows the index's data order.
  test("the legend lists one model's rungs in ladder order", async ({ mount }) => {
    const cells = sweep().filter((x) => x.model === "claude-opus-5");
    const c = await mount(<TokenAccumulationChart cells={cells} results={resultsFor(cells)} />);
    await expect(chips(c)).toHaveText(
      ["low", "high", "max"].map((r) => `${SUITE} · claude/claude-opus-5 · ${r} · n=1`).concat(`${SUITE} · claude/claude-opus-5 · n=1`),
      { timeout: 2_000 },
    );
  });

  // The grouping gained effort (ADR 0049) but the panel note (TokenAccumulationChart.tsx:84) and
  // the plot's aria-label (:91) still describe "one line per suite × harness × model".
  test("the note and aria-label name effort as a grouping axis", async ({ mount }) => {
    const cells = sweep();
    const c = await mount(<TokenAccumulationChart cells={cells} results={resultsFor(cells)} />);
    await expect(c.locator("#TokenAccumulationChart")).toContainText(/effort|rung/, { timeout: 2_000 });
    await expect(graph(c)).toHaveAttribute("aria-label", /effort|rung/, { timeout: 1_000 });
  });

  test("filtered to nothing says so, and does not blame a missing ledger", async ({ mount }) => {
    const c = await mount(<TokenAccumulationChart cells={[]} results={{}} />);
    await expect(c.getByText(NO_MATCH)).toBeVisible();
    await expect(c.getByText("No session with a per-call ledger")).toHaveCount(0);
    await expect(graph(c)).toHaveCount(0);
  });

  test("cells with no ledger, or no loaded result, draw nothing and say why", async ({ mount }) => {
    const cells = [cell({ session_id: "no-ledger", has_ledger: false }), cell({ session_id: "loading" })];
    const c = await mount(<TokenAccumulationChart cells={cells} results={{ "no-ledger": result({ session_id: "no-ledger" }), loading: null }} />);
    await expect(c.getByText("No session with a per-call ledger yet; run the evals or the replay.")).toBeVisible();
    await expect(graph(c)).toHaveCount(0);
  });

  test("a ledgered session beside unledgered ones is the only line", async ({ mount }) => {
    const cells = [cell({ session_id: "a", effort: "low", has_ledger: false }), cell({ session_id: "b", effort: "high" })];
    const c = await mount(<TokenAccumulationChart cells={cells} results={resultsFor(cells)} />);
    await expect(chips(c)).toHaveText([`${SUITE} · claude/claude-opus-5 · high · n=1`]);
  });

  test("axis titles, panel heading and closest hover", async ({ mount }) => {
    const cells = sweep();
    const c = await mount(<TokenAccumulationChart cells={cells} results={resultsFor(cells)} />);
    const g = await readGraph(c);
    expect(g.hovermode).toBe("closest");
    const t = await drawnTitles(c);
    expect(t.x).toBe("turn");
    expect(t.y).toBe("accumulative_billed_tokens so far");
    await expect(c.locator("#TokenAccumulationChart")).toContainText("accumulative_billed_tokens accumulating per turn");
    await expect(c.locator('[data-el="TokenAccumulationChart"] .el').first()).toHaveText("TokenAccumulationChart");
  });

  test("hovering a point names its value, turn and arm", async ({ mount, page }) => {
    const cells = [cell({ session_id: "solo", effort: "xhigh" })];
    const c = await mount(<TokenAccumulationChart cells={cells} results={resultsFor(cells)} />);
    await readGraph(c);
    const point = graph(c).locator(".scatterlayer .point").nth(1);
    const box = (await point.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    const hover = graph(c).locator(".hoverlayer .hovertext");
    await expect(hover).toContainText("114,072 after turn 2");
    await expect(hover).toContainText(`${SUITE} · claude/claude-opus-5 · xhigh · n=1`);
  });

  test("a legend chip hides its line, and its envelope, then brings them back", async ({ mount }) => {
    const cells = [cell({ session_id: "h1", effort: "high" }), cell({ session_id: "h2", effort: "high" }), cell({ session_id: "l1", effort: "low" })];
    const c = await mount(<TokenAccumulationChart cells={cells} results={resultsFor(cells, (x) => flat(x.session_id === "h2" ? [5, 5, 5] : [1, 1, 1]))} />);
    // ladder order: `low` leads the legend, so the high group's three traces come after its one
    const chip = chips(c).nth(1);
    await expect(chip).toHaveText(`${SUITE} · claude/claude-opus-5 · high · n=2`);
    await expect(chip).toHaveAttribute("aria-pressed", "true");
    await chip.click();
    await expect(chip).toHaveAttribute("aria-pressed", "false");
    await expect.poll(async () => (await readGraph(c)).traces.map((t) => t.visible)).toEqual([true, "legendonly", "legendonly", "legendonly"]);
    await chip.click();
    await expect.poll(async () => (await readGraph(c)).traces.map((t) => t.visible)).toEqual([true, true, true, true]);
  });

  test("past the palette, series cycle colours with a new dash per lap", async ({ mount }) => {
    const cells = Array.from({ length: 10 }, (_, i) => cell({ session_id: `m${i}`, model: `model-${i}` }));
    const c = await mount(<TokenAccumulationChart cells={cells} results={resultsFor(cells)} />);
    const lines = mainLines((await readGraph(c)).traces);
    const series = tokens.themes.light.series;
    expect(lines.map((t) => t.lineColor)).toEqual([...series, series[0], series[1]]);
    expect(lines.map((t) => t.lineDash)).toEqual([...Array(8).fill("solid"), "dash", "dash"]);
  });

  for (const mode of ["light", "dark"] as const) {
    test(`lines and legend swatches take the ${mode} series tokens`, async ({ mount }) => {
      const theme = tokens.themes[mode];
      const cells = sweep().slice(0, 3);
      const c = await mount<HooksConfig>(<TokenAccumulationChart cells={cells} results={resultsFor(cells)} />, { hooksConfig: { mode } });
      const g = await readGraph(c);
      expect(mainLines(g.traces).map((t) => t.lineColor)).toEqual(theme.series.slice(0, 3));
      expect(g.fontColor).toBe(theme.ink);
      await expect(graph(c).locator(".scatterlayer .js-line").first()).toHaveCSS("stroke", rgb(theme.series[0]!));
      await expect(chips(c).first().locator("div[aria-hidden]").first()).toHaveCSS("background-color", rgb(theme.series[0]!));
    });
  }

  // A project may override the series tokens (`xharness_report_design_tokens`) with any CSS
  // colour Plotly parses; the envelope only handled `#rrggbb` and fell back to a grey wash that
  // no longer matched its line.
  for (const [token, drawn] of [
    ["#4f46e5", "rgb(79, 70, 229)"],
    ["#36c", "rgb(51, 102, 204)"],
    ["rgb(51, 102, 204)", "rgb(51, 102, 204)"],
  ] as const) {
    test(`the envelope takes the line's own colour for a ${token} series token`, async ({ mount, page }) => {
      const cells = [cell({ session_id: "h1", effort: "high" }), cell({ session_id: "h2", effort: "high" })];
      const c = await mount(<TokenAccumulationChart cells={cells} results={resultsFor(cells, (x) => flat(x.session_id === "h2" ? [5, 5] : [1, 1]))} />);
      await readGraph(c);
      await page.evaluate((col) => document.documentElement.style.setProperty("--xh-series-1", col), token);
      await expect.poll(async () => mainLines((await readGraph(c)).traces)[0]!.lineColor).toBe(token);
      const fill = await graph(c)
        .locator(".scatterlayer .js-fill")
        .first()
        .evaluate((p) => {
          const s = getComputedStyle(p);
          // the effective wash: the fill's own alpha, its path, and the trace group Plotly drew it in
          return { fill: s.fill, opacity: Number(s.fillOpacity) * Number(s.opacity) * Number(getComputedStyle(p.closest(".trace")!).opacity) };
        });
      expect(fill.fill).toBe(drawn);
      expect(fill.opacity).toBeGreaterThan(0.05);
      expect(fill.opacity).toBeLessThan(0.3);
    });
  }

  test("flipping the theme on the root re-colours the drawn lines", async ({ mount, page }) => {
    const cells = sweep().slice(0, 1);
    const c = await mount(<TokenAccumulationChart cells={cells} results={resultsFor(cells)} />);
    await expect(graph(c).locator(".scatterlayer .js-line").first()).toHaveCSS("stroke", rgb(tokens.themes.light.series[0]!));
    await page.evaluate((dark) => {
      const root = document.documentElement;
      dark.series.forEach((col, i) => root.style.setProperty(`--xh-series-${i + 1}`, col));
      root.style.setProperty("--xh-ink", dark.ink);
      root.classList.add("dark");
    }, tokens.themes.dark);
    await expect(graph(c).locator(".scatterlayer .js-line").first()).toHaveCSS("stroke", rgb(tokens.themes.dark.series[0]!));
    await expect.poll(async () => (await readGraph(c)).fontColor).toBe(tokens.themes.dark.ink);
  });

  test("wide: the legend sits beside the plot; narrow: it wraps beneath", async ({ mount, page }) => {
    const cells = sweep();
    await page.setViewportSize({ width: 1280, height: 900 });
    const c = await mount(<TokenAccumulationChart cells={cells} results={resultsFor(cells)} />);
    await readGraph(c);
    const legend = c.locator('[data-el="ChartLegend"]');
    let plot = (await graph(c).boundingBox())!;
    let leg = (await legend.boundingBox())!;
    expect(leg.x).toBeGreaterThanOrEqual(plot.x + plot.width);
    expect(leg.y).toBeLessThan(plot.y + plot.height);
    const wide = plot.width;

    await page.setViewportSize({ width: 500, height: 900 });
    await expect.poll(async () => (await legend.boundingBox())!.y).toBeGreaterThanOrEqual(plot.y + plot.height);
    plot = (await graph(c).boundingBox())!;
    leg = (await legend.boundingBox())!;
    expect(plot.width).toBeLessThan(wide);
    await expect.poll(async () => (await readGraph(c)).width).toBeLessThanOrEqual(Math.ceil(plot.width));
    expect(leg.y).toBeGreaterThanOrEqual(plot.y + plot.height);
  });
});
