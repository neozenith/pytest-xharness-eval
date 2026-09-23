/**
 * `SessionSummaryTable`: the rolled-up view of exactly the cells `SessionTable` lists, one row per
 * skill × case × harness × model × effort (ADR 0042, ADR 0049). It sorts on its own `ssort`/`sdir`
 * pair, and only in its fixed key order does it band by skill and mute a repeated skill. Each test
 * states its cells and, where the order matters, a `hooksConfig.search`.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import type { Page } from "@playwright/test";
import { SessionSummaryTable } from "../src/components/SessionSummaryTable";
import { cell, sweep } from "./fixtures";

const MUTED = { light: "rgb(91, 96, 112)", dark: "rgb(154, 160, 176)" };
const BAD = { light: "rgb(185, 28, 28)", dark: "rgb(248, 113, 113)" };
const NONE = "–";
const NO_MATCH = "No session matches the current filters.";

const KEYS = ["skill", "case", "harness", "model", "effort", "runs", "pass", "cost", "billed", "peak", "turns", "tools", "coverage", "tps", "wall"];
const col = (key: string) => KEYS.indexOf(key);

/** The sweep fixture's groups, in the fixed key order: skill, case, harness, model, then the ladder. */
const OPUS = "mermaidjs-diagrams|eval_dual_density|claude|claude-opus-5";
const SWEEP_KEYS = [
  "discovery|eval_map|codex|gpt-5.6-luna|low",
  `${OPUS}|low`,
  `${OPUS}|high`,
  `${OPUS}|max`,
  // The rung-less group keeps its pre-axis key byte for byte: no trailing `|`.
  OPUS,
  "mermaidjs-diagrams|eval_dual_density|claude|claude-sonnet-5|medium",
  "mermaidjs-diagrams|eval_dual_density|codex|gpt-5.6-sol|xhigh",
];

const rows = (page: Page) => page.locator("#SessionSummaryTable tbody tr[data-key]");
const keys = (page: Page) => rows(page).evaluateAll((trs) => trs.map((tr) => tr.getAttribute("data-key")));
const column = (page: Page, key: string) => rows(page).evaluateAll((trs, i) => trs.map((tr) => (tr.children[i] as HTMLElement).innerText), col(key));
const head = (page: Page, key: string) => page.locator(`#SessionSummaryTable thead th[data-k="${key}"]`);
const search = (page: Page) => page.evaluate(() => location.search);
const row = (page: Page, key: string) => page.locator(`#SessionSummaryTable tbody tr[data-key="${key}"]`);
const td = (page: Page, key: string, column: string) => row(page, key).locator("td").nth(col(column));

test.describe("SessionSummaryTable: rendering", () => {
  test("renders one row per group, in the fixed key order, with every column", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />);
    expect(await keys(page)).toEqual(SWEEP_KEYS);
    expect(await page.locator("#SessionSummaryTable thead th").evaluateAll((ths) => ths.map((th) => th.getAttribute("data-k")))).toEqual(KEYS);
    await expect(page.locator('#SessionSummaryTable thead th[aria-sort="none"]')).toHaveCount(KEYS.length);
  });

  test("the caption says once what every measure head no longer prints", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />);
    const caption = page.locator("#SessionSummaryTable caption");
    await expect(caption).toHaveText("every measure is the arithmetic mean over the runs in its group that carry that field");
    await expect(caption.locator(".const")).toHaveText("arithmetic mean");
    await expect(caption).toHaveCSS("caption-side", "top");
  });

  test("every measure head answers to `mean <field>` in full, while printing the short label", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />);
    for (const [label, name] of [
      ["cost", "mean estimated_cost_usd"],
      ["billed", "mean accumulative_billed_tokens"],
      ["peak ctx", "mean peak_context_tokens"],
      ["turns", "mean turns"],
      ["tools", "mean tool_calls"],
      ["coverage", "mean skill_coverage loaded share"],
      ["tok/s", "mean output_tokens_per_sec"],
      ["wall", "mean wall_ms"],
      ["pass rate", "verdict pass rate"],
    ]) {
      const button = page.getByRole("button", { name: `${label} — ${name}` });
      await expect(button).toBeVisible();
      await expect(button).toHaveText(label!);
    }
    const effort = page.getByRole("button", { name: "effort", exact: true });
    await expect(effort).toHaveAttribute("aria-describedby", "SessionSummaryTable-def-effort");
    await expect(effort).toHaveAccessibleDescription(/^effort — the reasoning rung every run in this group was sent/);
  });

  test("the metrics half opens on runs, which draws the dividing rule", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />);
    const grouped = page.locator('#SessionSummaryTable thead th[data-group="metrics"]');
    await expect(grouped).toHaveCount(1);
    await expect(grouped).toHaveAttribute("data-k", "runs");
    await expect(grouped).toHaveCSS("border-left-width", "1px");
    await expect(td(page, SWEEP_KEYS[0]!, "runs")).toHaveCSS("text-align", "right");
  });

  test("a group's measures are the means over its runs", async ({ mount, page }) => {
    await mount(
      <SessionSummaryTable
        cells={[
          cell({ session_id: "m-1", effort: "high", estimated_cost_usd: 1, turns: 2, tool_calls: 10, wall_ms: 10_000, output_tokens_per_sec: 50 }),
          cell({ session_id: "m-2", effort: "high", estimated_cost_usd: 3, turns: 5, tool_calls: 11, wall_ms: 20_000, output_tokens_per_sec: 60 }),
        ]}
      />,
    );
    const key = `${OPUS}|high`;
    await expect(td(page, key, "runs")).toHaveText("2");
    await expect(td(page, key, "cost")).toHaveText("$2.0000");
    await expect(td(page, key, "turns")).toHaveText("3.5");
    await expect(td(page, key, "tools")).toHaveText("10.5");
    await expect(td(page, key, "wall")).toHaveText("15.0s");
    await expect(td(page, key, "tps")).toHaveText("55.00");
    await expect(td(page, key, "coverage")).toHaveText("40.0%");
    await expect(td(page, key, "billed").locator("span")).toHaveText("1.5M");
    await expect(td(page, key, "billed").locator("span")).toHaveAttribute("title", "1,504,090");
    await expect(td(page, key, "peak")).toContainText("· 12.0%");
    await expect(td(page, key, "model").locator("code")).toHaveText("opus-5");
    await expect(td(page, key, "model").locator("code")).toHaveAttribute("title", "claude-opus-5");
    await expect(td(page, key, "case").locator("span")).toHaveText("dual_density");
  });

  test("a mean is over the runs that carry the field, never counting a missing one as zero", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={[cell({ session_id: "p-1", estimated_cost_usd: 2 }), cell({ session_id: "p-2", estimated_cost_usd: null })]} />);
    await expect(td(page, OPUS, "runs")).toHaveText("2");
    await expect(td(page, OPUS, "cost")).toHaveText("$2.0000");
  });

  test("a measure no run carries is the muted glyph", async ({ mount, page }) => {
    await mount(
      <SessionSummaryTable
        cells={[
          cell({
            estimated_cost_usd: null,
            accumulative_billed_tokens: null,
            peak_context_tokens: null,
            turns: null,
            skill_coverage: {},
            output_tokens_per_sec: null,
            wall_ms: null,
            verdict: null,
          }),
        ]}
      />,
    );
    for (const key of ["pass", "cost", "billed", "peak", "turns", "coverage", "tps", "wall"]) {
      const glyph = td(page, OPUS, key).locator("> span.muted");
      await expect(glyph, key).toHaveText(NONE);
      await expect(glyph, key).toHaveCSS("color", MUTED.light);
    }
  });

  test("an empty set of cells keeps the head and caption and says why the body is empty", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={[]} />);
    await expect(rows(page)).toHaveCount(0);
    const empty = page.locator("#SessionSummaryTable td.empty");
    await expect(empty).toHaveText(NO_MATCH);
    await expect(empty).toHaveAttribute("colspan", String(KEYS.length));
    await expect(page.locator("#SessionSummaryTable thead th")).toHaveCount(KEYS.length);
    await expect(page.locator("#SessionSummaryTable caption")).toBeVisible();
  });

  test("the head is pinned to the top of its own scroll box", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />);
    await expect(head(page, "skill")).toHaveCSS("position", "sticky");
  });

  test("renders in dark mode with the dark tokens", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={[cell({ session_id: "d-1", effort: "high", verdict: "fail" }), cell({ session_id: "d-2" })]} />, {
      hooksConfig: { mode: "dark" },
    });
    await expect(rows(page)).toHaveCount(2);
    await expect(page.locator("body")).toHaveCSS("background-color", "rgb(15, 17, 23)");
    await expect(td(page, `${OPUS}|high`, "pass").locator(".bad")).toHaveCSS("color", BAD.dark);
    await expect(td(page, OPUS, "effort").locator("> span.muted")).toHaveCSS("color", MUTED.dark);
    await expect(td(page, OPUS, "skill")).toHaveCSS("color", MUTED.dark);
  });
});

test.describe("SessionSummaryTable: pass rate", () => {
  test("a group that did not pass clean takes the bad ink at 600 weight; the percentage stays muted", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={[cell({ session_id: "f-1", verdict: "pass" }), cell({ session_id: "f-2", verdict: "fail" })]} />);
    const cellEl = td(page, OPUS, "pass");
    await expect(cellEl).toHaveText("1/2 · 50.0%");
    const fraction = cellEl.locator("span.bad.strong");
    await expect(fraction).toHaveText("1/2");
    await expect(fraction).toHaveCSS("color", BAD.light);
    await expect(fraction).toHaveCSS("font-weight", "600");
    await expect(cellEl.locator("span.muted")).toHaveCSS("color", MUTED.light);
  });

  test("a clean group stays quiet", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={[cell({ session_id: "c-1" }), cell({ session_id: "c-2" })]} />);
    const cellEl = td(page, OPUS, "pass");
    await expect(cellEl).toHaveText("2/2 · 100.0%");
    await expect(cellEl.locator(".bad")).toHaveCount(0);
    await expect(cellEl.locator("span").first()).not.toHaveCSS("font-weight", "600");
  });

  test("an ungraded run is never a failure: it is counted beside the rate", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={[cell({ session_id: "u-1" }), cell({ session_id: "u-2", verdict: null })]} />);
    const cellEl = td(page, OPUS, "pass");
    await expect(cellEl).toHaveText("1/1 · 100.0% · 1 no history");
    await expect(cellEl.locator(".bad")).toHaveCount(0);
  });

  test("an error verdict counts as graded and not passed", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={[cell({ session_id: "e-1" }), cell({ session_id: "e-2", verdict: "error" })]} />);
    await expect(td(page, OPUS, "pass").locator(".bad")).toHaveText("1/2");
  });

  test("sorting by pass rate ranks the share, an ungraded group last in both directions", async ({ mount, page }) => {
    const cells = [
      cell({ session_id: "r-half-1", effort: "low", verdict: "pass" }),
      cell({ session_id: "r-half-2", effort: "low", verdict: "fail" }),
      cell({ session_id: "r-none", effort: "medium", verdict: null }),
      cell({ session_id: "r-all", effort: "high", verdict: "pass" }),
      cell({ session_id: "r-zero", effort: "max", verdict: "fail" }),
    ];
    const c = await mount(<SessionSummaryTable cells={cells} />, { hooksConfig: { search: "?ssort=pass&sdir=desc" } });
    expect(await keys(page)).toEqual([`${OPUS}|high`, `${OPUS}|low`, `${OPUS}|max`, `${OPUS}|medium`]);
    await head(page, "pass").locator("button").click();
    await expect.poll(() => search(page)).toBe("?ssort=pass&sdir=asc");
    await c.update(<SessionSummaryTable cells={cells} />);
    expect(await keys(page)).toEqual([`${OPUS}|max`, `${OPUS}|low`, `${OPUS}|high`, `${OPUS}|medium`]);
  });
});

test.describe("SessionSummaryTable: banding and repeat muting", () => {
  test("in key order, the first row of each new skill opens a band", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />);
    const bands = await rows(page).evaluateAll((trs) => trs.map((tr) => tr.getAttribute("data-band")));
    expect(bands).toEqual([null, "skill", null, null, null, null, null]);
    const banded = row(page, `${OPUS}|low`).locator("td").first();
    await expect(banded).toHaveCSS("box-shadow", /inset/);
    await expect(banded).toHaveCSS("padding-top", "15px");
  });

  test("in key order, a skill repeating the row above's recedes to the muted ink but is still printed", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />);
    const repeats = await rows(page).evaluateAll((trs) => trs.map((tr) => (tr.children[0] as HTMLElement).getAttribute("data-repeat")));
    expect(repeats).toEqual([null, null, "true", "true", "true", "true", "true"]);
    expect(await column(page, "skill")).toEqual(["discovery", ...Array(6).fill("mermaidjs-diagrams")]);
    await expect(td(page, `${OPUS}|high`, "skill")).toHaveCSS("color", MUTED.light);
    await expect(td(page, `${OPUS}|low`, "skill")).not.toHaveCSS("color", MUTED.light);
  });

  test("only the skill column mutes a repeat: case, harness and model always print at full ink", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />);
    await expect(page.locator("#SessionSummaryTable tbody td[data-repeat]")).toHaveCount(5);
    for (const key of ["case", "harness", "model", "effort"]) {
      await expect(td(page, `${OPUS}|high`, key)).not.toHaveAttribute("data-repeat", /.*/);
    }
  });

  test("a sorted table draws neither bands nor muted repeats: 'the row above' is no longer a group", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />, { hooksConfig: { search: "?ssort=skill&sdir=asc" } });
    await expect(page.locator("#SessionSummaryTable tbody tr[data-band]")).toHaveCount(0);
    await expect(page.locator("#SessionSummaryTable tbody td[data-repeat]")).toHaveCount(0);
    await expect(td(page, `${OPUS}|high`, "skill")).not.toHaveCSS("color", MUTED.light);
  });

  test("clicking any head switches banding and muting off", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />);
    await expect(page.locator("#SessionSummaryTable tbody td[data-repeat]")).toHaveCount(5);
    await head(page, "runs").locator("button").click();
    await expect(page.locator("#SessionSummaryTable tbody td[data-repeat]")).toHaveCount(0);
    await expect(page.locator("#SessionSummaryTable tbody tr[data-band]")).toHaveCount(0);
  });

  test("an unknown ssort key is no sort: the fixed order, its bands and nothing marked sorted", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />, { hooksConfig: { search: "?ssort=bogus&sdir=desc" } });
    expect(await keys(page)).toEqual(SWEEP_KEYS);
    await expect(page.locator("#SessionSummaryTable tbody tr[data-band]")).toHaveCount(1);
    await expect(page.locator('#SessionSummaryTable thead th[aria-sort="none"]')).toHaveCount(KEYS.length);
  });

  test("a group with no skill sorts after every skill and prints the muted glyph", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={[cell({ session_id: "ns", skill: null }), cell({ session_id: "s" })]} />);
    expect(await keys(page)).toEqual([OPUS, "|eval_dual_density|claude|claude-opus-5"]);
    await expect(td(page, "|eval_dual_density|claude|claude-opus-5", "skill").locator("span.muted")).toHaveText(NONE);
  });
});

test.describe("SessionSummaryTable: sorting", () => {
  test("a fresh text head opens ascending and a fresh measure descending; a second click flips", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />);
    await expect(head(page, "harness").locator("svg.sort-ico")).toHaveClass(/lucide-arrow-up/);
    await expect(head(page, "cost").locator("svg.sort-ico")).toHaveClass(/lucide-arrow-down/);
    await head(page, "harness").locator("button").click();
    await expect.poll(() => search(page)).toBe("?ssort=harness&sdir=asc");
    await expect(head(page, "harness")).toHaveAttribute("aria-sort", "ascending");
    await head(page, "harness").locator("button").click();
    await expect.poll(() => search(page)).toBe("?ssort=harness&sdir=desc");
    await expect(head(page, "harness")).toHaveAttribute("aria-sort", "descending");
    await head(page, "cost").locator("button").click();
    await expect.poll(() => search(page)).toBe("?ssort=cost&sdir=desc");
    await expect(head(page, "harness")).toHaveAttribute("aria-sort", "none");
  });

  test("sorting by mean cost ranks groups, largest first; ties keep the key order", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />, { hooksConfig: { search: "?ssort=cost&sdir=desc" } });
    // Fixture costs: max 3.1, high 1.2, pre-axis 1.0, luna 1.0276 (default), sol 0.9, sonnet 0.6, low 0.4.
    expect(await keys(page)).toEqual([`${OPUS}|max`, `${OPUS}|high`, SWEEP_KEYS[0], OPUS, SWEEP_KEYS[6], SWEEP_KEYS[5], `${OPUS}|low`]);
    await expect(head(page, "cost")).toHaveAttribute("aria-sort", "descending");
    await expect(head(page, "cost").locator("svg.sort-ico")).toHaveAttribute("data-active", "true");
  });

  test("equal values keep the alphabetical key order under a sort", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />, { hooksConfig: { search: "?ssort=runs&sdir=desc" } });
    expect(await keys(page)).toEqual(SWEEP_KEYS);
  });

  test("peak context ranks by the mean share of the window, not raw tokens", async ({ mount, page }) => {
    await mount(
      <SessionSummaryTable
        cells={[
          cell({ session_id: "w-big", effort: "low", peak_context_tokens: 60_000, context_window_pct: 6 }),
          cell({ session_id: "w-small", effort: "high", peak_context_tokens: 68_000, context_window: 200_000, context_window_pct: 34 }),
        ]}
      />,
      { hooksConfig: { search: "?ssort=peak&sdir=desc" } },
    );
    expect(await keys(page)).toEqual([`${OPUS}|high`, `${OPUS}|low`]);
  });

  test("a sort click writes only the summary's pair, carrying the session sort, facets and theme", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />, { hooksConfig: { search: "?sort=turns&dir=asc&harness=claude&effort=high&theme=dark" } });
    await head(page, "cost").locator("button").click();
    await expect.poll(() => search(page)).toBe("?sort=turns&dir=asc&ssort=cost&sdir=desc&harness=claude&effort=high&theme=dark");
  });

  test("a missing sdir reads as ascending", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />, { hooksConfig: { search: "?ssort=effort" } });
    await expect(head(page, "effort")).toHaveAttribute("aria-sort", "ascending");
  });

  test("the SessionTable's own sort never reorders this table", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />, { hooksConfig: { search: "?sort=estimated_cost_usd&dir=desc" } });
    expect(await keys(page)).toEqual(SWEEP_KEYS);
    await expect(page.locator('#SessionSummaryTable thead th[aria-sort="none"]')).toHaveCount(KEYS.length);
  });

  for (const key of ["Enter", "Space"]) {
    test(`${key} on a focused head sorts it`, async ({ mount, page }) => {
      await mount(<SessionSummaryTable cells={sweep()} />);
      await head(page, "turns").locator("button").focus();
      await page.keyboard.press(key);
      await expect.poll(() => search(page)).toBe("?ssort=turns&sdir=desc");
    });
  }
});

test.describe("SessionSummaryTable: the effort axis (ADR 0049)", () => {
  test("two rungs of one model are two rows, never one averaged row", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />);
    const opus = (await keys(page)).filter((k) => k?.startsWith(OPUS));
    expect(opus).toEqual([`${OPUS}|low`, `${OPUS}|high`, `${OPUS}|max`, OPUS]);
    await expect(td(page, `${OPUS}|max`, "cost")).toHaveText("$3.1000");
    await expect(td(page, `${OPUS}|low`, "cost")).toHaveText("$0.4000");
  });

  test("runs of the same rung roll up into one row", async ({ mount, page }) => {
    await mount(
      <SessionSummaryTable
        cells={[cell({ session_id: "h-1", effort: "high" }), cell({ session_id: "h-2", effort: "high" }), cell({ session_id: "l-1", effort: "low" })]}
      />,
    );
    expect(await keys(page)).toEqual([`${OPUS}|low`, `${OPUS}|high`]);
    await expect(td(page, `${OPUS}|high`, "runs")).toHaveText("2");
    await expect(td(page, `${OPUS}|low`, "runs")).toHaveText("1");
  });

  test("a pre-axis sweep keeps its pre-axis group keys: no effort segment at all", async ({ mount, page }) => {
    await mount(
      <SessionSummaryTable cells={[cell({ session_id: "old-1" }), cell({ session_id: "old-2" }), cell({ session_id: "old-3", model: "claude-sonnet-5" })]} />,
    );
    expect(await keys(page)).toEqual([OPUS, "mermaidjs-diagrams|eval_dual_density|claude|claude-sonnet-5"]);
    await expect(td(page, OPUS, "runs")).toHaveText("2");
  });

  test("a rung-less group shows the muted glyph in the effort column", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />);
    const glyph = td(page, OPUS, "effort").locator("> span");
    await expect(glyph).toHaveClass("muted");
    await expect(glyph).toHaveText(NONE);
    await expect(glyph).toHaveCSS("color", MUTED.light);
    await expect(td(page, `${OPUS}|high`, "effort")).toHaveText("high");
  });

  test("in key order, rungs of one model follow the ladder and the rung-less group comes last", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={["max", null, "xhigh", "low", "high", "medium"].map((effort, i) => cell({ session_id: `k-${i}`, effort }))} />);
    expect(await column(page, "effort")).toEqual(["low", "medium", "high", "xhigh", "max", NONE]);
  });

  test("sorting by effort ascending follows the ladder, a null last", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />, { hooksConfig: { search: "?ssort=effort&sdir=asc" } });
    expect(await column(page, "effort")).toEqual(["low", "low", "medium", "high", "xhigh", "max", NONE]);
    // The two `low` groups tie, and keep the key order: discovery before mermaidjs-diagrams.
    expect((await keys(page)).slice(0, 2)).toEqual([SWEEP_KEYS[0], `${OPUS}|low`]);
  });

  test("sorting by effort descending reverses the ladder, a null still last", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />, { hooksConfig: { search: "?ssort=effort&sdir=desc" } });
    expect(await column(page, "effort")).toEqual(["max", "xhigh", "high", "medium", "low", "low", NONE]);
    expect((await keys(page)).slice(4, 6)).toEqual([SWEEP_KEYS[0], `${OPUS}|low`]);
  });

  test("clicking the effort head sorts by rung position, never alphabetically", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />);
    await head(page, "effort").locator("button").click();
    await expect.poll(() => search(page)).toBe("?ssort=effort&sdir=asc");
    const asc = await column(page, "effort");
    expect(asc).not.toEqual(["high", "low", "low", "max", "medium", "xhigh", NONE]);
    expect(asc).toEqual(["low", "low", "medium", "high", "xhigh", "max", NONE]);
    await head(page, "effort").locator("button").click();
    await expect.poll(() => search(page)).toBe("?ssort=effort&sdir=desc");
    expect(await column(page, "effort")).toEqual(["max", "xhigh", "high", "medium", "low", "low", NONE]);
  });

  test("a rung the page does not know sorts after the ladder and before a null", async ({ mount, page }) => {
    await mount(
      <SessionSummaryTable
        cells={[cell({ session_id: "x-1", effort: null }), cell({ session_id: "x-2", effort: "turbo" }), cell({ session_id: "x-3", effort: "max" })]}
      />,
    );
    expect(await column(page, "effort")).toEqual(["max", "turbo", NONE]);
  });
});

test.describe("SessionSummaryTable: keyboard access to a clipped table", () => {
  test("a table that fits costs no tab stop: the scroll box is not focusable", async ({ mount, page }) => {
    await page.setViewportSize({ width: 1600, height: 900 });
    await mount(
      <div style={{ padding: 20 }}>
        <SessionSummaryTable cells={sweep()} />
      </div>,
    );
    const region = page.getByRole("region", { name: "Summary table, scrollable" });
    await expect(region).toHaveAttribute("data-edge-end", "false");
    await expect(region).toHaveAttribute("tabindex", "-1");
    const { scroll, client } = await region.evaluate((el) => ({ scroll: el.scrollWidth, client: el.clientWidth }));
    expect(scroll).toBeLessThanOrEqual(client + 1);
  });

  test("a clipped table makes its scroll box a tab stop, and the arrow keys scroll it", async ({ mount, page }) => {
    await page.setViewportSize({ width: 640, height: 800 });
    await mount(
      <div style={{ padding: 20 }}>
        <SessionSummaryTable cells={sweep()} />
      </div>,
    );
    const region = page.getByRole("region", { name: "Summary table, scrollable" });
    await expect(region).toHaveAttribute("data-edge-end", "true");
    await expect(region).toHaveAttribute("tabindex", "0");
    await page.keyboard.press("Tab");
    await expect(region).toBeFocused();
    // The ring is drawn on the unmasked wrapper, because the box's own edge mask would clip it.
    await expect(page.locator(".table-scroll-ring")).toHaveCSS("outline-style", "solid");
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("ArrowRight");
    await expect.poll(() => region.evaluate((el) => el.scrollLeft)).toBeGreaterThan(0);
    await expect(region).toHaveAttribute("data-edge-start", "true");
  });

  test("the rows are a readout: no row is focusable and none carries a click affordance", async ({ mount, page }) => {
    await mount(<SessionSummaryTable cells={sweep()} />);
    const focusable = await rows(page).evaluateAll((trs) => trs.filter((tr) => tr.hasAttribute("tabindex")).length);
    expect(focusable).toBe(0);
    await rows(page).first().click();
    expect(await search(page)).toBe("");
  });
});
