/**
 * The catalogue of session-log record kinds: a mirror of `pytest_xharness_eval/records.py`
 * (ADR 0022, ADR 0024). Every log line is a record; `classify` maps it to a *kind*
 * (`harness/type[/subtype]`) and every kind belongs to a *category* that says what sort of
 * information it carries. The glossary's "Record kinds" table is the contract; an unseen
 * shape classifies as `<harness>/unknown` rather than failing.
 */

/** A parsed session-log record; the shapes differ per harness so only `unknown` is honest. */
export type Rec = Record<string, unknown>;

/** Category -> pill colour (white text on each passes WCAG AA). The page overrides these from report.tokens.json. */
export const CATEGORIES: Record<string, string> = {
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

/** Kind -> category. Kinds not listed fall back by prefix in `categoryOf`. */
export const KINDS: Record<string, string> = {
  "claude/user/prompt": "prompt",
  "claude/user/injected": "harness_context",
  "claude/user/tool_result": "tool_result",
  "claude/assistant/text": "assistant_text",
  "claude/assistant/thinking": "thinking",
  "claude/assistant/tool_use": "tool_call",
  "claude/assistant/synthetic": "harness_meta",
  "claude/attachment/total_tokens_reminder": "harness_meta",
  "claude/attachment/deferred_tools_delta": "harness_context",
  "claude/attachment/agent_listing_delta": "harness_context",
  "claude/attachment/skill_listing": "harness_context",
  "claude/attachment/auto_mode": "harness_meta",
  "claude/attachment/task_reminder": "harness_meta",
  "claude/ai-title": "harness_meta",
  "claude/atis-latch": "harness_meta",
  "claude/last-prompt": "harness_meta",
  "claude/queue-operation": "harness_meta",
  "claude/system": "harness_meta",
  "codex/session_meta": "session_meta",
  "codex/turn_context": "session_meta",
  "codex/world_state": "harness_meta",
  "codex/response_item/message/user": "prompt",
  "codex/response_item/message/user/injected": "harness_context",
  "codex/response_item/message/developer": "harness_context",
  "codex/response_item/message/system": "harness_context",
  "codex/response_item/message/assistant": "assistant_text",
  "codex/response_item/reasoning": "thinking",
  "codex/response_item/custom_tool_call": "tool_call",
  "codex/response_item/function_call": "tool_call",
  "codex/response_item/custom_tool_call_output": "tool_result",
  "codex/response_item/function_call_output": "tool_result",
  "codex/event_msg/task_started": "lifecycle",
  "codex/event_msg/task_complete": "lifecycle",
  "codex/event_msg/token_count": "usage",
  "codex/event_msg/item_completed/AgentMessage": "assistant_text",
  "codex/event_msg/item_completed/CommandExecution": "tool_exec",
  "codex/event_msg/item_completed/FileChange": "file_change",
  "codex/event_msg/item_completed/Reasoning": "thinking",
  "codex/event_msg/item_completed/UserMessage": "prompt",
  "codex/event_msg/item_completed/UserMessage/injected": "harness_context",
};

/**
 * Human names for the categories, as the glossary and the RecordKindsPanel show them.
 * `records.py` carries no such table; this is the page's own wording.
 */
export const NICE: Record<string, string> = {
  prompt: "prompt",
  assistant_text: "assistant text",
  thinking: "thinking",
  tool_call: "tool call",
  tool_result: "tool result",
  tool_exec: "tool execution",
  file_change: "file change",
  usage: "usage",
  harness_context: "harness context",
  harness_meta: "harness meta",
  session_meta: "session meta",
  lifecycle: "lifecycle",
  unknown: "unknown",
};

const PREFIX_CATEGORY: [string, string][] = [
  ["claude/attachment/", "harness_meta"],
  ["codex/event_msg/item_completed/", "lifecycle"],
  ["codex/event_msg/", "lifecycle"],
  ["codex/response_item/message/", "harness_context"],
  ["codex/response_item/", "harness_meta"],
];

const isObj = (v: unknown): v is Rec => typeof v === "object" && v !== null && !Array.isArray(v);

const blockTypes = (c: unknown): Set<string> => new Set((Array.isArray(c) ? c : []).filter(isObj).map((b) => String(b.type)));

/** Flatten a content value (string or list of text-bearing blocks) to its text. */
export const messageText = (c: unknown): string =>
  typeof c === "string" ? c : Array.isArray(c) ? c.map((b) => (isObj(b) ? String(b.text ?? "") : "")).join("\n") : "";

/** The name of the XML-style tag a message opens with, or null for plain prose. */
export const leadingTag = (t: unknown): string | null => {
  const m = /^\s*<([A-Za-z_][\w.-]*)[\s>/]/.exec(String(t ?? ""));
  return m ? m[1]! : null;
};

/** True for an assistant message Claude Code wrote itself (model "<synthetic>") rather than received from the API. */
export const isSynthetic = (message: Rec | undefined): boolean => String(message?.model ?? "").startsWith("<");

function classifyClaude(r: Rec): string {
  const t = String(r.type ?? "unknown");
  const message = isObj(r.message) ? r.message : undefined;
  if (t === "user") {
    const c = message?.content;
    if (typeof c !== "string" && blockTypes(c).has("tool_result")) return "claude/user/tool_result";
    return leadingTag(messageText(c)) ? "claude/user/injected" : "claude/user/prompt";
  }
  if (t === "assistant") {
    if (isSynthetic(message)) return "claude/assistant/synthetic";
    const k = blockTypes(message?.content);
    if (k.has("tool_use")) return "claude/assistant/tool_use";
    if (k.has("thinking") && !k.has("text")) return "claude/assistant/thinking";
    return "claude/assistant/text";
  }
  if (t === "attachment") {
    const a = isObj(r.attachment) ? r.attachment : {};
    return `claude/attachment/${String(a.type ?? "unknown")}`;
  }
  return `claude/${t}`;
}

function classifyCodex(r: Rec): string {
  const t = String(r.type ?? "unknown");
  const p = isObj(r.payload) ? r.payload : {};
  if (t === "response_item") {
    const s = String(p.type ?? "unknown");
    if (s === "message") {
      const role = String(p.role ?? "unknown");
      const inj = role === "user" && leadingTag(messageText(p.content));
      return `codex/response_item/message/${role}${inj ? "/injected" : ""}`;
    }
    return `codex/response_item/${s}`;
  }
  if (t === "event_msg") {
    const s = String(p.type ?? "unknown");
    if (s === "item_completed") {
      const it = isObj(p.item) ? p.item : {};
      const kind = String(it.item_type ?? it.type ?? "unknown");
      const inj = kind === "UserMessage" && leadingTag(messageText(it.content));
      return `codex/event_msg/item_completed/${kind}${inj ? "/injected" : ""}`;
    }
    return `codex/event_msg/${s}`;
  }
  return `codex/${t}`;
}

/** The kind of one record: `harness/type[/subtype]`; never throws. */
export function classify(harness: string, r: unknown): string {
  if (!isObj(r)) return `${harness}/unknown`;
  return harness === "claude" ? classifyClaude(r) : classifyCodex(r);
}

/** The category a kind belongs to; unseen kinds fall back by prefix, then to `unknown`. */
export function categoryOf(kind: string): string {
  const direct = KINDS[kind];
  if (direct) return direct;
  return PREFIX_CATEGORY.find(([p]) => kind.startsWith(p))?.[1] ?? "unknown";
}

/** True for the record that carries a model call's usage: the measurement point of a turn. */
export const isCallRecord = (harness: string, rec: unknown): boolean => {
  if (!isObj(rec)) return false;
  if (harness === "claude") return rec.type === "assistant" && !isSynthetic(isObj(rec.message) ? rec.message : undefined);
  return rec.type === "event_msg" && isObj(rec.payload) && rec.payload.type === "token_count";
};
