/**
 * `ReportHeader`: the report's title on the sweep, and the eval · session · harness · model
 * [· effort] tuple inside a SessionView. The rung rides the tuple only when the cell named one
 * (ADR 0049); the meta line summarises the index; the theme toggle is a callback.
 */
import { expect, test } from "./test";
import type { Page } from "@playwright/test";
import type { HooksConfig } from "../playwright/index";
import { ReportHeader } from "../src/components/ReportHeader";
import { cell, index, sweep } from "./fixtures";

const search = (page: Page) => page.evaluate(() => location.search);
const noop = () => {};

test.describe("on the sweep (no cell)", () => {
  test("titles the report and summarises the index", async ({ mount, page }) => {
    await mount(<ReportHeader index={index()} cell={undefined} mode="light" onToggleMode={noop} />);
    const header = page.locator("header#ReportHeader");
    await expect(header).toBeVisible();
    await expect(page.locator("h1#ReportTitle")).toContainText("xharness eval report");
    await expect(page.locator('#ReportTitle .el[data-el="ReportTitle"]')).toHaveText("ReportTitle");
    await expect(page.locator("#ReportTitleEffort")).toHaveCount(0);
    const meta = page.locator("#ReportMeta");
    // 3.1 + 0.4 + 1.2 + 1.0 + 0.6 + 0.9 + 1.0276 (the default cell's cost)
    await expect(meta).toHaveText(/^7 session\(s\) · 2 skills: discovery, mermaidjs-diagrams · estimated \$8\.2276 · generated .+ · inline$/);
  });

  test("a single skill is named in the singular", async ({ mount, page }) => {
    await mount(<ReportHeader index={index(sweep().filter((c) => c.skill === "mermaidjs-diagrams"))} cell={undefined} mode="light" onToggleMode={noop} />);
    await expect(page.locator("#ReportMeta")).toContainText("6 session(s) · skill: mermaidjs-diagrams · estimated");
  });

  test("null skills are left out of the skill list, and no skills means no clause", async ({ mount, page }) => {
    const cells = sweep().map((c) => ({ ...c, skill: null }));
    await mount(<ReportHeader index={index(cells)} cell={undefined} mode="light" onToggleMode={noop} />);
    await expect(page.locator("#ReportMeta")).toHaveText(/^7 session\(s\) · estimated/);
    await expect(page.locator("#ReportMeta")).not.toContainText("skill");
  });

  test("skills are listed sorted and deduplicated", async ({ mount, page }) => {
    const cells = [cell({ skill: "zeta" }), cell({ skill: "alpha" }), cell({ skill: "zeta" }), cell({ skill: null })];
    await mount(<ReportHeader index={index(cells)} cell={undefined} mode="light" onToggleMode={noop} />);
    await expect(page.locator("#ReportMeta")).toContainText("2 skills: alpha, zeta ·");
  });

  test("null costs count as zero in the estimated total", async ({ mount, page }) => {
    const cells = [cell({ estimated_cost_usd: null }), cell({ estimated_cost_usd: 0.5 })];
    await mount(<ReportHeader index={index(cells)} cell={undefined} mode="light" onToggleMode={noop} />);
    await expect(page.locator("#ReportMeta")).toContainText("estimated $0.5000");
  });

  test("a non-inline index does not say inline", async ({ mount, page }) => {
    await mount(<ReportHeader index={{ ...index(), inline: false }} cell={undefined} mode="light" onToggleMode={noop} />);
    await expect(page.locator("#ReportMeta")).not.toContainText("inline");
  });

  test("an empty index", async ({ mount, page }) => {
    await mount(<ReportHeader index={index([])} cell={undefined} mode="light" onToggleMode={noop} />);
    await expect(page.locator("#ReportMeta")).toContainText("0 session(s) · estimated $0.0000");
  });

  test("before the index loads it says loading", async ({ mount, page }) => {
    await mount(<ReportHeader index={null} cell={undefined} mode="light" onToggleMode={noop} />);
    await expect(page.locator("#ReportMeta")).toHaveText("loading…");
    await expect(page.locator("#ReportTitle")).toContainText("xharness eval report");
  });

  test("is sticky at the top of the page", async ({ mount, page }) => {
    await mount(<ReportHeader index={index()} cell={undefined} mode="light" onToggleMode={noop} />);
    await expect(page.locator("#ReportHeader")).toHaveCSS("position", "sticky");
    await expect(page.locator("#ReportHeader")).toHaveCSS("top", "0px");
  });
});

test.describe("inside a session (the tuple)", () => {
  test("names eval · session · harness · model · rung when the cell has a rung", async ({ mount, page }) => {
    const c = cell({ session_id: "aaaaaaaa-0003", effort: "high" });
    await mount(<ReportHeader index={index()} cell={c} mode="light" onToggleMode={noop} />);
    const title = page.locator("#ReportTitle");
    await expect(title).toHaveText(/^xharness›eval_dual_density·aaaaaaaa·claude·claude-opus-5·highReportTitle$/);
    const effort = page.locator("#ReportTitleEffort");
    await expect(effort).toHaveText("high");
    await expect(effort).toHaveAttribute("title", "effort: the reasoning rung the CLI was sent");
    await expect(effort).toHaveCSS("font-family", /mono/i);
  });

  for (const rung of ["low", "medium", "xhigh", "max", "some-future-rung"]) {
    test(`prints the rung verbatim: ${rung}`, async ({ mount, page }) => {
      await mount(<ReportHeader index={index()} cell={cell({ effort: rung })} mode="light" onToggleMode={noop} />);
      await expect(page.locator("#ReportTitleEffort")).toHaveText(rung);
    });
  }

  test("omits the rung, and its separator, when the cell named none", async ({ mount, page }) => {
    await mount(<ReportHeader index={index()} cell={cell({ effort: null })} mode="light" onToggleMode={noop} />);
    await expect(page.locator("#ReportTitleEffort")).toHaveCount(0);
    const title = page.locator("#ReportTitle");
    await expect(title).toHaveText(/^xharness›eval_dual_density·1feb573f·claude·claude-opus-5ReportTitle$/);
    expect(((await title.textContent()) ?? "").split("·").length - 1).toBe(3);
  });

  test("an empty-string rung is treated as no rung", async ({ mount, page }) => {
    await mount(<ReportHeader index={index()} cell={cell({ effort: "" })} mode="light" onToggleMode={noop} />);
    await expect(page.locator("#ReportTitleEffort")).toHaveCount(0);
  });

  test("the session id is shortened to eight characters", async ({ mount, page }) => {
    await mount(<ReportHeader index={index()} cell={cell()} mode="light" onToggleMode={noop} />);
    await expect(page.locator("#ReportTitle")).toContainText("1feb573f");
    await expect(page.locator("#ReportTitle")).not.toContainText("1feb573f-ba51");
  });

  test("the home link is the short brand and navigates to the overview", async ({ mount, page }) => {
    await mount<HooksConfig>(<ReportHeader index={index()} cell={cell()} mode="light" onToggleMode={noop} />, {
      hooksConfig: { search: `?session=${cell().session_id}&turn=2` },
    });
    const home = page.locator("#ReportTitle a");
    await expect(home).toHaveText("xharness");
    await expect(home).toHaveAttribute("href", "?");
    await home.click();
    await expect.poll(() => search(page)).toBe("");
    // a real history entry (push): Back returns to the session
    await page.evaluate(() => history.back());
    await expect.poll(() => search(page)).toBe(`?session=${cell().session_id}&turn=2`);
  });

  test("the meta line still summarises the whole sweep", async ({ mount, page }) => {
    await mount(<ReportHeader index={index()} cell={cell({ effort: "max" })} mode="light" onToggleMode={noop} />);
    await expect(page.locator("#ReportMeta")).toContainText("7 session(s)");
  });
});

test.describe("theme toggle", () => {
  test("calls onToggleMode on click, and is labelled", async ({ mount, page }) => {
    let calls = 0;
    await mount(<ReportHeader index={index()} cell={undefined} mode="light" onToggleMode={() => (calls += 1)} />);
    const toggle = page.locator("#ThemeToggle");
    await expect(toggle).toHaveAttribute("aria-label", "toggle light / dark");
    await expect(toggle).toHaveAttribute("title", "toggle light / dark");
    await toggle.click();
    await toggle.click();
    await expect.poll(() => calls).toBe(2);
  });

  test("is reachable and operable from the keyboard", async ({ mount, page }) => {
    let calls = 0;
    await mount(<ReportHeader index={index()} cell={undefined} mode="light" onToggleMode={() => (calls += 1)} />);
    await page.locator("#ThemeToggle").focus();
    await page.keyboard.press("Enter");
    await expect.poll(() => calls).toBe(1);
  });

  test("shows a moon in light mode and a sun in dark mode", async ({ mount, page }) => {
    const c = await mount(<ReportHeader index={index()} cell={undefined} mode="light" onToggleMode={noop} />);
    await expect(page.locator("#ThemeToggle svg.lucide-moon")).toHaveCount(1);
    await expect(page.locator("#ThemeToggle svg.lucide-sun")).toHaveCount(0);
    await c.update(<ReportHeader index={index()} cell={undefined} mode="dark" onToggleMode={noop} />);
    await expect(page.locator("#ThemeToggle svg.lucide-sun")).toHaveCount(1);
    await expect(page.locator("#ThemeToggle svg.lucide-moon")).toHaveCount(0);
  });
});

test.describe("dark mode", () => {
  test("paints the header on the dark panel", async ({ mount, page }) => {
    await mount<HooksConfig>(<ReportHeader index={index()} cell={cell({ effort: "high" })} mode="dark" onToggleMode={noop} />, {
      hooksConfig: { mode: "dark" },
    });
    await expect(page.locator("#ReportHeader")).toHaveCSS("background-color", "rgb(23, 26, 35)");
    await expect(page.locator("#ReportTitleEffort")).toHaveText("high");
  });

  test("light mode paints the white panel", async ({ mount, page }) => {
    await mount(<ReportHeader index={index()} cell={undefined} mode="light" onToggleMode={noop} />);
    await expect(page.locator("#ReportHeader")).toHaveCSS("background-color", "rgb(255, 255, 255)");
  });
});
