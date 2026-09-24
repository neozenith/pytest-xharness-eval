/**
 * `Table` and its parts (src/components/ui/table.tsx): real table markup inside a `.table-scroll`
 * box that measures which edges clip (`data-edge-start` / `data-edge-end`, faded by a mask), and,
 * given `scrollLabel`, becomes a named region whose tab stop is *measured*: tabindex 0 only while
 * columns are clipped. Its focus ring lives on the unmasked `.table-scroll-ring` wrapper.
 */
import { expect, test } from "./test";
import type { Locator } from "@playwright/test";
import { Table, TableBody, TableCaption, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "../src/components/ui/table";
import type { HooksConfig } from "../playwright/index";

const resolved = (el: Locator, token: string) =>
  el.evaluate((_, t) => {
    const probe = document.createElement("span");
    probe.style.color = `var(--xh-${t})`;
    document.body.append(probe);
    const out = getComputedStyle(probe).color;
    probe.remove();
    return out;
  }, token);

/** A readout: `cols` columns, `rows` rows, nothing focusable inside. */
const readout = (p: { width: number; cols?: number; rows?: number; scrollLabel?: string; id?: string; className?: string }) => {
  const cols = Array.from({ length: p.cols ?? 3 }, (_, i) => `column ${i + 1}`);
  const rows = Array.from({ length: p.rows ?? 2 }, (_, r) => r);
  return (
    <div style={{ width: p.width }}>
      <Table id={p.id} scrollLabel={p.scrollLabel} className={p.className}>
        <TableCaption>totals by arm</TableCaption>
        <TableHeader>
          <TableRow>
            {cols.map((c) => (
              <TableHead key={c} className={c === "column 1" ? undefined : "num"}>
                {c}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r}>
              {cols.map((c, i) => (
                <TableCell key={c} className={i === 0 ? "key" : "num"}>
                  {i === 0 ? `row ${r + 1}` : `${(r + 1) * 1000 + i}.00`}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
        <TableFooter>
          <TableRow>
            <TableCell>total</TableCell>
          </TableRow>
        </TableFooter>
      </Table>
    </div>
  );
};

const WIDE = { width: 360, cols: 14 } as const;
const NARROW = { width: 900, cols: 3 } as const;

test("Table renders semantic table markup with data-slot on every part", async ({ page, mount }) => {
  await mount(readout(NARROW));
  const table = page.getByRole("table");
  await expect(table).toHaveAttribute("data-slot", "table");
  await expect(table).toHaveClass(/\bxh-table\b/);
  await expect(page.locator("[data-slot=table-container]")).toHaveClass(/\btable-scroll\b/);
  for (const [slot, tag] of [
    ["table-header", "THEAD"],
    ["table-body", "TBODY"],
    ["table-footer", "TFOOT"],
    ["table-row", "TR"],
    ["table-head", "TH"],
    ["table-cell", "TD"],
    ["table-caption", "CAPTION"],
  ] as const) {
    expect(
      await page
        .locator(`[data-slot=${slot}]`)
        .first()
        .evaluate((n) => n.tagName),
    ).toBe(tag);
  }
  await expect(page.getByRole("columnheader", { name: "column 2" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "row 1" })).toBeVisible();
  await expect(table).toHaveAccessibleName("totals by arm");
});

test("Table merges a caller className after xh-table and forwards table props", async ({ page, mount }) => {
  await mount(readout({ ...NARROW, className: "mine", id: "Readout" }));
  const table = page.getByRole("table");
  await expect(table).toHaveClass("xh-table mine");
  await expect(table).toHaveAttribute("id", "Readout");
});

test("Table without scrollLabel: no region, no declared tab stop, no ring wrapper", async ({ page, mount }) => {
  await mount(readout(WIDE));
  const box = page.locator("[data-slot=table-container]");
  await expect(box).not.toHaveAttribute("role", /.*/);
  await expect(box).not.toHaveAttribute("aria-label", /.*/);
  await expect(box).not.toHaveAttribute("tabindex", /.*/);
  await expect(page.locator(".table-scroll-ring")).toHaveCount(0);
  // No Tab assertion: Chromium makes a scroller with no focusable content keyboard-focusable on
  // its own, which is browser behaviour rather than the component's.
});

test("Table with scrollLabel is a named region inside the ring wrapper", async ({ page, mount }) => {
  await mount(readout({ ...WIDE, scrollLabel: "session summary" }));
  const region = page.getByRole("region", { name: "session summary" });
  await expect(region).toHaveAttribute("data-slot", "table-container");
  expect(await region.evaluate((n) => n.parentElement?.className)).toBe("table-scroll-ring");
});

test("Table scrollLabel: an overflowing box is a tab stop (tabindex 0)", async ({ page, mount }) => {
  await mount(readout({ ...WIDE, scrollLabel: "session summary" }));
  const region = page.getByRole("region", { name: "session summary" });
  await expect(region).toHaveAttribute("tabindex", "0");
  await page.keyboard.press("Tab");
  await expect(region).toBeFocused();
});

test("Table scrollLabel: a box that fits costs no tab stop (tabindex -1)", async ({ page, mount }) => {
  await mount(
    <div>
      {readout({ ...NARROW, scrollLabel: "session summary" })}
      <button type="button">after</button>
    </div>,
  );
  const region = page.getByRole("region", { name: "session summary" });
  await expect(region).toHaveAttribute("tabindex", "-1");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "after" })).toBeFocused();
});

test("Table scrollLabel: the tab stop follows a resize (ResizeObserver re-measures)", async ({ page, mount }) => {
  await mount(readout({ ...WIDE, scrollLabel: "session summary" }));
  const region = page.getByRole("region", { name: "session summary" });
  await expect(region).toHaveAttribute("tabindex", "0");
  await region.evaluate((n) => {
    (n.closest(".table-scroll-ring")!.parentElement as HTMLElement).style.width = "4000px";
  });
  await expect(region).toHaveAttribute("tabindex", "-1");
  await expect(region).toHaveAttribute("data-edge-end", "false");
  await region.evaluate((n) => {
    (n.closest(".table-scroll-ring")!.parentElement as HTMLElement).style.width = "360px";
  });
  await expect(region).toHaveAttribute("tabindex", "0");
  await expect(region).toHaveAttribute("data-edge-end", "true");
});

test("Table edges: a fitting table flags neither edge and is not masked", async ({ page, mount }) => {
  await mount(readout(NARROW));
  const box = page.locator("[data-slot=table-container]");
  await expect(box).toHaveAttribute("data-edge-start", "false");
  await expect(box).toHaveAttribute("data-edge-end", "false");
  expect(await box.evaluate((n) => getComputedStyle(n).getPropertyValue("--xh-fade-end").trim())).toBe("0px");
});

test("Table edges: overflow flags the end, scrolling moves the flag to the start", async ({ page, mount }) => {
  await mount(readout(WIDE));
  const box = page.locator("[data-slot=table-container]");
  await expect(box).toHaveAttribute("data-edge-start", "false");
  await expect(box).toHaveAttribute("data-edge-end", "true");
  expect(await box.evaluate((n) => getComputedStyle(n).getPropertyValue("--xh-fade-end").trim())).toBe("28px");
  expect(await box.evaluate((n) => getComputedStyle(n).maskImage)).toContain("linear-gradient");

  await box.evaluate((n) => n.scrollTo({ left: 100 }));
  await expect(box).toHaveAttribute("data-edge-start", "true");
  await expect(box).toHaveAttribute("data-edge-end", "true");

  await box.evaluate((n) => n.scrollTo({ left: n.scrollWidth }));
  await expect(box).toHaveAttribute("data-edge-start", "true");
  await expect(box).toHaveAttribute("data-edge-end", "false");
  expect(await box.evaluate((n) => getComputedStyle(n).getPropertyValue("--xh-fade-start").trim())).toBe("28px");
});

test("Table scrollLabel: arrow keys scroll the focused box", async ({ page, mount }) => {
  await mount(readout({ ...WIDE, scrollLabel: "session summary" }));
  const region = page.getByRole("region", { name: "session summary" });
  await region.focus();
  for (let i = 0; i < 5; i++) await page.keyboard.press("ArrowRight");
  await expect.poll(() => region.evaluate((n) => n.scrollLeft)).toBeGreaterThan(0);
  await expect(region).toHaveAttribute("data-edge-start", "true");
});

for (const mode of ["light", "dark"] as const) {
  test(`Table scrollLabel: keyboard focus draws the ring on the wrapper, not the masked box (${mode})`, async ({ page, mount }) => {
    await mount(readout({ ...WIDE, scrollLabel: "session summary" }), { hooksConfig: { mode } satisfies HooksConfig });
    const region = page.getByRole("region", { name: "session summary" });
    const ring = page.locator(".table-scroll-ring");
    await expect(ring).toHaveCSS("outline-style", "none");
    await page.keyboard.press("Tab");
    await expect(region).toBeFocused();
    await expect(ring).toHaveCSS("outline-style", "solid");
    await expect(ring).toHaveCSS("outline-width", "2px");
    await expect(ring).toHaveCSS("outline-offset", "2px");
    await expect(ring).toHaveCSS("outline-color", await resolved(ring, "accent"));
  });

  test(`Table head is muted with a --xh-line rule beneath (${mode})`, async ({ page, mount }) => {
    await mount(readout(NARROW), { hooksConfig: { mode } satisfies HooksConfig });
    const th = page.getByRole("columnheader", { name: "column 1" });
    await expect(th).toHaveCSS("color", await resolved(th, "muted"));
    await expect(th).toHaveCSS("border-bottom-color", await resolved(th, "line"));
    await expect(th).toHaveCSS("font-size", "11px");
    await expect(th).toHaveCSS("white-space", "nowrap");
  });
}

test("Table is full-width, collapsed, tabular-numbered, caption below", async ({ page, mount }) => {
  await mount(readout(NARROW));
  const table = page.getByRole("table");
  await expect(table).toHaveCSS("border-collapse", "collapse");
  await expect(table).toHaveCSS("font-variant-numeric", "tabular-nums");
  await expect(table).toHaveCSS("caption-side", "bottom");
  const [tw, bw] = await table.evaluate((n) => [n.getBoundingClientRect().width, n.parentElement!.clientWidth]);
  expect(tw).toBeCloseTo(bw, 0);
});

for (const id of ["SessionTable", "SessionSummaryTable"]) {
  test(`#${id} pins its header while the rows scroll inside a capped box`, async ({ page, mount }) => {
    await mount(readout({ width: 900, cols: 3, rows: 80, id }));
    const box = page.locator("[data-slot=table-container]");
    await expect(box).toHaveCSS("overflow-y", "auto");
    expect(await box.evaluate((n) => n.scrollHeight > n.clientHeight)).toBe(true);
    const th = page.getByRole("columnheader", { name: "column 1" });
    await expect(th).toHaveCSS("position", "sticky");
    await expect(th).toHaveCSS("top", "0px");
    await expect(th).toHaveCSS("background-color", await resolved(th, "panel"));
    const top = (await box.boundingBox())!.y;
    await box.evaluate((n) => n.scrollTo({ top: 600 }));
    await expect.poll(async () => (await th.boundingBox())!.y).toBeCloseTo(top, 0);
    await expect(th).toBeVisible();
  });
}

test("A table without those ids does not pin its header", async ({ page, mount }) => {
  await mount(readout({ ...NARROW, rows: 40 }));
  await expect(page.getByRole("columnheader", { name: "column 1" })).toHaveCSS("position", "static");
});
