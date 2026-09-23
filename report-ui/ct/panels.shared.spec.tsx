/**
 * The panels' shared pieces (`shared.tsx`): the category-coloured kind `Pill`, the `Chip`
 * (display span, or a toggle button when it has an `onClick`), the `KvTable` and the `Notice`.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import { Chip, KvTable, Notice, Pill } from "../src/components/panels/shared";
import { PHONE, pageOverflowX, resolveColour } from "./panels.data";

test.describe("Pill", () => {
  test("names its kind, titles its category and paints that category's token", async ({ mount, page }) => {
    const c = await mount(<Pill kind="claude/assistant/thinking" />);
    const pill = c.locator(".pill");
    await expect(pill).toHaveText("claude/assistant/thinking");
    await expect(pill).toHaveAttribute("title", "thinking");
    expect(await pill.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe(await resolveColour(page, "#6d28d9"));
    expect(await pill.evaluate((el) => getComputedStyle(el).whiteSpace)).toBe("nowrap");
  });

  test("an unmapped kind is the `unknown` category, never uncoloured", async ({ mount, page }) => {
    const c = await mount(<Pill kind="gemini/whatever" />);
    const pill = c.locator(".pill");
    await expect(pill).toHaveAttribute("title", "unknown");
    expect(await pill.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe(await resolveColour(page, "#374151"));
  });
});

test.describe("Chip", () => {
  test("without onClick it is a display span with a bold label", async ({ mount }) => {
    const c = await mount(
      <Chip label="files">
        <span>5</span>
      </Chip>,
    );
    const chip = c.locator(".filter-chip");
    expect(await chip.evaluate((el) => el.tagName)).toBe("SPAN");
    await expect(chip.locator("b")).toHaveText("files");
    await expect(chip).toHaveText("files5");
  });

  test("with onClick it is a button, reports each press, and shows `on`", async ({ mount }) => {
    let pressed = 0;
    const c = await mount(
      <Chip label="run" on onClick={() => (pressed += 1)}>
        1
      </Chip>,
    );
    const chip = c.locator("button.filter-chip");
    await expect(chip).toHaveAttribute("type", "button");
    await expect(chip).toHaveAttribute("data-on", "true");
    await chip.click();
    await chip.focus();
    await c.page().keyboard.press("Enter");
    await expect.poll(() => pressed).toBe(2);
  });

  test("an off button carries no data-on at all", async ({ mount }) => {
    const c = await mount(<Chip label="run" onClick={() => {}} />);
    const chip = c.locator("button.filter-chip");
    await expect(chip).not.toHaveAttribute("data-on", /.*/);
    await expect(chip).toHaveText("run");
  });

  test("without a label only the children render", async ({ mount }) => {
    const c = await mount(<Chip>just a count</Chip>);
    const chip = c.locator(".filter-chip");
    await expect(chip.locator("b")).toHaveCount(0);
    await expect(chip).toHaveText("just a count");
  });
});

/** The widest rows the panels put in a KvTable: ReconciliationPanel's four columns. */
const WIDE_ROWS: [string, string, string, string][] = [
  ["estimated / harness reported cost", "$1.0276", "$1.0288", "Δ $0.0011"],
  ["accumulative_billed_tokens", "1,504,090", "1,504,090", ""],
];

test.describe("KvTable", () => {
  test("the first cell is the key, every further cell a right-aligned value", async ({ mount }) => {
    const c = await mount(
      <KvTable
        id="Kv"
        rows={[
          ["alpha", "1", "2"],
          ["beta", <b key="b">3</b>],
        ]}
      />,
    );
    const table = c.locator("#Kv");
    await expect(table.locator("tr")).toHaveCount(2);
    await expect(table.locator("tr").nth(0).locator("td")).toHaveText(["alpha", "1", "2"]);
    await expect(table.locator("tr").nth(0).locator("td").first()).toHaveClass(/key/);
    for (const td of await table.locator("td.num").all()) {
      await expect(td).toHaveCSS("text-align", "right");
      await expect(td).toHaveCSS("vertical-align", "top");
    }
    await expect(table.locator("tr").nth(1).locator("b")).toHaveText("3");
  });

  test("no rows is an empty table, not an error", async ({ mount }) => {
    const c = await mount(<KvTable id="Kv" rows={[]} />);
    await expect(c.locator("#Kv tr")).toHaveCount(0);
  });

  test("a clipped KvTable at phone width is reachable from the keyboard", async ({ mount, page }) => {
    // BUG: shared.tsx:42 — KvTable renders `<Table>` without `scrollLabel`, and a KvTable's rows
    // are text only. ui/table.tsx:47-52 requires `scrollLabel` of "any table whose rows hold
    // nothing focusable", or the columns past the clipped right edge are pointer-only (WCAG
    // 2.1.1). Expected: when the box clips, it is a tab stop. Actual: no tabindex. Affects
    // CostByTierPanel, RatesApplied and ReconciliationPanel.
    // The precondition (the box really clips) is pinned by the passing test below.
    test.fail();
    await page.setViewportSize(PHONE);
    const c = await mount(<KvTable id="Kv" rows={WIDE_ROWS} />);
    await expect(c.locator("#Kv").locator("xpath=..")).toHaveAttribute("tabindex", "0", { timeout: 1000 });
  });

  test("at phone width a reconciliation-shaped KvTable clips inside its box, never the page", async ({ mount, page }) => {
    await page.setViewportSize(PHONE);
    const c = await mount(<KvTable id="Kv" rows={WIDE_ROWS} />);
    const box = c.locator("#Kv").locator("xpath=..");
    await expect(box).toHaveClass(/table-scroll/);
    expect(await pageOverflowX(page)).toBeLessThanOrEqual(0);
    expect(await box.evaluate((el) => el.scrollWidth - el.clientWidth > 1)).toBe(true);
    await expect(c.locator("#Kv").locator("button, a[href], input, [tabindex]")).toHaveCount(0);
  });
});

test.describe("Notice", () => {
  for (const mode of ["light", "dark"] as const) {
    test(`${mode}: warn-coloured text`, async ({ mount, page }) => {
      const c = await mount(<Notice>replay the cache</Notice>, { hooksConfig: { mode } });
      const n = c.locator(".warn");
      await expect(n).toHaveText("replay the cache");
      expect(await n.evaluate((el) => getComputedStyle(el).color)).toBe(await resolveColour(page, "var(--xh-warn)"));
      expect(await n.evaluate((el) => getComputedStyle(el).color)).toBe(mode === "dark" ? "rgb(251, 191, 36)" : await resolveColour(page, "var(--xh-warn)"));
    });
  }
});
