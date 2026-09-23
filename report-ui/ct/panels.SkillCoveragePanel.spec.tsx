/**
 * SkillCoveragePanel: the skill's catalogued files, the turns that loaded or ran each, the
 * status word (and its colour) per file state, the summary chips that filter the table, and
 * the `ShowIgnored` switch that reveals the files the ignore rules removed (ADR 0022, 0023).
 */
import { expect, test } from "@playwright/experimental-ct-react";
import type { Locator } from "@playwright/test";
import { SkillCoveragePanel, type SkillCoverage } from "../src/components/panels/SkillCoveragePanel";
import { coverage, PHONE, pageOverflowX, resolveColour } from "./panels.data";

const summary = (c: Locator) => c.locator("#SkillCoverageSummary");
const chip = (c: Locator, label: string) =>
  summary(c)
    .locator(".filter-chip")
    .filter({ has: c.page().locator("b", { hasText: new RegExp(`^${label}$`) }) });
const bodyRows = (c: Locator) => c.locator("#SkillCoveragePanel tbody tr");
const rowOf = (c: Locator, path: string) => bodyRows(c).filter({ has: c.page().locator("code", { hasText: new RegExp(`^${path.replace(/\./g, "\\.")}$`) }) });
const paths = async (c: Locator) => (await bodyRows(c).locator("td:first-child").allTextContents()).map((t) => t.trim());
const colour = (l: Locator) => l.evaluate((el) => getComputedStyle(el).color);
const toggleIgnored = (c: Locator) => c.locator("#ShowIgnored");

const VISIBLE = ["SKILL.md", "resources/contrast_tooling.md", "scripts/mermaid_contrast.ts", "scripts/render_mermaid.sh", "scripts/x.test.ts"];

test.describe("summary chips", () => {
  test("every count, in order, with the skill name first", async ({ mount }) => {
    const c = await mount(<SkillCoveragePanel coverage={coverage()} />);
    await expect(summary(c).locator(".filter-chip")).toHaveText([
      "skillmermaidjs-diagrams",
      "files5",
      "docs2",
      "scripts2",
      "tests1",
      "assets0",
      "loaded2 / 5",
      "run1 / 2 scripts",
      "not_loaded3",
      "not_run1",
      "ignored1",
    ]);
  });

  test("only the six filtering chips are buttons, and `files` (all) starts on", async ({ mount }) => {
    const c = await mount(<SkillCoveragePanel coverage={coverage()} />);
    await expect(summary(c).locator("button.filter-chip b")).toHaveText(["files", "loaded", "run", "not_loaded", "not_run", "ignored"]);
    await expect(summary(c).locator("span.filter-chip b")).toHaveText(["skill", "docs", "scripts", "tests", "assets"]);
    await expect(chip(c, "files")).toHaveAttribute("data-on", "true");
    for (const l of ["loaded", "run", "not_loaded", "not_run", "ignored"]) await expect(chip(c, l)).not.toHaveAttribute("data-on", /.*/);
  });

  test("the loaded / run / not_* counts are coloured by state", async ({ mount, page }) => {
    const c = await mount(<SkillCoveragePanel coverage={coverage()} />);
    expect(await colour(chip(c, "loaded").locator(".good"))).toBe(await resolveColour(page, "var(--xh-good)"));
    expect(await colour(chip(c, "run").locator(".accentc"))).toBe(await resolveColour(page, "var(--xh-accent)"));
    expect(await colour(chip(c, "not_loaded").locator(".bad"))).toBe(await resolveColour(page, "var(--xh-bad)"));
    expect(await colour(chip(c, "not_run").locator(".bad"))).toBe(await resolveColour(page, "var(--xh-bad)"));
  });

  test("a summary missing its counts prints the no-value glyph rather than 0", async ({ mount }) => {
    const c = await mount(<SkillCoveragePanel coverage={{ ...coverage(), summary: undefined, not_loaded: undefined, not_run: undefined }} />);
    await expect(chip(c, "files")).toHaveText("files–");
    await expect(chip(c, "loaded")).toHaveText("loaded– / –");
    // not_loaded / not_run count lists, and a missing list is an empty one
    await expect(chip(c, "not_loaded")).toHaveText("not_loaded0");
    await expect(chip(c, "not_run")).toHaveText("not_run0");
  });
});

test.describe("the file table", () => {
  test("headers, and ignored files hidden by default", async ({ mount }) => {
    const c = await mount(<SkillCoveragePanel coverage={coverage()} />);
    await expect(c.locator("#SkillCoveragePanel thead th")).toHaveText(["path", "kind", "bytes", "loaded at turns", "run at turns", "status"]);
    expect(await paths(c)).toEqual(VISIBLE);
    await expect(c.getByText("README.md")).toHaveCount(0);
  });

  test("every field of a row: path, kind, bytes, loaded and run turns", async ({ mount }) => {
    const c = await mount(<SkillCoveragePanel coverage={coverage()} />);
    const r = rowOf(c, "scripts/mermaid_contrast.ts");
    const tds = r.locator("td");
    await expect(tds.nth(0).locator("code")).toHaveText("scripts/mermaid_contrast.ts");
    await expect(tds.nth(1)).toHaveText("script");
    await expect(tds.nth(2)).toHaveText("12,000");
    await expect(tds.nth(2)).toHaveCSS("text-align", "right");
    await expect(tds.nth(3).locator("code.code-chip")).toHaveText(["t3"]);
    await expect(tds.nth(4).locator("code.code-chip")).toHaveText(["t7", "t9"]);
    // an untouched file has empty turn cells, not a placeholder
    await expect(rowOf(c, "scripts/render_mermaid.sh").locator("td").nth(3)).toHaveText("");
    await expect(rowOf(c, "scripts/render_mermaid.sh").locator("td").nth(4)).toHaveText("");
  });

  const STATES: [string, string, string, string][] = [
    // path, status word, class, colour token
    ["SKILL.md", "loaded", "good", "--xh-good"],
    ["scripts/mermaid_contrast.ts", "run", "accentc", "--xh-accent"],
    ["resources/contrast_tooling.md", "not loaded", "bad", "--xh-bad"],
    ["scripts/render_mermaid.sh", "not run · not loaded", "bad", "--xh-bad"],
    ["scripts/x.test.ts", "test (not expected)", "muted", "--xh-muted"],
  ];
  for (const mode of ["light", "dark"] as const) {
    for (const [path, word, cls, token] of STATES) {
      test(`${mode}: ${path} reads "${word}" in ${token}`, async ({ mount, page }) => {
        const c = await mount(<SkillCoveragePanel coverage={coverage()} />, { hooksConfig: { mode } });
        const status = rowOf(c, path).locator("td").nth(5).locator("span");
        await expect(status).toHaveText(word);
        await expect(status).toHaveClass(cls);
        expect(await colour(status)).toBe(await resolveColour(page, `var(${token})`));
      });
    }
  }

  test("a file both loaded and run reads `run`: running outranks loading", async ({ mount }) => {
    const c = await mount(<SkillCoveragePanel coverage={coverage()} />);
    await expect(rowOf(c, "scripts/mermaid_contrast.ts").locator("td").nth(5)).toHaveText("run");
  });

  test("an asset never touched reads `not loaded`; only a test is `not expected`", async ({ mount }) => {
    const cov: SkillCoverage = { ...coverage(), files: [{ path: "assets/logo.svg", kind: "asset", bytes: 2048, ignored: false, loaded: [], run: [] }] };
    const c = await mount(<SkillCoveragePanel coverage={cov} />);
    await expect(rowOf(c, "assets/logo.svg").locator("td").nth(5).locator(".bad")).toHaveText("not loaded");
  });
});

test.describe("ShowIgnored", () => {
  test("reveals the ignored file, muted, with the `ignored` status; switching off hides it again", async ({ mount, page }) => {
    const c = await mount(<SkillCoveragePanel coverage={coverage()} />);
    await expect(toggleIgnored(c)).toHaveAttribute("aria-checked", "false");
    await toggleIgnored(c).click();
    await expect(toggleIgnored(c)).toHaveAttribute("aria-checked", "true");
    await expect(bodyRows(c)).toHaveCount(6);
    const readme = rowOf(c, "README.md");
    await expect(readme).toHaveClass(/muted/);
    await expect(readme.locator("td").nth(5)).toHaveText("ignored");
    expect(await colour(readme.locator("td").nth(5).locator("span"))).toBe(await resolveColour(page, "var(--xh-muted)"));
    await toggleIgnored(c).click();
    await expect(bodyRows(c)).toHaveCount(5);
  });

  test("the switch has an accessible name and toggles from the keyboard", async ({ mount, page }) => {
    const c = await mount(<SkillCoveragePanel coverage={coverage()} />);
    const sw = c.getByRole("switch", { name: "show ignored files" });
    await sw.focus();
    await expect(sw).toBeFocused();
    await page.keyboard.press("Space");
    await expect(sw).toHaveAttribute("aria-checked", "true");
    await expect(bodyRows(c)).toHaveCount(6);
  });

  test("the label text toggles the switch too", async ({ mount }) => {
    const c = await mount(<SkillCoveragePanel coverage={coverage()} />);
    await c.getByText("show ignored files").click();
    await expect(toggleIgnored(c)).toHaveAttribute("aria-checked", "true");
  });
});

test.describe("chip filters", () => {
  const FILTERED: [string, string[]][] = [
    ["loaded", ["SKILL.md", "scripts/mermaid_contrast.ts"]],
    ["run", ["scripts/mermaid_contrast.ts"]],
    ["not_loaded", ["resources/contrast_tooling.md", "scripts/render_mermaid.sh", "scripts/x.test.ts"]],
    ["not_run", ["scripts/render_mermaid.sh"]],
    ["ignored", ["README.md"]],
  ];
  for (const [f, expected] of FILTERED) {
    test(`${f}: filters the table, lights the chip, and a second press returns to all`, async ({ mount }) => {
      const c = await mount(<SkillCoveragePanel coverage={coverage()} />);
      await chip(c, f).click();
      expect(await paths(c)).toEqual(expected);
      await expect(chip(c, f)).toHaveAttribute("data-on", "true");
      await expect(chip(c, "files")).not.toHaveAttribute("data-on", /.*/);
      await chip(c, f).click();
      expect(await paths(c)).toEqual(VISIBLE);
      await expect(chip(c, "files")).toHaveAttribute("data-on", "true");
    });
  }

  test("the chip counts agree with the rows each chip filters to", async ({ mount }) => {
    const c = await mount(<SkillCoveragePanel coverage={coverage()} />);
    for (const [f, n] of [
      ["not_loaded", 3],
      ["not_run", 1],
      ["ignored", 1],
    ] as const) {
      await chip(c, f).click();
      await expect(bodyRows(c)).toHaveCount(n);
      await expect(chip(c, f)).toContainText(String(n));
    }
  });

  test("`files` returns to all from any filter, and pressing it while on stays on all", async ({ mount }) => {
    const c = await mount(<SkillCoveragePanel coverage={coverage()} />);
    await chip(c, "files").click();
    expect(await paths(c)).toEqual(VISIBLE);
    await chip(c, "run").click();
    await chip(c, "files").click();
    expect(await paths(c)).toEqual(VISIBLE);
    await expect(chip(c, "files")).toHaveAttribute("data-on", "true");
  });

  test("an ignored file stays out of every state filter, even with ShowIgnored on", async ({ mount }) => {
    const cov: SkillCoverage = {
      ...coverage(),
      files: [...(coverage().files ?? []), { path: "scripts/ignored_but_run.sh", kind: "script", bytes: 10, ignored: true, loaded: [2], run: [2] }],
    };
    const c = await mount(<SkillCoveragePanel coverage={cov} />);
    await toggleIgnored(c).click();
    await chip(c, "run").click();
    expect(await paths(c)).toEqual(["scripts/mermaid_contrast.ts"]);
    await chip(c, "ignored").click();
    expect(await paths(c)).toEqual(["README.md", "scripts/ignored_but_run.sh"]);
  });

  test("the ignored filter shows ignored files without ShowIgnored", async ({ mount }) => {
    const c = await mount(<SkillCoveragePanel coverage={coverage()} />);
    await chip(c, "ignored").click();
    await expect(toggleIgnored(c)).toHaveAttribute("aria-checked", "false");
    expect(await paths(c)).toEqual(["README.md"]);
  });

  test("filter chips are tab stops and press with Enter", async ({ mount, page }) => {
    const c = await mount(<SkillCoveragePanel coverage={coverage()} />);
    await chip(c, "not_run").focus();
    await expect(chip(c, "not_run")).toBeFocused();
    await page.keyboard.press("Enter");
    expect(await paths(c)).toEqual(["scripts/render_mermaid.sh"]);
    await page.keyboard.press("Space");
    expect(await paths(c)).toEqual(VISIBLE);
  });
});

test.describe("no catalogue", () => {
  for (const [name, cov] of [
    ["empty", {}],
    ["null", null],
    ["no files", { skill: "x", files: [], summary: { files: 0 } }],
  ] as const) {
    test(`${name}: a notice pointing at the replay, and an empty table`, async ({ mount }) => {
      const c = await mount(<SkillCoveragePanel coverage={cov as SkillCoverage | null} />);
      const notice = summary(c).locator(".warn");
      await expect(notice).toHaveText("no skill coverage on this result (predates ADR 0022); re-run or replay the cell");
      await expect(summary(c).locator(".filter-chip")).toHaveCount(0);
      await expect(bodyRows(c)).toHaveCount(0);
    });
  }
});

const longCoverage = (): SkillCoverage => ({
  ...coverage(),
  files: [
    ...(coverage().files ?? []),
    {
      path: "resources/a/deeply/nested/directory/structure/that/keeps/going/and/going/with_a_very_long_file_name_that_never_breaks.md",
      kind: "doc",
      bytes: 1_234_567,
      ignored: false,
      loaded: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
      run: [],
    },
  ],
});

const scrollBox = (c: Locator) => c.locator("#SkillCoveragePanel").locator("xpath=..");
const clips = (box: Locator) => box.evaluate((el) => el.scrollWidth - el.clientWidth > 1);

test.describe("layout", () => {
  test("at phone width a long path scrolls inside the table box, never the page", async ({ mount, page }) => {
    await page.setViewportSize(PHONE);
    const c = await mount(<SkillCoveragePanel coverage={longCoverage()} />);
    await expect(bodyRows(c)).toHaveCount(6);
    expect(await pageOverflowX(page)).toBeLessThanOrEqual(0);
    await expect(scrollBox(c)).toHaveClass(/table-scroll/);
  });

  test("the summary chips wrap at phone width", async ({ mount, page }) => {
    await page.setViewportSize(PHONE);
    const c = await mount(<SkillCoveragePanel coverage={coverage()} />);
    const tops = await summary(c)
      .locator(".filter-chip")
      .evaluateAll((els) => new Set(els.map((e) => Math.round(e.getBoundingClientRect().top))).size);
    expect(tops).toBeGreaterThan(1);
    expect(await pageOverflowX(page)).toBeLessThanOrEqual(0);
  });

  // Regression: the file table had no `scrollLabel` and its rows hold nothing focusable, so at
  // phone width the columns past the clipped edge were pointer-only (WCAG 2.1.1).
  test("a clipped table is a named tab stop", async ({ mount, page }) => {
    await page.setViewportSize(PHONE);
    const c = await mount(<SkillCoveragePanel coverage={longCoverage()} />);
    await expect(bodyRows(c)).toHaveCount(6);
    await expect(scrollBox(c)).toHaveAttribute("tabindex", "0");
    await expect(scrollBox(c)).toHaveAttribute("role", "region");
    await expect(scrollBox(c)).toHaveAttribute("aria-label", "skill files");
  });

  test("at phone width the table box does clip (the precondition of the keyboard test above)", async ({ mount, page }) => {
    await page.setViewportSize(PHONE);
    const c = await mount(<SkillCoveragePanel coverage={longCoverage()} />);
    await expect(bodyRows(c)).toHaveCount(6);
    expect(await clips(scrollBox(c))).toBe(true);
    // and no row holds anything focusable that could scroll it instead
    await expect(bodyRows(c).locator("button, a[href], input, [tabindex]")).toHaveCount(0);
  });
});
