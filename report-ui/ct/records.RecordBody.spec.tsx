/**
 * `RecordBody`: the nice body of one parsed record, by kind. Each test mounts one record kind
 * and checks the fields its renderer promises to lift out of the JSON, and that the envelope
 * follows. A kind no renderer claims falls back to its JSON.
 */
import { expect, test } from "@playwright/experimental-ct-react";
import { RecordBody } from "../src/components/records/records";
import {
  claudeAssistant,
  claudeAttachment,
  claudeToolResult,
  claudeUser,
  codexCompleted,
  codexEvent,
  codexLine,
  codexResponse,
  codexTurnContext,
} from "./fixtures";

test("claude/user/injected is marked harness-injected and its XML sections titled", async ({ mount }) => {
  const c = await mount(<RecordBody harness="claude" rec={claudeUser("<system-reminder>\nbe brief\n</system-reminder>")} />);
  await expect(c.getByText("harness-injected; not the prompt under test")).toBeVisible();
  await expect(c.locator('[data-el="V.xmlish"] .bhead .tag')).toHaveText("<system-reminder>");
  await expect(c.locator('[data-el="V.xmlish"]')).toContainText("be brief");
});

test("claude/user/tool_result keeps the harness's toolUseResult collapsed", async ({ mount }) => {
  const c = await mount(<RecordBody harness="claude" rec={claudeToolResult("README.md")} />);
  await expect(c.locator('[data-el="R.claude/user/tool_result"] [data-el="B.tool_result"]')).toContainText("toolu_01");
  const trigger = c.getByText("toolUseResult (harness view of the result)");
  await expect(trigger).toBeVisible();
  await expect(c.getByText('"interrupted": false')).toBeHidden();
  await trigger.click();
  await expect(c.getByText('"interrupted": false')).toBeVisible();
});

test("claude/assistant/thinking shows the thought and the signature size, not the signature", async ({ mount }) => {
  const c = await mount(<RecordBody harness="claude" rec={claudeAssistant([{ type: "thinking", thinking: "Plan first.", signature: "x".repeat(1234) }])} />);
  await expect(c.locator('[data-el="B.thinking"]')).toContainText("Plan first.");
  await expect(c.locator('[data-el="B.thinking"]')).toContainText("signature1,234 chars");
  await expect(c.locator('[data-el="B.thinking"]')).not.toContainText("xxxx");
});

test("claude/assistant/thinking with the text omitted says so", async ({ mount }) => {
  const c = await mount(<RecordBody harness="claude" rec={claudeAssistant([{ type: "thinking", thinking: "", signature: "s" }])} />);
  await expect(c.locator('[data-el="B.thinking"]')).toContainText("(thinking text omitted by the CLI)");
});

test("claude/assistant/synthetic is flagged as not a model call and shows its error", async ({ mount }) => {
  const rec = claudeAssistant([{ type: "text", text: "API Error: overloaded" }], "<synthetic>", { error: { type: "overloaded_error" } });
  const c = await mount(<RecordBody harness="claude" rec={rec} />);
  await expect(c.getByText("harness-generated message, not a model call")).toBeVisible();
  await expect(c).toContainText("API Error: overloaded");
  await expect(c.locator('[data-el="V.json"]').filter({ hasText: "overloaded_error" })).toBeVisible();
});

test("claude/attachment/deferred_tools_delta shows added and removed tools as tinted chips", async ({ mount }) => {
  const c = await mount(
    <RecordBody harness="claude" rec={claudeAttachment("deferred_tools_delta", { addedNames: ["WebFetch", "Monitor"], removedNames: ["NotebookEdit"] })} />,
  );
  await expect(c.locator(".tag.added")).toHaveText(["WebFetch", "Monitor"]);
  await expect(c.locator(".tag.removed")).toHaveText(["NotebookEdit"]);
  await expect(c.locator('[data-el="V.kvs"]')).toContainText("re-added–");
});

test("claude/attachment/skill_listing and agent_listing_delta render as two-column listings", async ({ mount }) => {
  const c = await mount(
    <RecordBody harness="claude" rec={claudeAttachment("skill_listing", { content: "- mermaidjs-diagrams: render diagrams\n- gooddocs: audit docs" })} />,
  );
  await expect(c.locator('[data-el="V.listing"] tr')).toHaveCount(2);
  await expect(c.locator('[data-el="V.listing"] tr').first()).toContainText("mermaidjs-diagramsrender diagrams");
  await c.update(
    <RecordBody harness="claude" rec={claudeAttachment("agent_listing_delta", { addedTypes: ["Explore"], addedLines: ["- Explore: search agent"] })} />,
  );
  await expect(c.locator(".tag")).toHaveText(["Explore"]);
  await expect(c.locator('[data-el="V.listing"]')).toContainText("search agent");
});

test("claude/attachment/auto_mode shows each flag as a check or a cross", async ({ mount }) => {
  const c = await mount(<RecordBody harness="claude" rec={claudeAttachment("auto_mode", { enabled: true, sticky: false, reason: "flag" })} />);
  const kvs = c.locator('[data-el="R.claude/attachment/auto_mode"] [data-el="V.kvs"]');
  await expect(kvs).toContainText("enabled✓ true");
  await expect(kvs).toContainText("sticky✗ false");
  await expect(kvs).toContainText("reasonflag");
  await expect(kvs).not.toContainText("type");
});

test("claude/attachment/task_reminder, ai-title, atis-latch, last-prompt, queue-operation", async ({ mount }) => {
  const c = await mount(<RecordBody harness="claude" rec={claudeAttachment("task_reminder", { itemCount: 2, content: [{ subject: "draw" }] })} />);
  await expect(c).toContainText("items2");
  await expect(c.locator('[data-el="V.json"]')).toContainText('"subject": "draw"');
  await c.update(<RecordBody harness="claude" rec={{ type: "ai-title", aiTitle: "Draw the architecture" }} />);
  await expect(c.locator('[data-el="V.text"] .txt')).toHaveText("Draw the architecture");
  await c.update(<RecordBody harness="claude" rec={{ type: "atis-latch", atis: "" }} />);
  await expect(c).toContainText("atis(empty)");
  await c.update(<RecordBody harness="claude" rec={{ type: "last-prompt", lastPrompt: "draw it", leafUuid: "leaf-9" }} />);
  await expect(c).toContainText("leafUuidleaf-9");
  await c.update(<RecordBody harness="claude" rec={{ type: "queue-operation", operation: "enqueue", content: "next" }} />);
  await expect(c).toContainText("operationenqueue");
  await expect(c).toContainText("next");
});

test("codex/session_meta lifts the session fields and collapses the base instructions as markdown", async ({ mount }) => {
  const rec = codexLine("session_meta", {
    cwd: "/w",
    cli_version: "0.155.1",
    model_provider: "openai",
    context_window: 258_400,
    base_instructions: { text: "# You are Codex\n- be terse" },
  });
  const c = await mount(<RecordBody harness="codex" rec={rec} />);
  const kvs = c.locator('[data-el="R.codex/session_meta"] > [data-el="V.kvs"]');
  await expect(kvs).toContainText("cli0.155.1");
  await expect(kvs).toContainText("context window258,400");
  const trigger = c.getByText("base_instructions (26 chars)");
  await trigger.click();
  await expect(c.locator("code.language-markdown .hljs-section")).toContainText("# You are Codex");
});

test("codex/turn_context lifts model, sandbox and network, and keeps the whole context collapsed", async ({ mount }) => {
  const c = await mount(<RecordBody harness="codex" rec={codexTurnContext("xhigh")} />);
  const kvs = c.locator('[data-el="R.codex/turn_context"] > [data-el="V.kvs"]');
  await expect(kvs).toContainText("modelgpt-5.6-sol");
  await expect(kvs).toContainText("sandboxworkspace-write");
  await expect(kvs).toContainText("network✗ false");
  await expect(kvs).toContainText("approvalnever");
  await expect(kvs).toContainText("effortxhigh");
  await c.getByText("all turn context").click();
  await expect(c.locator('[data-el="R.codex/turn_context"] [data-el="V.json"]')).toContainText('"effort": "xhigh"');
});

test("codex/turn_context takes the rung from collaboration_mode when `effort` is absent, and drops the row when neither names one", async ({ mount }) => {
  const rec = codexTurnContext("medium");
  delete (rec.payload as Record<string, unknown>).effort;
  const c = await mount(<RecordBody harness="codex" rec={rec} />);
  const kvs = c.locator('[data-el="R.codex/turn_context"] > [data-el="V.kvs"]');
  await expect(kvs).toContainText("effortmedium");
  await c.update(<RecordBody harness="codex" rec={codexLine("turn_context", { model: "gpt-5.6-sol", cwd: "/w" })} />);
  await expect(kvs.locator("b")).toHaveText(["model", "cwd"]);
});

test("a Claude assistant record names its rung beside the model; a pre-ADR 0049 line has no effort row", async ({ mount }) => {
  const c = await mount(<RecordBody harness="claude" rec={claudeAssistant([{ type: "text", text: "done" }])} />);
  const grid = c.locator('[data-el="claudeMessage"] > [data-el="V.kvs"]');
  await expect(grid).toContainText("modelclaude-opus-5efforthigh");
  const old = claudeAssistant([{ type: "text", text: "done" }]);
  delete old.effort;
  await c.update(<RecordBody harness="claude" rec={old} />);
  await expect(grid.locator("b")).toHaveText(["model", "stop", "message id"]);
});

test("codex/world_state lists its state, and says so when empty", async ({ mount }) => {
  const c = await mount(<RecordBody harness="codex" rec={codexLine("world_state", { full: true, state: { git_clean: false, branch: "main" } })} />);
  await expect(c).toContainText("full snapshot✓ true");
  await expect(c).toContainText("git_clean✗ false");
  await expect(c).toContainText("branchmain");
  await c.update(<RecordBody harness="codex" rec={codexLine("world_state", { full: false, state: {} })} />);
  await expect(c.getByText("empty state")).toBeVisible();
});

test("codex/response_item/message/assistant shows its text, phase and id", async ({ mount }) => {
  const c = await mount(
    <RecordBody
      harness="codex"
      rec={codexResponse({ type: "message", role: "assistant", id: "msg_9", phase: "final", content: [{ type: "output_text", text: "Done." }] })}
    />,
  );
  await expect(c.locator('[data-el="B.output_text"]')).toHaveText(/Done\./);
  await expect(c).toContainText("phasefinal");
  await expect(c).toContainText("message idmsg_9");
});

test("codex/response_item/reasoning shows the summary, or says the reasoning is encrypted", async ({ mount }) => {
  const c = await mount(
    <RecordBody
      harness="codex"
      rec={codexResponse({ type: "reasoning", summary: [{ type: "summary_text", text: "Checking." }], encrypted_content: "gAAAA" })}
    />,
  );
  await expect(c).toContainText("Checking.");
  await expect(c).toContainText("encrypted5 chars");
  await c.update(<RecordBody harness="codex" rec={codexResponse({ type: "reasoning", summary: [], encrypted_content: "gAAAA" })} />);
  await expect(c).toContainText("(reasoning encrypted; no summary)");
});

test("codex/response_item/function_call parses its JSON arguments; a broken string stays a string", async ({ mount }) => {
  const c = await mount(
    <RecordBody harness="codex" rec={codexResponse({ type: "function_call", name: "shell", call_id: "c2", arguments: '{"command":["ls","-la"]}' })} />,
  );
  await expect(c.locator('[data-el="T.fallback"] [data-el="V.json"]')).toContainText('"command"');
  await expect(c.locator('[data-el="T.fallback"] .hljs-attr').first()).toBeVisible();
  await c.update(<RecordBody harness="codex" rec={codexResponse({ type: "function_call", name: "shell", call_id: "c2", arguments: "{not json" })} />);
  await expect(c.locator('[data-el="T.fallback"] [data-el="V.code"]')).toContainText("{not json");
});

test("codex call outputs sniff JSON output into a highlighted JSON block", async ({ mount }) => {
  const c = await mount(
    <RecordBody
      harness="codex"
      rec={codexResponse({ type: "function_call_output", call_id: "c2", output: '{"output":"README.md","metadata":{"exit_code":0}}' })}
    />,
  );
  await expect(c).toContainText("call_idc2");
  await expect(c.locator('[data-el="V.output"] [data-el="V.json"]')).toContainText('"exit_code": 0');
  await c.update(<RecordBody harness="codex" rec={codexResponse({ type: "custom_tool_call_output", call_id: "c1", output: "Exit code: 0\nok" })} />);
  await expect(c.locator('[data-el="V.output"]')).toContainText("Exit code: 0");
});

test("codex task_started and task_complete show their lifecycle fields", async ({ mount }) => {
  const c = await mount(
    <RecordBody
      harness="codex"
      rec={codexEvent({ type: "task_started", turn_id: "turn_1", model_context_window: 258_400, collaboration_mode_kind: "default" })}
    />,
  );
  await expect(c).toContainText("turn_idturn_1");
  await expect(c).toContainText("modedefault");
  await c.update(
    <RecordBody
      harness="codex"
      rec={codexEvent({ type: "task_complete", duration_ms: 83_000, time_to_first_token_ms: 1_400, last_agent_message: "All done." })}
    />,
  );
  await expect(c).toContainText("time to first token1,400 ms");
  await expect(c).toContainText("All done.");
});

test("codex FileChange shows each file and its diff with +/- highlighting", async ({ mount }) => {
  const rec = codexCompleted({
    item_type: "FileChange",
    changes: { "a.md": { type: "update", unified_diff: "@@ -1 +1 @@\n-old\n+new" }, "b.md": { type: "add", content: "x" } },
  });
  const c = await mount(<RecordBody harness="codex" rec={rec} />);
  await expect(c.locator('[data-el="V.diff"]')).toHaveCount(2);
  await expect(c.locator(".hljs-deletion").first()).toHaveText("-old");
  await expect(c.locator(".hljs-addition").first()).toHaveText("+new");
  // A change without a unified diff shows its JSON instead of nothing.
  await expect(c.locator('[data-el="V.diff"]').nth(1)).toContainText('"content": "x"');
});

test("codex item_completed Reasoning, AgentMessage and UserMessage/injected", async ({ mount }) => {
  const c = await mount(<RecordBody harness="codex" rec={codexCompleted({ item_type: "Reasoning", summary_text: [] })} />);
  await expect(c).toContainText("(no reasoning summary)");
  await c.update(<RecordBody harness="codex" rec={codexCompleted({ item_type: "AgentMessage", id: "i1", content: [{ type: "Text", text: "Done." }] })} />);
  await expect(c.locator('[data-el="codexItem"] [data-el="B.Text"]')).toContainText("Done.");
  await c.update(
    <RecordBody
      harness="codex"
      rec={codexCompleted({ item_type: "UserMessage", content: [{ type: "Text", text: "<environment_context>x</environment_context>" }] })}
    />,
  );
  await expect(c.getByText("harness-injected; not the prompt under test")).toBeVisible();
});

test("a kind with no renderer falls back to its JSON, and the kind can be passed pre-classified", async ({ mount }) => {
  const c = await mount(<RecordBody harness="codex" rec={codexEvent({ type: "exec_command_begin", call_id: "c", command: ["ls"] })} />);
  await expect(c.locator('[data-el="R.fallback"]')).toContainText('"exec_command_begin"');
  await c.update(<RecordBody harness="claude" rec={claudeUser("hi")} kind="claude/ai-title" />);
  // The renderer is chosen by the given kind; with no aiTitle its frame holds no text.
  await expect(c.locator('[data-el="R.claude/ai-title"]')).toHaveCount(1);
  await expect(c.locator('[data-el="R.claude/ai-title"] [data-el="V.text"]')).toHaveCount(0);
  await expect(c.locator('[data-el="V.envelope"]')).toHaveCount(1);
});

test("the envelope carries the Codex turn_id and passthrough create_time", async ({ mount }) => {
  const rec = codexEvent({ type: "task_started", turn_id: "turn_7", internal_chat_message_metadata_passthrough: { create_time: "1756000000" } });
  const c = await mount(<RecordBody harness="codex" rec={rec} />);
  await c.getByText("record envelope").click();
  const env = c.locator('[data-el="V.envelope"] [data-el="V.kvs"]');
  await expect(env).toContainText("turn_idturn_7");
  await expect(env).toContainText("create_time1756000000");
  await expect(env).toContainText("timestamp2026-08-23T07:20:00.000Z");
});

// Finding: a boolean field the record does not carry printed as the word "undefined"
// (`<Flag value={undefined} />` is an element, so the Kvs row survived its own empty check).
test("a Flag field the record does not carry is no row, never the word undefined", async ({ mount }) => {
  const c = await mount(<RecordBody harness="codex" rec={codexLine("turn_context", { model: "gpt-5.6-sol", sandbox_policy: { type: "read-only" } })} />);
  await expect(c.locator('[data-el="R.codex/turn_context"] > [data-el="V.kvs"] b')).toHaveText(["model", "sandbox"]);
  await c.update(<RecordBody harness="codex" rec={codexLine("world_state", { state: { branch: "main" } })} />);
  await expect(c.locator('[data-el="R.codex/world_state"]')).not.toContainText("undefined");
  await expect(c.locator('[data-el="R.codex/world_state"] [data-el="V.kvs"] b')).toHaveText(["branch"]);
});
