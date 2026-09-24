/**
 * `RecordCard`: one session-log line as a card, dispatched on the `harness` prop. Every record
 * kind either dialect writes is mounted here and must classify to its catalogued kind, render
 * through its own `R.<kind>` renderer, carry its `L<line>` anchor and paint its pill from the
 * category token. The rest pins the card's behaviour in a real browser: the nice/raw flip, the
 * permalink, the failure paths (unparseable line, unknown kind, a renderer that throws), dark
 * mode, and a line whose one token is wider than any viewport.
 */
import { expect, test } from "./test";
import type { Page } from "@playwright/test";
import { RecordCard } from "../src/components/records/RecordCard";
import { CATEGORIES, categoryOf } from "../src/lib/records";
import type { HooksConfig } from "../playwright/index";
import {
  ANSI_TEXT,
  UNBROKEN,
  claudeAssistant,
  claudeAttachment,
  claudeToolResult,
  claudeToolUse,
  claudeUser,
  codexCompleted,
  codexEvent,
  codexLine,
  codexResponse,
  codexTokenCount,
  codexTurnContext,
} from "./fixtures";

test.use({ timezoneId: "UTC" });

const rgb = (hex: string): string => {
  const n = parseInt(hex.slice(1), 16);
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
};

/** How far the page scrolls sideways; a card must never make it scroll. */
const pageOverflow = (page: Page): Promise<number> => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

type Row = [kind: string, rec: Record<string, unknown>];

/** Every Claude record kind the catalogue names, as Claude Code writes it. */
const CLAUDE: Row[] = [
  ["claude/user/prompt", claudeUser("draw the architecture")],
  ["claude/user/injected", claudeUser("<system-reminder>\nbe brief</system-reminder>")],
  ["claude/user/tool_result", claudeToolResult("total 0\n-rw-r--r-- README.md")],
  ["claude/assistant/text", claudeAssistant([{ type: "text", text: "Both gates pass clean." }])],
  ["claude/assistant/thinking", claudeAssistant([{ type: "thinking", thinking: "Plan the diagram first.", signature: "c2lnbmF0dXJl" }])],
  ["claude/assistant/tool_use", claudeToolUse("Bash", { command: "ls -la", description: "list" })],
  ["claude/assistant/synthetic", claudeAssistant([{ type: "text", text: "API Error: overloaded" }], "<synthetic>", { error: { type: "overloaded_error" } })],
  ["claude/attachment/total_tokens_reminder", claudeAttachment("total_tokens_reminder", { text: "<budget>12,000 tokens left</budget>" })],
  [
    "claude/attachment/deferred_tools_delta",
    claudeAttachment("deferred_tools_delta", { addedNames: ["WebFetch"], removedNames: ["NotebookEdit"], readdedNames: [] }),
  ],
  [
    "claude/attachment/agent_listing_delta",
    claudeAttachment("agent_listing_delta", { addedTypes: ["Explore"], addedLines: ["- Explore: read-only search agent"] }),
  ],
  ["claude/attachment/skill_listing", claudeAttachment("skill_listing", { content: "- mermaidjs-diagrams: render diagrams\n- gooddocs: audit docs" })],
  ["claude/attachment/auto_mode", claudeAttachment("auto_mode", { enabled: true, reason: "flag" })],
  ["claude/attachment/task_reminder", claudeAttachment("task_reminder", { itemCount: 1, content: [{ id: "1", subject: "draw", status: "pending" }] })],
  ["claude/ai-title", { type: "ai-title", aiTitle: "Draw the architecture", sessionId: "s" }],
  ["claude/atis-latch", { type: "atis-latch", atis: "v1.abc", sessionId: "s" }],
  ["claude/last-prompt", { type: "last-prompt", lastPrompt: "draw the architecture", leafUuid: "leaf-1" }],
  ["claude/queue-operation", { type: "queue-operation", operation: "enqueue", content: "draw it", timestamp: "2026-08-23T07:18:00.000Z" }],
];

/** Every Codex record kind the catalogue names, as codex-cli writes it. */
const CODEX: Row[] = [
  [
    "codex/session_meta",
    codexLine("session_meta", {
      id: "sess-1",
      cwd: "/w",
      cli_version: "0.155.1",
      model_provider: "openai",
      source: "exec",
      base_instructions: { text: "# You are Codex" },
    }),
  ],
  ["codex/turn_context", codexTurnContext("xhigh")],
  ["codex/world_state", codexLine("world_state", { full: true, state: { git_clean: true, branch: "main" } })],
  ["codex/response_item/message/user", codexResponse({ type: "message", role: "user", content: [{ type: "input_text", text: "draw the architecture" }] })],
  [
    "codex/response_item/message/user/injected",
    codexResponse({ type: "message", role: "user", content: [{ type: "input_text", text: "<environment_context>\n<cwd>/w</cwd>\n</environment_context>" }] }),
  ],
  [
    "codex/response_item/message/developer",
    codexResponse({ type: "message", role: "developer", content: [{ type: "input_text", text: "<permissions>read-only</permissions>" }] }),
  ],
  ["codex/response_item/message/system", codexResponse({ type: "message", role: "system", content: [{ type: "input_text", text: "be careful" }] })],
  [
    "codex/response_item/message/assistant",
    codexResponse({ type: "message", role: "assistant", id: "msg_9", phase: "final", content: [{ type: "output_text", text: "Done." }] }),
  ],
  [
    "codex/response_item/reasoning",
    codexResponse({ type: "reasoning", summary: [{ type: "summary_text", text: "Checking the tree." }], encrypted_content: "gAAAA" }),
  ],
  [
    "codex/response_item/custom_tool_call",
    codexResponse({
      type: "custom_tool_call",
      name: "exec",
      call_id: "call_1",
      status: "completed",
      input: 'tools.exec_command({ cmd: "bun run check", workdir: "/w" })',
    }),
  ],
  [
    "codex/response_item/function_call",
    codexResponse({ type: "function_call", name: "shell", call_id: "call_2", arguments: JSON.stringify({ command: ["ls", "-la"] }) }),
  ],
  ["codex/response_item/custom_tool_call_output", codexResponse({ type: "custom_tool_call_output", call_id: "call_1", output: "Exit code: 0\nok" })],
  [
    "codex/response_item/function_call_output",
    codexResponse({ type: "function_call_output", call_id: "call_2", output: '{"output":"README.md","metadata":{"exit_code":0}}' }),
  ],
  ["codex/event_msg/task_started", codexEvent({ type: "task_started", turn_id: "turn_1", model_context_window: 258_400, collaboration_mode_kind: "default" })],
  [
    "codex/event_msg/task_complete",
    codexEvent({ type: "task_complete", turn_id: "turn_1", duration_ms: 83_000, time_to_first_token_ms: 1_400, last_agent_message: "Done." }),
  ],
  ["codex/event_msg/token_count", codexTokenCount()],
  ["codex/event_msg/item_completed/AgentMessage", codexCompleted({ item_type: "AgentMessage", id: "i1", content: [{ type: "Text", text: "Done." }] })],
  [
    "codex/event_msg/item_completed/CommandExecution",
    codexCompleted({
      item_type: "CommandExecution",
      command: ["bash", "-lc", "ls"],
      cwd: "/w",
      status: "completed",
      exit_code: 0,
      duration_ms: 42,
      aggregated_output: "README.md",
    }),
  ],
  [
    "codex/event_msg/item_completed/FileChange",
    codexCompleted({ item_type: "FileChange", changes: { "ARCHITECTURE.md": { type: "add", unified_diff: "@@ -0,0 +1 @@\n+# Architecture" } } }),
  ],
  ["codex/event_msg/item_completed/Reasoning", codexCompleted({ item_type: "Reasoning", summary_text: ["Checking the tree."] })],
  ["codex/event_msg/item_completed/UserMessage", codexCompleted({ item_type: "UserMessage", content: [{ type: "Text", text: "draw it" }] })],
  [
    "codex/event_msg/item_completed/UserMessage/injected",
    codexCompleted({ item_type: "UserMessage", content: [{ type: "Text", text: "<environment_context>x</environment_context>" }] }),
  ],
];

for (const [harness, rows] of [
  ["claude", CLAUDE],
  ["codex", CODEX],
] as const) {
  for (const [i, [kind, rec]] of rows.entries()) {
    test(`${kind} classifies, renders through R.${kind}, and anchors at L${i + 1}`, async ({ mount }) => {
      const lineNo = i + 1;
      const raw = JSON.stringify(rec);
      const c = await mount(<RecordCard harness={harness} lineNo={lineNo} raw={raw} view="nice" />);
      await expect(c.locator(`#L${lineNo}`)).toHaveAttribute("data-kind", kind);
      await expect(c.locator(`#L${lineNo}`)).toHaveAttribute("data-harness", harness);
      await expect(c.locator(".rec-head .line")).toHaveText(`L${lineNo}`);
      await expect(c.locator(`[data-el="R.${kind}"]`)).toHaveCount(1);
      await expect(c.locator('[data-el="R.fallback"]')).toHaveCount(0);
      await expect(c.getByText("renderer failed")).toHaveCount(0);
      const category = categoryOf(kind);
      const pill = c.locator(".pill");
      await expect(pill).toHaveText(kind);
      await expect(pill).toHaveAttribute("title", `${kind} · ${category}`);
      await expect(pill).toHaveCSS("background-color", rgb(CATEGORIES[category]!));
      await expect(c.locator(".rec-head .chars")).toHaveText(`${raw.length.toLocaleString("en-US")} chars`);
      // Every nice body ends in the collapsible envelope.
      await expect(c.locator('[data-el="V.envelope"]')).toHaveCount(1);
    });
  }
}

test("the timestamp reads as HH:MM:SS.mmm, and a record without one shows a dash", async ({ mount }) => {
  const c = await mount(<RecordCard harness="claude" lineNo={1} raw={JSON.stringify(claudeUser("go"))} view="nice" />);
  await expect(c.locator(".rec-head .clock")).toHaveText("07:18:05.537");
  await c.update(<RecordCard harness="claude" lineNo={1} raw={JSON.stringify({ type: "ai-title", aiTitle: "x" })} view="nice" />);
  await expect(c.locator(".rec-head .clock")).toHaveText("–");
});

test("the pill is painted from --xh-category-*, so a project palette moves it", async ({ mount, page }) => {
  const c = await mount(<RecordCard harness="claude" lineNo={2} raw={JSON.stringify(claudeToolUse("Bash", { command: "ls" }))} view="nice" />);
  const pill = c.locator(".pill");
  await expect(pill).toHaveCSS("background-color", rgb(CATEGORIES.tool_call!));
  await expect(pill).toHaveCSS("color", "rgb(255, 255, 255)");
  await page.evaluate(() => document.documentElement.style.setProperty("--xh-category-tool_call", "#123456"));
  await expect(pill).toHaveCSS("background-color", "rgb(18, 52, 86)");
  // The tool_use block's left rule draws from the same token.
  await expect(c.locator(".block.tool_use")).toHaveCSS("border-left-color", "rgb(18, 52, 86)");
});

test("the context annotation shows its text with its title", async ({ mount }) => {
  const c = await mount(
    <RecordCard
      harness="claude"
      lineNo={3}
      raw={JSON.stringify(claudeToolUse("Bash", { command: "ls" }))}
      ctx={{ text: "ctx 3.6%", title: "turn 1 processed 35,599" }}
      view="nice"
    />,
  );
  await expect(c.locator(".rec-head .ctx")).toHaveText("ctx 3.6%");
  await expect(c.locator(".rec-head .ctx")).toHaveAttribute("title", "turn 1 processed 35,599");
});

test("the card's flip swaps nice for highlighted raw JSON, and a page-wide view change resets it", async ({ mount }) => {
  const raw = JSON.stringify(claudeToolResult("total 0"));
  const c = await mount(<RecordCard harness="claude" lineNo={4} raw={raw} view="nice" />);
  await expect(c.locator(".rec-nice")).toBeVisible();
  const flip = c.getByRole("button", { name: "raw" });
  await expect(flip).toHaveAttribute("data-mode", "nice");
  await flip.click();
  await expect(c.locator(".rec-nice")).toHaveCount(0);
  const json = c.locator('.rec-raw [data-el="V.json"]');
  await expect(json).toContainText('"tool_use_id": "toolu_01"');
  await expect(json.locator("code.hljs.language-json .hljs-attr").first()).toBeVisible();
  await expect(c.getByRole("button", { name: "nice" })).toHaveAttribute("data-mode", "raw");

  // Same view prop: the card keeps its own flip.
  await c.update(<RecordCard harness="claude" lineNo={4} raw={raw} view="nice" />);
  await expect(c.locator(".rec-raw")).toBeVisible();
  // The page-wide view moves to raw and back: every card follows it.
  await c.update(<RecordCard harness="claude" lineNo={4} raw={raw} view="raw" />);
  await expect(c.locator(".rec-raw")).toBeVisible();
  await c.update(<RecordCard harness="claude" lineNo={4} raw={raw} view="nice" />);
  await expect(c.locator(".rec-nice")).toBeVisible();
});

test("view=raw mounts straight into the raw body", async ({ mount }) => {
  const c = await mount(<RecordCard harness="codex" lineNo={5} raw={JSON.stringify(codexTokenCount())} view="raw" />);
  await expect(c.locator(".rec-raw")).toContainText('"token_count"');
  await expect(c.locator(".rec-nice")).toHaveCount(0);
});

test("the permalink button writes the line= deeplink into the address bar", async ({ mount, page }) => {
  const c = await mount(<RecordCard harness="claude" lineNo={12} raw={JSON.stringify(claudeUser("go"))} view="nice" permalink="?session=abc&line=12" />);
  await c.getByRole("button", { name: "link to log line 12" }).click();
  await expect.poll(() => new URL(page.url()).search).toBe("?session=abc&line=12");
});

test("no permalink prop, no permalink button", async ({ mount }) => {
  const c = await mount(<RecordCard harness="claude" lineNo={12} raw={JSON.stringify(claudeUser("go"))} view="nice" />);
  await expect(c.getByRole("button", { name: /link to log line/ })).toHaveCount(0);
});

test("an unparseable line is shown as it was written, under an unknown-coloured pill", async ({ mount }) => {
  const c = await mount(<RecordCard harness="claude" lineNo={6} raw="{not json" view="nice" />);
  await expect(c.locator("#L6")).toHaveAttribute("data-kind", "claude/unparseable");
  await expect(c.locator(".pill")).toHaveCSS("background-color", rgb(CATEGORIES.unknown!));
  await expect(c.locator(".rec-nice")).toContainText("{not json");
  await c.getByRole("button", { name: "raw" }).click();
  await expect(c.locator(".rec-raw")).toContainText("{not json");
});

test("a JSON line that is not an object (an array) is unparseable, not dropped", async ({ mount }) => {
  const c = await mount(<RecordCard harness="codex" lineNo={7} raw="[1,2,3]" view="nice" />);
  await expect(c.locator("#L7")).toHaveAttribute("data-kind", "codex/unparseable");
  await expect(c.locator(".rec-nice")).toContainText("[1,2,3]");
});

test("an unknown record kind degrades visibly: R.fallback JSON with its label always shown", async ({ mount }) => {
  const rec = { type: "mystery", payload: { secret: 42 } };
  const c = await mount(<RecordCard harness="codex" lineNo={8} raw={JSON.stringify(rec)} view="nice" />);
  await expect(c.locator("#L8")).toHaveAttribute("data-kind", "codex/mystery");
  await expect(c.locator(".pill")).toHaveCSS("background-color", rgb(CATEGORIES.unknown!));
  const fallback = c.locator('[data-el="R.fallback"]');
  await expect(fallback.locator('[data-el="V.json"]')).toContainText('"secret": 42');
  // The fallback's name is on view without a hover: an unrendered kind is announced, not hidden.
  await expect(fallback.locator(":scope > .comp-label")).toHaveText("R.fallback");
  await expect(fallback.locator(":scope > .comp-label")).toHaveCSS("opacity", "1");
});

test("claude/system has a category but no renderer: it falls back to JSON rather than vanishing", async ({ mount }) => {
  const rec = { type: "system", subtype: "compact_boundary", content: "Conversation compacted", level: "info" };
  const c = await mount(<RecordCard harness="claude" lineNo={9} raw={JSON.stringify(rec)} view="nice" />);
  await expect(c.locator("#L9")).toHaveAttribute("data-kind", "claude/system");
  await expect(c.locator(".pill")).toHaveCSS("background-color", rgb(CATEGORIES.harness_meta!));
  await expect(c.locator('[data-el="R.fallback"]')).toContainText("Conversation compacted");
});

test("a renderer that throws shows the failure and the raw line, and the card survives", async ({ mount }) => {
  // MultiEdit's renderer maps over `edits`; a string there throws inside the renderer.
  const raw = JSON.stringify(claudeToolUse("MultiEdit", { file_path: "a.py", edits: "not a list" }));
  const c = await mount(<RecordCard harness="claude" lineNo={10} raw={raw} view="nice" />);
  await expect(c.locator("#L10")).toBeVisible();
  await expect(c.locator(".rec-nice .warn")).toContainText("renderer failed:");
  await expect(c.locator(".rec-nice")).toContainText('"edits":"not a list"');
  await c.getByRole("button", { name: "raw" }).click();
  await expect(c.locator(".rec-raw")).toContainText('"not a list"');
});

test("ANSI colour codes in a tool result render as colour, not escape noise", async ({ mount }) => {
  const c = await mount(<RecordCard harness="claude" lineNo={11} raw={JSON.stringify(claudeToolResult(ANSI_TEXT))} view="nice" />);
  const ansi = c.locator('[data-el="B.tool_result"] [data-el="V.ansi"]');
  await expect(ansi).toContainText("FAILED tests/test_x.py::test_y");
  await expect(ansi).not.toContainText("[31m");
  await expect(ansi.locator("span", { hasText: "FAILED" })).toHaveCSS("color", "rgb(187, 0, 0)");
  await expect(ansi.locator("span", { hasText: "PASSED" })).toHaveCSS("color", "rgb(0, 187, 0)");
});

test("the record envelope collapses the bookkeeping fields, including the Claude effort rung", async ({ mount }) => {
  const c = await mount(<RecordCard harness="claude" lineNo={13} raw={JSON.stringify(claudeToolUse("Read", { file_path: "SKILL.md" }))} view="nice" />);
  const env = c.locator('[data-el="V.envelope"]');
  await expect(env.locator('[data-el="V.kvs"]')).toBeHidden();
  await env.getByText("record envelope").click();
  const kvs = env.locator('[data-el="V.kvs"]');
  await expect(kvs).toBeVisible();
  await expect(kvs).toContainText("requestIdreq_011");
  await expect(kvs).toContainText("efforthigh");
});

// ADR 0049: the effort rung reaches every place the report names an arm. Regression: the Codex
// turn_context card once named the model in its grid but left the rung it ran at in the
// collapsed "all turn context" JSON only.
test("codex/turn_context names the effort rung beside the model", async ({ mount }) => {
  const c = await mount(<RecordCard harness="codex" lineNo={2} raw={JSON.stringify(codexTurnContext("xhigh"))} view="nice" />);
  const grid = c.locator('[data-el="R.codex/turn_context"] > [data-el="V.kvs"]');
  await expect(grid.locator("b")).toHaveText(["model", "effort", "cwd", "approval", "sandbox", "network", "personality", "timezone", "date"]);
  await expect(grid).toContainText("modelgpt-5.6-sol");
  await expect(grid).toContainText("effortxhigh");
});

test("a Claude assistant card names the effort rung beside the model", async ({ mount }) => {
  const c = await mount(<RecordCard harness="claude" lineNo={3} raw={JSON.stringify(claudeToolUse("Read", { file_path: "SKILL.md" }))} view="nice" />);
  const grid = c.locator('[data-el="claudeMessage"] > [data-el="V.kvs"]');
  await expect(grid.locator("b")).toHaveText(["model", "effort", "stop", "message id"]);
  await expect(grid).toContainText("efforthigh");
});

test.describe("dark mode", () => {
  test("the card sits on the dark panel and code uses the dark highlight palette", async ({ mount }) => {
    const c = await mount<HooksConfig>(
      <RecordCard harness="claude" lineNo={14} raw={JSON.stringify(claudeToolUse("Bash", { command: 'echo "hi"' }))} view="nice" />,
      {
        hooksConfig: { mode: "dark" },
      },
    );
    await expect(c.locator("#L14")).toHaveCSS("background-color", "rgb(23, 26, 35)");
    await expect(c.locator(".pill")).toHaveCSS("background-color", rgb(CATEGORIES.tool_call!));
    await expect(c.locator(".pill")).toHaveCSS("color", "rgb(255, 255, 255)");
    await expect(c.locator('[data-el="V.bash"] .hljs-string').first()).toHaveCSS("color", "rgb(126, 231, 135)");
  });
});

test.describe("a token wider than the viewport never scrolls the page sideways", () => {
  const cases: [string, "claude" | "codex", Record<string, unknown>][] = [
    ["assistant text", "claude", claudeAssistant([{ type: "text", text: UNBROKEN }])],
    ["a Bash command", "claude", claudeToolUse("Bash", { command: UNBROKEN })],
    ["a Read path in a key/value grid", "claude", claudeToolUse("Read", { file_path: `/${UNBROKEN}` })],
    ["a tool result", "claude", claudeToolResult(UNBROKEN)],
    ["a Codex cwd", "codex", codexLine("turn_context", { model: "gpt-5.6-sol", cwd: `/${UNBROKEN}` })],
    ["an unknown kind's JSON", "codex", { type: "mystery", blob: UNBROKEN }],
  ];
  for (const [what, harness, rec] of cases) {
    test(what, async ({ mount, page }) => {
      const c = await mount(<RecordCard harness={harness} lineNo={1} raw={JSON.stringify(rec)} view="nice" />);
      await expect(c.locator("#L1")).toBeVisible();
      expect(await pageOverflow(page)).toBeLessThanOrEqual(0);
      await c.getByRole("button", { name: "raw" }).click();
      await expect(c.locator(".rec-raw")).toBeVisible();
      expect(await pageOverflow(page)).toBeLessThanOrEqual(0);
    });
  }
});
