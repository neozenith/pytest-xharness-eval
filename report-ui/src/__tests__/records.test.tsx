import { fireEvent, screen } from "@testing-library/react";
import { renderT as render } from "./render";
import { RecordCard } from "@/components/records/RecordCard";
import { TurnRawRecords, ctxFor, ranges, turnId } from "@/components/records/TurnRawRecords";
import { RecordViewToggle } from "@/components/records/RecordViewToggle";
import { CATEGORIES, KINDS, NICE, categoryOf, classify, isCallRecord } from "@/lib/records";
import type { Call, RunResult } from "@/lib/types";

// ---- record shapes, as the two harnesses write them ----------------------------------

const claudeUser = (content: unknown) => ({ type: "user", timestamp: "2026-08-23T07:18:05.537Z", uuid: "u1", message: { role: "user", content } });
const claudeAssistant = (content: unknown, model = "claude-sonnet-5") => ({
  type: "assistant",
  timestamp: "2026-08-23T07:18:06.000Z",
  requestId: "req_1",
  message: {
    id: "msg_1",
    model,
    role: "assistant",
    stop_reason: "tool_use",
    content,
    usage: { input_tokens: 2, cache_read_input_tokens: 100, cache_creation_input_tokens: 5, output_tokens: 9 },
  },
});
const toolUse = claudeAssistant([{ type: "tool_use", id: "toolu_1", name: "Bash", input: { command: "ls -la", description: "list" } }]);
const toolResult = claudeUser([{ type: "tool_result", tool_use_id: "toolu_1", content: "total 0\n-rw-r--r-- README.md" }]);
const codexExecCall = {
  type: "response_item",
  timestamp: "2026-08-23T07:20:00.000Z",
  payload: {
    type: "custom_tool_call",
    name: "exec",
    call_id: "call_1",
    status: "completed",
    input: 'tools.exec_command({ cmd: "bun run check", workdir: "/w" })',
  },
};
const codexTokenCount = {
  type: "event_msg",
  payload: { type: "token_count", info: { last_token_usage: { input_tokens: 10, cached_input_tokens: 8, output_tokens: 1 }, model_context_window: 258400 } },
};

// ---- the catalogue -------------------------------------------------------------------

test("classify mirrors records.py for both harnesses", () => {
  expect(classify("claude", claudeUser("do the thing"))).toBe("claude/user/prompt");
  expect(classify("claude", claudeUser("<system-reminder>\nhi</system-reminder>"))).toBe("claude/user/injected");
  expect(classify("claude", toolResult)).toBe("claude/user/tool_result");
  expect(classify("claude", toolUse)).toBe("claude/assistant/tool_use");
  expect(classify("claude", claudeAssistant([{ type: "thinking", thinking: "hmm" }]))).toBe("claude/assistant/thinking");
  expect(classify("claude", claudeAssistant([{ type: "text", text: "done" }]))).toBe("claude/assistant/text");
  expect(classify("claude", claudeAssistant([{ type: "text", text: "API Error" }], "<synthetic>"))).toBe("claude/assistant/synthetic");
  expect(classify("claude", { type: "attachment", attachment: { type: "skill_listing" } })).toBe("claude/attachment/skill_listing");
  expect(classify("claude", { type: "ai-title", aiTitle: "x" })).toBe("claude/ai-title");
  expect(classify("codex", { type: "session_meta", payload: {} })).toBe("codex/session_meta");
  expect(classify("codex", { type: "response_item", payload: { type: "message", role: "user", content: [{ type: "input_text", text: "go" }] } })).toBe(
    "codex/response_item/message/user",
  );
  expect(
    classify("codex", {
      type: "response_item",
      payload: { type: "message", role: "user", content: [{ type: "input_text", text: "<environment_context>x</environment_context>" }] },
    }),
  ).toBe("codex/response_item/message/user/injected");
  expect(classify("codex", codexExecCall)).toBe("codex/response_item/custom_tool_call");
  expect(classify("codex", codexTokenCount)).toBe("codex/event_msg/token_count");
  expect(classify("codex", { type: "event_msg", payload: { type: "item_completed", item: { item_type: "CommandExecution" } } })).toBe(
    "codex/event_msg/item_completed/CommandExecution",
  );
  expect(classify("codex", "not a record")).toBe("codex/unknown");
  expect(classify("claude", null)).toBe("claude/unknown");
});

test("every catalogued kind has a category with a pill colour, and unseen kinds fall back by prefix", () => {
  for (const [kind, category] of Object.entries(KINDS)) {
    expect(categoryOf(kind)).toBe(category);
    expect(CATEGORIES[category]).toMatch(/^#[0-9a-f]{6}$/);
    expect(NICE[category]).toBeTruthy();
  }
  expect(categoryOf("claude/attachment/brand_new")).toBe("harness_meta");
  expect(categoryOf("codex/event_msg/item_completed/Novel")).toBe("lifecycle");
  expect(categoryOf("codex/response_item/message/tool")).toBe("harness_context");
  expect(categoryOf("something/else")).toBe("unknown");
});

test("isCallRecord finds the measurement record of a turn on each harness", () => {
  expect(isCallRecord("claude", toolUse)).toBe(true);
  expect(isCallRecord("claude", claudeAssistant([], "<synthetic>"))).toBe(false);
  expect(isCallRecord("claude", toolResult)).toBe(false);
  expect(isCallRecord("codex", codexTokenCount)).toBe(true);
  expect(isCallRecord("codex", codexExecCall)).toBe(false);
});

// ---- the card -----------------------------------------------------------------------

const chain = (el: HTMLElement, stopAt: HTMLElement): string[] => {
  const out: string[] = [];
  let node: HTMLElement | null = el;
  while (node && node !== stopAt.parentElement) {
    const label = node.dataset.el;
    if (label) out.unshift(label);
    node = node.parentElement;
  }
  return out;
};

test("a RecordCard's HTML reads in the glossary's vocabulary: RecordCard > R.<kind> > claudeMessage > B.tool_use > T.Bash > V.bash", () => {
  const { container } = render(<RecordCard harness="claude" lineNo={12} raw={JSON.stringify(toolUse)} ctx={{ text: "ctx 3.6%", title: "t" }} view="nice" />);
  const card = container.querySelector("#L12") as HTMLElement;
  expect(card.dataset.el).toBe("RecordCard");
  expect(card.dataset.kind).toBe("claude/assistant/tool_use");
  const bash = container.querySelector('[data-el="V.bash"]') as HTMLElement;
  expect(chain(bash, card)).toEqual(["RecordCard", "R.claude/assistant/tool_use", "claudeMessage", "B.tool_use", "T.Bash", "V.bash"]);
  expect(bash.textContent).toContain("ls -la");
  expect(container.querySelector('[data-el="V.usage"]')).not.toBeNull();
  expect(container.querySelector('[data-el="V.envelope"]')).not.toBeNull();
  expect(screen.getByText("L12")).toBeInTheDocument();
  expect(screen.getByText("ctx 3.6%")).toBeInTheDocument();
  // The pill names its category, and its tooltip carries the whole kind — the head elides it on a narrow card.
  expect(screen.getByTitle("claude/assistant/tool_use · tool_call")).toHaveTextContent("claude/assistant/tool_use");
});

test("the raw/nice flip swaps the body, and a page-wide view change resets it", () => {
  const { container, rerender } = render(<RecordCard harness="claude" lineNo={1} raw={JSON.stringify(toolResult)} view="nice" />);
  expect(container.querySelector(".rec-nice")).not.toBeNull();
  expect(container.querySelector(".rec-raw")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "raw" }));
  expect(container.querySelector(".rec-raw")).not.toBeNull();
  expect(container.querySelector(".rec-nice")).toBeNull();
  expect(container.querySelector('.rec-raw [data-el="V.json"]')?.textContent).toContain("toolu_1");
  rerender(<RecordCard harness="claude" lineNo={1} raw={JSON.stringify(toolResult)} view="nice" />);
  expect(container.querySelector(".rec-raw")).not.toBeNull(); // the view did not change, the card keeps its own flip
  rerender(<RecordCard harness="claude" lineNo={1} raw={JSON.stringify(toolResult)} view="raw" />);
  rerender(<RecordCard harness="claude" lineNo={1} raw={JSON.stringify(toolResult)} view="nice" />);
  expect(container.querySelector(".rec-nice")).not.toBeNull();
});

test("a Codex exec_command payload renders its cmd as a bash block with the JavaScript collapsed", () => {
  const { container } = render(<RecordCard harness="codex" lineNo={7} raw={JSON.stringify(codexExecCall)} view="nice" />);
  const bash = container.querySelector('[data-el="T.exec"] [data-el="V.bash"]') as HTMLElement;
  expect(bash.textContent).toContain("bun run check");
  expect(container.querySelector('[data-el="T.exec"] [data-el="V.kvs"]')?.textContent).toContain("/w");
  expect(screen.getByText("full tool input (javascript)")).toBeInTheDocument();
});

test("an unparseable line and an unknown kind are shown, never dropped", () => {
  const { container } = render(<RecordCard harness="claude" lineNo={3} raw="{not json" view="nice" />);
  expect(container.querySelector("#L3")?.getAttribute("data-kind")).toBe("claude/unparseable");
  expect(container.textContent).toContain("{not json");
  const { container: c2 } = render(<RecordCard harness="codex" lineNo={4} raw={JSON.stringify({ type: "mystery", payload: { a: 1 } })} view="nice" />);
  expect(c2.querySelector('[data-el="R.fallback"] [data-el="V.json"]')?.textContent).toContain('"mystery"');
});

// ---- the turn's records ------------------------------------------------------------

const call = (n: number, records: number[], context_tokens: number, context_pct: number | null): Call => ({
  n,
  at: "t",
  usage: {
    input_tokens: 2,
    output_tokens: 1,
    cache_read_tokens: 0,
    cache_write_tokens: 0,
    cache_write_1h_tokens: 0,
    cache_write_5m_tokens: 0,
    reasoning_tokens: 0,
  },
  tools: [],
  text: "",
  thinking: "",
  stop_reason: "tool_use",
  latency_ms: null,
  context_tokens,
  context_pct,
  output_tokens_per_sec: null,
  records,
  results_in: [],
});

const result = {
  harness: "claude",
  session_id: "1feb573f-ba51",
  context_window: 1_000_000,
  calls: [call(1, [1, 2], 35_599, 3.56), call(2, [3, 4, 5], 35_867, 3.59)],
} as unknown as RunResult;

test("ranges and turnId match the legacy helpers", () => {
  expect(ranges([3, 4, 5, 9, 11, 12])).toBe("3-5, 9, 11-12");
  expect(ranges([])).toBe("");
  expect(turnId("abc", 4)).toBe("abc/t4");
});

test("ctxFor annotates a call with its own context and a tool result with the next turn's", () => {
  expect(ctxFor(result, result.calls[0]!, "claude/assistant/tool_use")).toEqual({ text: "ctx 3.6%", title: "turn 1 processed 35,599 of a 1M window" });
  expect(ctxFor(result, result.calls[0]!, "claude/user/tool_result")?.text).toBe("→ t2 3.6%");
  expect(ctxFor(result, result.calls[1]!, "claude/user/tool_result")?.text).toBe("ctx 3.6%"); // no next turn
  expect(ctxFor(result, call(3, [], 0, null), "claude/user/tool_result")).toBeNull();
});

test("TurnRawRecords renders one card per log line of the turn under the turn's id", () => {
  const lines = [
    JSON.stringify(claudeUser("go")),
    JSON.stringify(toolUse),
    JSON.stringify(toolResult),
    JSON.stringify(claudeAssistant([{ type: "text", text: "done" }])),
    "{broken",
  ];
  const { container } = render(<TurnRawRecords result={result} call={result.calls[1]!} lines={lines} view="nice" />);
  const root = container.querySelector('[data-el="TurnRawRecords"]') as HTMLElement;
  expect(root.id).toBe("1feb573f-ba51/t2");
  expect(root.querySelector("h4")?.textContent).toContain("lines 3-5 · context 3.6% of 1M");
  expect([...root.querySelectorAll('.rec[data-el="RecordCard"]')].map((c) => c.id)).toEqual(["L3", "L4", "L5"]);
  expect(root.querySelector("#L3")?.getAttribute("data-kind")).toBe("claude/user/tool_result");
  expect(root.querySelector("#L5")?.getAttribute("data-kind")).toBe("claude/unparseable");
});

test("TurnRawRecords says so when there is no log or no records", () => {
  const { container } = render(<TurnRawRecords result={result} call={result.calls[0]!} lines={null} view="nice" />);
  expect(container.textContent).toContain("no captured log beside this result");
  const { container: c2 } = render(<TurnRawRecords result={result} call={call(3, [], 1, 0.1)} lines={["{}"]} view="nice" />);
  expect(c2.textContent).toContain("no records attributed to this turn");
});

test("RecordViewToggle reports the chosen view", () => {
  const onChange = vi.fn();
  render(<RecordViewToggle view="nice" onChange={onChange} />);
  fireEvent.click(screen.getByText("raw JSON"));
  expect(onChange).toHaveBeenCalledWith("raw");
});
