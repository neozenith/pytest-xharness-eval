/**
 * `OverviewFilters` (ADR 0042, ADR 0049): the overview's one global filter. It reads the route and
 * writes it back with `replaceRoute`, so every click is asserted against `location.search`, and
 * every route-driven state is mounted through `hooksConfig.search`.
 *
 * The sweep (`fixtures.sweep()`) has 7 cells: skills discovery(1) / mermaidjs-diagrams(6),
 * harnesses claude(5) / codex(2), four models, and rungs low(2) medium high xhigh max plus one
 * rung-less cell.
 */
import { expect, test } from "./test";
import type { Locator, Page } from "@playwright/test";
import type { HooksConfig } from "../playwright/index";
import { OverviewFilters } from "../src/components/OverviewFilters";
import { cell, sweep } from "./fixtures";

const search = (page: Page) => page.evaluate(() => location.search);
const row = (c: Locator, facet: string) => c.locator(`[role="group"][data-facet="${facet}"]`);
const chip = (c: Locator, facet: string, value: string) => c.locator(`button.filter-chip[data-facet="${facet}"][data-value="${value}"]`);
const values = (c: Locator, facet: string) =>
  row(c, facet)
    .locator("button.filter-chip")
    .evaluateAll((els) => els.map((e) => e.getAttribute("data-value")));
const countOf = (c: Locator, facet: string, value: string) => chip(c, facet, value).locator(".muted");

/** Wait until the box stops moving: the mount settles a few px as the theme's styles land. */
const settle = async (page: Page, target: Locator): Promise<void> => {
  let last = "";
  for (let i = 0; i < 40; i++) {
    const now = JSON.stringify(await target.boundingBox());
    if (now === last) return;
    last = now;
    await page.waitForTimeout(100);
  }
  throw new Error("layout never settled");
};

test.describe("rendering", () => {
  test("eyebrow, glossary name, one group per facet in fixed order, unfiltered count", async ({ mount, page }) => {
    const c = await mount(<OverviewFilters cells={sweep()} />);
    // the mount root is a `display: contents` theme wrapper; the card is the component's own box
    await expect(page.locator("#OverviewFilters")).toBeVisible();
    await expect(c.locator("h2")).toContainText("Filters");
    await expect(c.locator('.el[data-el="OverviewFilters"]')).toHaveText("OverviewFilters");
    await expect(c).toContainText("narrows the chart and both tables below");
    const facets = await c.locator('[role="group"]').evaluateAll((els) => els.map((e) => e.getAttribute("data-facet")));
    expect(facets).toEqual(["skill", "harness", "model", "effort"]);
    for (const f of facets) await expect(row(c, f!)).toHaveAttribute("aria-label", `filter by ${f}`);
    await expect(c.locator("#OverviewFilterCount")).toHaveText(/^7 of 7 sessions\s*7 sessions$/);
    await expect(c.getByRole("status")).toHaveAttribute("aria-atomic", "true");
    await expect(c.locator("#OverviewFilterCount > span:not(.sizer)")).toHaveText("7 sessions");
    await expect(c.locator("button.filter-chip[aria-pressed=true]")).toHaveCount(0);
  });

  test("non-effort options are lexicographic, nulls dropped", async ({ mount }) => {
    const c = await mount(<OverviewFilters cells={sweep()} />);
    expect(await values(c, "skill")).toEqual(["discovery", "mermaidjs-diagrams"]);
    expect(await values(c, "harness")).toEqual(["claude", "codex"]);
    expect(await values(c, "model")).toEqual(["claude-opus-5", "claude-sonnet-5", "gpt-5.6-luna", "gpt-5.6-sol"]);
  });

  test("clear button is always rendered but hidden, out of the tab order, when nothing is selected", async ({ mount }) => {
    const c = await mount(<OverviewFilters cells={sweep()} />);
    const clear = c.locator("#OverviewFiltersClear");
    await expect(clear).toHaveCount(1);
    await expect(clear).toHaveAttribute("aria-hidden", "true");
    await expect(clear).toHaveAttribute("tabindex", "-1");
    await expect(clear).toBeHidden();
    await expect(clear).toHaveCSS("pointer-events", "none");
    // hidden, not unmounted: its box is still reserved in the line, at the control tier's 28px
    // and at the very width it has once shown (font metrics vary by platform, so no literal)
    const box = (await clear.boundingBox())!;
    expect(box.width).toBeGreaterThan(0);
    expect(box.height).toBeCloseTo(28, 3);
    await c.locator("button.filter-chip").first().click();
    await expect(clear).toBeVisible();
    expect((await clear.boundingBox())!.width).toBeCloseTo(box.width, 1);
  });

  test("a facet with a single value says so", async ({ mount }) => {
    const c = await mount(<OverviewFilters cells={sweep().filter((x) => x.harness === "claude")} />);
    await expect(row(c, "harness")).toContainText("only value in this sweep");
    await expect(row(c, "skill")).toContainText("only value in this sweep");
    await expect(row(c, "model")).not.toContainText("only value in this sweep");
  });

  test("skill row drops out when every cell's skill is null", async ({ mount }) => {
    const c = await mount(<OverviewFilters cells={sweep().map((x) => ({ ...x, skill: null }))} />);
    await expect(row(c, "skill")).toHaveCount(0);
    await expect(row(c, "harness")).toHaveCount(1);
  });

  test("an empty sweep renders the bar with no rows and a zero count", async ({ mount }) => {
    const c = await mount(<OverviewFilters cells={[]} />);
    await expect(c.locator('[role="group"]')).toHaveCount(0);
    await expect(c.locator("#OverviewFilterCount > span:not(.sizer)")).toHaveText("0 sessions");
  });

  test("dark mode paints a lit chip in the dark accent", async ({ mount }) => {
    const c = await mount<HooksConfig>(<OverviewFilters cells={sweep()} />, { hooksConfig: { mode: "dark", search: "?effort=high" } });
    await expect(chip(c, "effort", "high")).toHaveCSS("color", "rgb(165, 180, 252)");
    await expect(chip(c, "effort", "low")).not.toHaveCSS("color", "rgb(165, 180, 252)");
  });

  test("light mode paints a lit chip in the light accent", async ({ mount }) => {
    const c = await mount<HooksConfig>(<OverviewFilters cells={sweep()} />, { hooksConfig: { search: "?effort=high" } });
    await expect(chip(c, "effort", "high")).toHaveCSS("color", "rgb(79, 70, 229)");
  });
});

test.describe("effort axis (ADR 0049)", () => {
  test("rungs come in ladder order, never alphabetical", async ({ mount }) => {
    const c = await mount(<OverviewFilters cells={sweep()} />);
    expect(await values(c, "effort")).toEqual(["low", "medium", "high", "xhigh", "max"]);
  });

  test("ladder order holds whatever order the cells arrive in", async ({ mount }) => {
    const cells = ["max", "high", "xhigh", "low", "medium"].map((e, i) => cell({ session_id: `s${i}`, effort: e }));
    const c = await mount(<OverviewFilters cells={cells} />);
    expect(await values(c, "effort")).toEqual(["low", "medium", "high", "xhigh", "max"]);
  });

  test("an unknown rung sorts after the ladder, lexically among peers", async ({ mount }) => {
    const cells = ["zeta", "max", "alpha", "low"].map((e, i) => cell({ session_id: `s${i}`, effort: e }));
    const c = await mount(<OverviewFilters cells={cells} />);
    expect(await values(c, "effort")).toEqual(["low", "max", "alpha", "zeta"]);
  });

  test("a null effort is never a chip", async ({ mount }) => {
    const c = await mount(<OverviewFilters cells={sweep()} />);
    await expect(row(c, "effort").locator("button.filter-chip")).toHaveCount(5);
    await expect(row(c, "effort")).not.toContainText("null");
    await expect(chip(c, "effort", "")).toHaveCount(0);
  });

  test("the effort row is absent when no cell named a rung (pre-ADR 0049 sweep)", async ({ mount }) => {
    const c = await mount(<OverviewFilters cells={sweep().map((x) => ({ ...x, effort: null }))} />);
    await expect(row(c, "effort")).toHaveCount(0);
    await expect(row(c, "model")).toHaveCount(1);
  });

  test("unfiltered counts per rung", async ({ mount }) => {
    const c = await mount(<OverviewFilters cells={sweep()} />);
    const expected: Record<string, string> = { low: "2", medium: "1", high: "1", xhigh: "1", max: "1" };
    for (const [v, n] of Object.entries(expected)) await expect(countOf(c, "effort", v)).toHaveText(n);
  });

  test("clicking a rung writes ?effort=… and lights the chip", async ({ mount, page }) => {
    const c = await mount(<OverviewFilters cells={sweep()} />);
    await chip(c, "effort", "high").click();
    await expect.poll(() => search(page)).toBe("?effort=high");
    await expect(chip(c, "effort", "high")).toHaveAttribute("aria-pressed", "true");
    await expect(chip(c, "effort", "high")).toHaveAttribute("data-on", "true");
    await expect(chip(c, "effort", "low")).toHaveAttribute("aria-pressed", "false");
    await expect(c.getByRole("status")).toContainText("1 of 7 sessions");
  });

  test("an effort deeplink selects its rungs and excludes the rung-less cell", async ({ mount }) => {
    const c = await mount<HooksConfig>(<OverviewFilters cells={sweep()} />, { hooksConfig: { search: "?effort=max,low" } });
    await expect(chip(c, "effort", "max")).toHaveAttribute("aria-pressed", "true");
    await expect(chip(c, "effort", "low")).toHaveAttribute("aria-pressed", "true");
    await expect(chip(c, "effort", "high")).toHaveAttribute("aria-pressed", "false");
    // low(2) + max(1); the null-effort cell does not survive a selection
    await expect(c.locator("#OverviewFilterCount .n")).toHaveText("3");
    await expect(c.getByRole("status")).toContainText("3 of 7 sessions");
    // the option list keeps ladder order, not selection order
    expect(await values(c, "effort")).toEqual(["low", "medium", "high", "xhigh", "max"]);
  });

  test("effort cross-filters the other facets' counts", async ({ mount }) => {
    const c = await mount<HooksConfig>(<OverviewFilters cells={sweep()} />, { hooksConfig: { search: "?effort=low" } });
    await expect(countOf(c, "harness", "claude")).toHaveText("1");
    await expect(countOf(c, "harness", "codex")).toHaveText("1");
    await expect(countOf(c, "model", "claude-sonnet-5")).toHaveText("0");
    await expect(chip(c, "model", "claude-sonnet-5")).toHaveAttribute("data-empty", "true");
    await expect(countOf(c, "skill", "discovery")).toHaveText("1");
    // the facet never filters itself
    await expect(countOf(c, "effort", "max")).toHaveText("1");
  });

  test("the other facets cross-filter the effort counts", async ({ mount }) => {
    const c = await mount<HooksConfig>(<OverviewFilters cells={sweep()} />, { hooksConfig: { search: "?harness=codex" } });
    await expect(countOf(c, "effort", "low")).toHaveText("1");
    await expect(countOf(c, "effort", "xhigh")).toHaveText("1");
    for (const v of ["medium", "high", "max"]) {
      await expect(countOf(c, "effort", v)).toHaveText("0");
      await expect(chip(c, "effort", v)).toHaveAttribute("data-empty", "true");
    }
    await expect(countOf(c, "harness", "claude")).toHaveText("5");
    await expect(countOf(c, "harness", "codex")).toHaveText("2");
    await expect(c.getByRole("status")).toContainText("2 of 7 sessions");
  });

  test("a zero-count chip stays clickable and reaches the empty state", async ({ mount, page }) => {
    const c = await mount<HooksConfig>(<OverviewFilters cells={sweep()} />, { hooksConfig: { search: "?harness=codex" } });
    await chip(c, "effort", "max").click();
    await expect.poll(() => search(page)).toBe("?harness=codex&effort=max");
    await expect(c.getByRole("status")).toContainText("0 of 7 sessions");
    await expect(chip(c, "effort", "max")).toHaveCSS("border-top-style", "dashed");
  });

  test("a stale rung in the deeplink is shown selected, count 0, after the ladder", async ({ mount }) => {
    const c = await mount<HooksConfig>(<OverviewFilters cells={sweep()} />, { hooksConfig: { search: "?effort=ultra" } });
    expect(await values(c, "effort")).toEqual(["low", "medium", "high", "xhigh", "max", "ultra"]);
    await expect(chip(c, "effort", "ultra")).toHaveAttribute("aria-pressed", "true");
    await expect(chip(c, "effort", "ultra")).toHaveAttribute("data-empty", "true");
    await expect(countOf(c, "effort", "ultra")).toHaveText("0");
  });
});

test.describe("route writes", () => {
  test("OR within a facet: a second value is appended, not reordered", async ({ mount, page }) => {
    const c = await mount(<OverviewFilters cells={sweep()} />);
    await chip(c, "effort", "high").click();
    await chip(c, "effort", "low").click();
    await expect.poll(() => search(page)).toBe("?effort=high,low");
    await expect(c.getByRole("status")).toContainText("3 of 7 sessions");
  });

  test("AND across facets, emitted in fixed param order", async ({ mount, page }) => {
    const c = await mount(<OverviewFilters cells={sweep()} />);
    await chip(c, "effort", "low").click();
    await chip(c, "harness", "codex").click();
    await chip(c, "skill", "discovery").click();
    await expect.poll(() => search(page)).toBe("?skill=discovery&harness=codex&effort=low");
    await expect(c.getByRole("status")).toContainText("1 of 7 sessions");
  });

  test("toggling the last value off returns the facet to every value", async ({ mount, page }) => {
    const c = await mount<HooksConfig>(<OverviewFilters cells={sweep()} />, { hooksConfig: { search: "?effort=high" } });
    await chip(c, "effort", "high").click();
    await expect.poll(() => search(page)).toBe("");
    await expect(c.locator("#OverviewFilterCount > span:not(.sizer)")).toHaveText("7 sessions");
    await expect(c.locator("#OverviewFiltersClear")).toHaveAttribute("aria-hidden", "true");
  });

  test("removing a value from the middle keeps the rest in place", async ({ mount, page }) => {
    const c = await mount<HooksConfig>(<OverviewFilters cells={sweep()} />, { hooksConfig: { search: "?model=gpt-5.6-sol,claude-opus-5,gpt-5.6-luna" } });
    await chip(c, "model", "claude-opus-5").click();
    await expect.poll(() => search(page)).toBe("?model=gpt-5.6-sol,gpt-5.6-luna");
  });

  test("a filter click carries both sorts and the theme through", async ({ mount, page }) => {
    const c = await mount<HooksConfig>(<OverviewFilters cells={sweep()} />, {
      hooksConfig: { search: "?sort=turns&dir=desc&ssort=cost&sdir=asc&theme=dark" },
    });
    await chip(c, "effort", "low").click();
    await expect.poll(() => search(page)).toBe("?sort=turns&dir=desc&ssort=cost&sdir=asc&effort=low&theme=dark");
  });

  test("uses replace, not push: no history entry per click", async ({ mount, page }) => {
    const c = await mount(<OverviewFilters cells={sweep()} />);
    // a marker entry the clicks must overwrite; Chromium caps history.length at 50, so it is no witness
    await page.evaluate(() => history.pushState(null, "", "?marker=1"));
    await chip(c, "effort", "low").click();
    await chip(c, "harness", "claude").click();
    await expect.poll(() => search(page)).toBe("?harness=claude&effort=low");
    await page.evaluate(() => history.back());
    // with push, Back would land on ?effort=low; with replace it passes the overwritten marker
    await expect.poll(() => search(page)).toBe("");
  });

  test("the option lists never move as you filter", async ({ mount }) => {
    const c = await mount(<OverviewFilters cells={sweep()} />);
    const before = await Promise.all(["skill", "harness", "model", "effort"].map((f) => values(c, f)));
    await chip(c, "harness", "codex").click();
    await chip(c, "effort", "xhigh").click();
    const after = await Promise.all(["skill", "harness", "model", "effort"].map((f) => values(c, f)));
    expect(after).toEqual(before);
  });

  test("a stale skill deeplink is named, not silently filtering", async ({ mount }) => {
    const c = await mount<HooksConfig>(<OverviewFilters cells={sweep()} />, { hooksConfig: { search: "?skill=__gone__" } });
    expect(await values(c, "skill")).toEqual(["discovery", "mermaidjs-diagrams", "__gone__"]);
    await expect(chip(c, "skill", "__gone__")).toHaveAttribute("aria-pressed", "true");
    await expect(chip(c, "skill", "__gone__")).toHaveAttribute("data-empty", "true");
    await expect(c.getByRole("status")).toContainText("0 of 7 sessions");
    await expect(c.locator("#OverviewFiltersClear")).toBeVisible();
  });

  test("a stale value on a single-valued facet suppresses the 'only value' note", async ({ mount }) => {
    const cells = sweep().filter((x) => x.harness === "claude");
    const c = await mount<HooksConfig>(<OverviewFilters cells={cells} />, { hooksConfig: { search: "?harness=gemini" } });
    expect(await values(c, "harness")).toEqual(["claude", "gemini"]);
    await expect(row(c, "harness")).not.toContainText("only value in this sweep");
  });

  test("on a session route no chip is lit, and a click lands on the overview", async ({ mount, page }) => {
    const c = await mount<HooksConfig>(<OverviewFilters cells={sweep()} />, { hooksConfig: { search: "?session=aaaaaaaa-0001&theme=dark" } });
    await expect(c.locator("button.filter-chip[aria-pressed=true]")).toHaveCount(0);
    await expect(c.locator("#OverviewFilterCount > span:not(.sizer)")).toHaveText("7 sessions");
    await chip(c, "effort", "max").click();
    await expect.poll(() => search(page)).toBe("?effort=max&theme=dark");
  });

  test("keyboard: Space and Enter toggle a focused chip", async ({ mount, page }) => {
    const c = await mount(<OverviewFilters cells={sweep()} />);
    await chip(c, "effort", "medium").focus();
    await page.keyboard.press("Space");
    await expect.poll(() => search(page)).toBe("?effort=medium");
    await page.keyboard.press("Enter");
    await expect.poll(() => search(page)).toBe("");
  });
});

test.describe("OverviewFiltersClear", () => {
  test("clears every facet, keeps sort and theme, hides itself", async ({ mount, page }) => {
    const c = await mount<HooksConfig>(<OverviewFilters cells={sweep()} />, {
      hooksConfig: { search: "?sort=turns&dir=asc&harness=codex&effort=low,xhigh&theme=light" },
    });
    const clear = c.locator("#OverviewFiltersClear");
    await expect(clear).toBeVisible();
    await expect(clear).not.toHaveAttribute("aria-hidden", /.*/);
    await expect(clear).toHaveText("clear filters");
    await clear.click();
    await expect.poll(() => search(page)).toBe("?sort=turns&dir=asc&theme=light");
    await expect(clear).toHaveAttribute("aria-hidden", "true");
    await expect(clear).toBeHidden();
    await expect(c.locator("button.filter-chip[aria-pressed=true]")).toHaveCount(0);
  });

  test("moves focus to the first chip instead of dropping it on <body>", async ({ mount, page }) => {
    const c = await mount<HooksConfig>(<OverviewFilters cells={sweep()} />, { hooksConfig: { search: "?effort=high" } });
    await c.locator("#OverviewFiltersClear").focus();
    await page.keyboard.press("Enter");
    await expect.poll(() => search(page)).toBe("");
    const first = chip(c, "skill", "discovery");
    await expect(first).toBeFocused();
    expect(await page.evaluate(() => document.activeElement?.tagName)).toBe("BUTTON");
  });

  test("first chip is the harness row's when the skill row drops out", async ({ mount, page }) => {
    const cells = sweep().map((x) => ({ ...x, skill: null }));
    const c = await mount<HooksConfig>(<OverviewFilters cells={cells} />, { hooksConfig: { search: "?effort=low" } });
    await c.locator("#OverviewFiltersClear").click();
    await expect.poll(() => search(page)).toBe("");
    await expect(chip(c, "harness", "claude")).toBeFocused();
  });

  test("Tab reaches it when a filter is on, and skips it when idle", async ({ mount, page }) => {
    const c = await mount<HooksConfig>(<OverviewFilters cells={sweep()} />, { hooksConfig: { search: "?effort=low" } });
    await c.locator("h2").click();
    await page.keyboard.press("Tab");
    await expect(c.locator("#OverviewFiltersClear")).toBeFocused();
    await page.keyboard.press("Enter");
    // idle now: Tab from the first chip backwards never lands on the hidden clear button
    await page.keyboard.press("Shift+Tab");
    await expect(c.locator("#OverviewFiltersClear")).not.toBeFocused();
  });
});

test.describe("no reflow (the documented four rules)", () => {
  for (const width of [780, 900, 940, 980, 1440]) {
    test(`a chip click changes no height, no row y, and keeps the chip under the pointer at ${width}px`, async ({ mount, page }) => {
      await page.setViewportSize({ width, height: 900 });
      const c = await mount(<OverviewFilters cells={sweep()} />);
      const target = chip(c, "effort", "high");
      const rowsY = async () => Promise.all(["skill", "harness", "model", "effort"].map(async (f) => (await row(c, f).boundingBox())!.y));
      const bar = page.locator("#OverviewFilters");
      await settle(page, bar);
      const bar0 = (await bar.boundingBox())!;
      const rows0 = await rowsY();
      const chip0 = (await target.boundingBox())!;
      await target.click();
      await expect(target).toHaveAttribute("aria-pressed", "true");
      const bar1 = (await bar.boundingBox())!;
      expect(bar1.height).toBe(bar0.height);
      expect(await rowsY()).toEqual(rows0);
      expect(await target.boundingBox()).toEqual(chip0);
      // and back again via the clear button
      await c.locator("#OverviewFiltersClear").click();
      expect((await bar.boundingBox())!.height).toBe(bar0.height);
      expect(await rowsY()).toEqual(rows0);
    });
  }

  test("a chip is the same width lit and unlit (the always-present .chip-dot)", async ({ mount }) => {
    const c = await mount(<OverviewFilters cells={sweep()} />);
    const target = chip(c, "model", "claude-opus-5");
    await expect(target.locator(".chip-dot")).toHaveCSS("opacity", "0");
    const w0 = (await target.boundingBox())!.width;
    await target.click();
    await expect(target.locator(".chip-dot")).toHaveCSS("opacity", "1");
    expect((await target.boundingBox())!.width).toBe(w0);
  });

  test("the count box is as wide unfiltered as filtered (the sizer)", async ({ mount }) => {
    // Regression: the sizer once reserved its figure at the regular weight while the lit figure is
    // 600, so the box grew ~0.4px on the first chip click and everything left of it shifted.
    const c = await mount(<OverviewFilters cells={sweep()} />);
    const count = c.locator("#OverviewFilterCount");
    await expect(count.locator(".sizer")).toHaveText("7 of 7 sessions");
    await expect(count.locator(".sizer")).toHaveAttribute("aria-hidden", "true");
    await expect(count.locator(".sizer")).toHaveCSS("visibility", "hidden");
    const w0 = (await count.boundingBox())!.width;
    await chip(c, "harness", "codex").click();
    expect((await count.boundingBox())!.width).toBe(w0);
  });

  test("a wrapped chip line starts at the chip column, not under the key", async ({ mount, page }) => {
    await page.setViewportSize({ width: 420, height: 900 });
    const c = await mount(<OverviewFilters cells={sweep()} />);
    const chips = row(c, "effort").locator("button.filter-chip");
    const xs = await chips.evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().left)));
    const ys = await chips.evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().top)));
    expect(new Set(ys).size).toBeGreaterThan(1); // it did wrap
    const firstOfEachLine = xs.filter((_, i) => i === 0 || ys[i] !== ys[i - 1]);
    expect(new Set(firstOfEachLine).size).toBe(1);
  });
});
