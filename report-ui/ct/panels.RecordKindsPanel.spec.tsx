/**
 * RecordKindsPanel: every record kind in the session log with its count, the pill coloured by
 * its category's design token (`--xh-category-<category>`, ADR 0022, 0024).
 */
import { expect, test } from "./test";
import type { Locator } from "@playwright/test";
import { RecordKindsPanel } from "../src/components/panels/RecordKindsPanel";
import { PHONE, pageOverflowX, resolveColour, result } from "./panels.data";

const panel = (c: Locator) => c.locator("#RecordKindsPanel");
const pill = (c: Locator, kind: string) => panel(c).locator(".pill", { hasText: new RegExp(`^${kind}$`) });
const bg = (l: Locator) => l.evaluate((el) => getComputedStyle(el).backgroundColor);

/** `categories` in the bundled `assets/report.tokens.json` (the JSON cannot be imported Node-side). */
const BUNDLED: Record<string, string> = {
  prompt: "#1d4ed8",
  assistant_text: "#065f46",
  thinking: "#6d28d9",
  tool_call: "#4338ca",
  tool_result: "#0f766e",
  tool_exec: "#9a3412",
  file_change: "#be185d",
  usage: "#b45309",
  harness_context: "#3f6212",
  harness_meta: "#475569",
  session_meta: "#1e3a8a",
  lifecycle: "#b91c1c",
  unknown: "#374151",
};

/** One kind per category, plus each prefix fallback and an unmapped kind. */
const KIND_TO_CATEGORY: [string, string][] = [
  ["claude/user/prompt", "prompt"],
  ["claude/assistant/text", "assistant_text"],
  ["claude/assistant/thinking", "thinking"],
  ["claude/assistant/tool_use", "tool_call"],
  ["claude/user/tool_result", "tool_result"],
  ["codex/event_msg/item_completed/CommandExecution", "tool_exec"],
  ["codex/event_msg/item_completed/FileChange", "file_change"],
  ["codex/event_msg/token_count", "usage"],
  ["claude/user/injected", "harness_context"],
  ["claude/system", "harness_meta"],
  ["codex/session_meta", "session_meta"],
  ["codex/event_msg/task_started", "lifecycle"],
  // prefix fallbacks for kinds the catalogue has not named
  ["claude/attachment/brand_new", "harness_meta"],
  ["codex/event_msg/item_completed/Novel", "lifecycle"],
  ["codex/event_msg/novel", "lifecycle"],
  ["codex/response_item/message/tool", "harness_context"],
  ["codex/response_item/novel", "harness_meta"],
  ["claude/made-up", "unknown"],
];

test("one chip per kind, in the result's order, each with its formatted count", async ({ mount }) => {
  const c = await mount(<RecordKindsPanel recordKinds={{ "claude/assistant/tool_use": 12_345, "claude/user/tool_result": 22, "claude/made-up": 1 }} />);
  await expect(panel(c).locator(".filter-chip")).toHaveText(["claude/assistant/tool_use 12,345", "claude/user/tool_result 22", "claude/made-up 1"]);
  // display-only chips: nothing to press
  await expect(panel(c).locator("button")).toHaveCount(0);
});

test("the fixture's four kinds render with the categories the jsdom test pins", async ({ mount }) => {
  const c = await mount(<RecordKindsPanel recordKinds={result().record_kinds} />);
  await expect(panel(c).locator(".pill")).toHaveCount(4);
  await expect(pill(c, "claude/assistant/tool_use")).toHaveAttribute("title", "tool_call");
  await expect(pill(c, "codex/event_msg/token_count")).toHaveAttribute("title", "usage");
  await expect(pill(c, "claude/made-up")).toHaveAttribute("title", "unknown");
});

for (const mode of ["light", "dark"] as const) {
  test(`${mode}: every category paints its pill from its own token, in white ink`, async ({ mount, page }) => {
    const kinds = Object.fromEntries(KIND_TO_CATEGORY.map(([k], i) => [k, i + 1]));
    const c = await mount(<RecordKindsPanel recordKinds={kinds} />, { hooksConfig: { mode } });
    const ink = await resolveColour(page, "var(--xh-on-category)");
    expect(ink).toBe("rgb(255, 255, 255)");
    for (const [kind, category] of KIND_TO_CATEGORY) {
      const p = pill(c, kind);
      await expect(p, kind).toHaveAttribute("title", category);
      // the token must be set (or the pill is a white word on nothing), and be the bundled colour
      const declared = await page.evaluate((n) => getComputedStyle(document.documentElement).getPropertyValue(`--xh-category-${n}`).trim(), category);
      expect(declared.toLowerCase(), `--xh-category-${category}`).toBe(BUNDLED[category]);
      expect(await bg(p), kind).toBe(await resolveColour(page, BUNDLED[category]!));
      expect(await p.evaluate((el) => getComputedStyle(el).color), kind).toBe(ink);
    }
  });
}

test("category colours are fixed per category: the same pill in both themes", async ({ mount, page }) => {
  const light = await mount(<RecordKindsPanel recordKinds={{ "claude/assistant/thinking": 1 }} />);
  const lightBg = await bg(pill(light, "claude/assistant/thinking"));
  await light.unmount();
  const dark = await mount(<RecordKindsPanel recordKinds={{ "claude/assistant/thinking": 1 }} />, { hooksConfig: { mode: "dark" } });
  await expect(page.locator("html")).toHaveClass(/dark/);
  expect(await bg(pill(dark, "claude/assistant/thinking"))).toBe(lightBg);
});

for (const [name, kinds] of [
  ["empty", {}],
  ["null", null],
  ["undefined", undefined],
] as const) {
  test(`${name} record_kinds: the predates-ADR-0022 notice, no chips`, async ({ mount, page }) => {
    const c = await mount(<RecordKindsPanel recordKinds={kinds} />);
    const notice = panel(c).locator(".warn");
    await expect(notice).toHaveText("no record_kinds on this result (predates ADR 0022)");
    expect(await notice.evaluate((el) => getComputedStyle(el).color)).toBe(await resolveColour(page, "var(--xh-warn)"));
    await expect(panel(c).locator(".filter-chip")).toHaveCount(0);
  });
}

test("the heading carries the glossary name", async ({ mount }) => {
  const c = await mount(<RecordKindsPanel recordKinds={{ "claude/system": 1 }} />);
  await expect(c.getByText("Record kinds in this session")).toBeVisible();
  await expect(c.locator('.el[data-el="RecordKindsPanel"]')).toHaveText("RecordKindsPanel");
});

test("many chips wrap onto several lines at phone width without pushing the page sideways", async ({ mount, page }) => {
  await page.setViewportSize(PHONE);
  const kinds = Object.fromEntries(KIND_TO_CATEGORY.map(([k], i) => [k, 1000 * (i + 1)]));
  const c = await mount(<RecordKindsPanel recordKinds={kinds} />);
  const rows = await panel(c)
    .locator(".filter-chip")
    .evaluateAll((els) => new Set(els.map((e) => Math.round(e.getBoundingClientRect().top))).size);
  expect(rows).toBeGreaterThan(3);
  expect(await pageOverflowX(page)).toBeLessThanOrEqual(0);
});

// Regression: the kind pill inherited `.pill`'s `white-space: nowrap`, so this real catalogue
// kind pushed the page 24px sideways at 375px. It now wraps after a `/`, whole and unelided.
test("the longest catalogued kind wraps inside the card at phone width, text intact", async ({ mount, page }) => {
  await page.setViewportSize(PHONE);
  const kind = "codex/event_msg/item_completed/UserMessage/injected";
  const c = await mount(<RecordKindsPanel recordKinds={{ [kind]: 1 }} />);
  await expect(pill(c, kind)).toHaveAttribute("title", "harness_context");
  expect(await pageOverflowX(page)).toBeLessThanOrEqual(0);
  const box = await pill(c, kind).boundingBox();
  const card = await c.locator('[data-el="RecordKindsPanel"]:not(.el)').boundingBox();
  expect(box!.x + box!.width).toBeLessThanOrEqual(card!.x + card!.width);
  expect(box!.height).toBeGreaterThan(24); // it wrapped, rather than being clipped or elided
  expect(await pill(c, kind).evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
});

test("a short kind stays on one line at desktop width", async ({ mount }) => {
  const c = await mount(<RecordKindsPanel recordKinds={{ "claude/user/prompt": 3 }} />);
  expect((await pill(c, "claude/user/prompt").boundingBox())!.height).toBeLessThanOrEqual(22);
});
