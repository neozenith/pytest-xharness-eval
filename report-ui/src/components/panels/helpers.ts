/** Pure helpers of the SessionView panels, ported verbatim from the legacy page. */
import { NONE, fmt } from "@/lib/format";

/** `<session_id>/t<n>`: the SessionTurnId, also the element id of the turn's TurnRawRecords block. */
export const turnId = (sessionId: string, n: number): string => `${sessionId}/t${n}`;

/** `[1,2,3,5,7,8]` -> `1-3, 5, 7-8`, the way the turn table shows a turn's log lines. */
export const ranges = (nums: number[]): string => {
  const out: string[] = [];
  let s: number | null = null;
  let p: number | null = null;
  for (const n of nums) {
    if (s == null || p == null) {
      s = p = n;
    } else if (n === p + 1) {
      p = n;
    } else {
      out.push(s === p ? `${s}` : `${s}-${p}`);
      s = p = n;
    }
  }
  if (s != null) out.push(s === p ? `${s}` : `${s}-${p}`);
  return out.join(", ");
};

/** `HH:MM:SS.mmm` of an ISO timestamp, local time. */
export const clock = (iso: string | null | undefined): string => {
  if (!iso) return NONE;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return `${d.toLocaleTimeString("en-AU", { hour12: false })}.${String(d.getMilliseconds()).padStart(3, "0")}`;
};

export const ms = (v: number | null | undefined): string => (v == null ? NONE : `${fmt(Math.round(v))} ms`);

/** A USD-per-token rate shown per million tokens, as `rates_applied` is read. */
export const rate = (x: number | null | undefined): string => (x == null ? NONE : `$${(Number(x) * 1e6).toFixed(3)} /M`);

// Mirrors pytest_xharness_eval/records.py KINDS (ADR 0022, 0024); the colour is `--xh-category-<category>`.
const KIND_CATEGORY: Record<string, string> = {
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
const PREFIX_CATEGORY: [string, string][] = [
  ["claude/attachment/", "harness_meta"],
  ["codex/event_msg/item_completed/", "lifecycle"],
  ["codex/event_msg/", "lifecycle"],
  ["codex/response_item/message/", "harness_context"],
  ["codex/response_item/", "harness_meta"],
];

export const categoryOfKind = (kind: string): string => KIND_CATEGORY[kind] ?? PREFIX_CATEGORY.find(([p]) => kind.startsWith(p))?.[1] ?? "unknown";

export type TurnView = "summary" | "detailed";
export type RecordView = "nice" | "raw";
