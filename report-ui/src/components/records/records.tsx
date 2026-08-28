/**
 * R: one renderer per record kind in the catalogue (glossary level *records*), plus
 * `R.fallback` (the raw JSON) for a kind no renderer claims. `RecordBody` picks the renderer
 * by the record's classified kind and appends the envelope.
 */
import type { ReactNode } from "react";
import { fmt, secs } from "@/lib/format";
import { type Rec, classify } from "@/lib/records";
import { Comp, Muted, Notice, Tag, Mono } from "./Comp";
import { Blocks, ClaudeMessage, CodexItem, Prose, texts } from "./blocks";
import { ToolInput } from "./tools";
import { Bash, Code, Details, Diff, Envelope, Flag, Json, Kvs, Listing, Output, Text, Usage, Xmlish, pretty, type Pair } from "./values";

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const obj = (v: unknown): Obj => (isObj(v) ? v : {});
const code = (v: unknown): ReactNode => (v ? <Mono>{String(v)}</Mono> : undefined);
const str = (v: unknown): string | undefined => (v == null ? undefined : String(v));
const num = (v: unknown): number | null => (typeof v === "number" ? v : null);
const ms = (v: unknown): string => (v == null ? "–" : `${fmt(Math.round(Number(v)))} ms`);
const list = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);

const Injected = () => <Muted>harness-injected; not the prompt under test</Muted>;

const chips = (names: unknown, tone?: "added" | "removed"): ReactNode =>
  list(names).length ? (
    <>
      {list(names).map((n, i) => (
        <Tag key={i} tone={tone}>
          {String(n)}
        </Tag>
      ))}
    </>
  ) : (
    "–"
  );

const R: Record<string, (r: Rec) => ReactNode> = {
  "claude/user/prompt": (r) => <Blocks content={obj(r.message).content} />,
  "claude/user/injected": (r) => (
    <>
      <Injected />
      <Blocks content={obj(r.message).content} />
    </>
  ),
  "claude/user/tool_result": (r) => (
    <>
      <Blocks content={obj(r.message).content} />
      <Details summary="toolUseResult (harness view of the result)">{r.toolUseResult ? <Json value={r.toolUseResult} /> : null}</Details>
    </>
  ),
  "claude/assistant/text": (r) => <ClaudeMessage message={r.message} />,
  "claude/assistant/thinking": (r) => <ClaudeMessage message={r.message} />,
  "claude/assistant/tool_use": (r) => <ClaudeMessage message={r.message} />,
  "claude/assistant/synthetic": (r) => (
    <>
      <Notice>harness-generated message, not a model call</Notice>
      <Blocks content={obj(r.message).content} />
      <Kvs pairs={[["stop", str(obj(r.message).stop_reason)]]} />
      {r.error ? <Json value={r.error} title="error" /> : null}
    </>
  ),
  "claude/attachment/total_tokens_reminder": (r) => <Xmlish text={obj(r.attachment).text} />,
  "claude/attachment/deferred_tools_delta": (r) => {
    const a = obj(r.attachment);
    return (
      <Kvs
        pairs={[
          ["added", chips(a.addedNames, "added")],
          ["removed", chips(a.removedNames, "removed")],
          ["re-added", chips(a.readdedNames)],
          ["pending MCP", a.pendingMcpServers ? pretty(a.pendingMcpServers) : undefined],
        ]}
      />
    );
  },
  "claude/attachment/agent_listing_delta": (r) => {
    const a = obj(r.attachment);
    return (
      <>
        <Kvs pairs={[["added types", chips(a.addedTypes)]]} />
        <Listing text={list(a.addedLines).join("\n")} />
      </>
    );
  },
  "claude/attachment/skill_listing": (r) => <Listing text={obj(r.attachment).content} />,
  "claude/attachment/auto_mode": (r) => (
    <Kvs
      pairs={Object.entries(obj(r.attachment))
        .filter(([k]) => k !== "type")
        .map(([k, v]): Pair => [k, <Flag key={k} value={v} />])}
    />
  ),
  "claude/attachment/task_reminder": (r) => {
    const a = obj(r.attachment);
    return (
      <>
        <Kvs pairs={[["items", fmt(num(a.itemCount))]]} />
        {list(a.content).length ? <Json value={a.content} title="tasks" /> : null}
      </>
    );
  },
  "claude/ai-title": (r) => <Text text={r.aiTitle} />,
  "claude/atis-latch": (r) => <Kvs pairs={[["atis", str(r.atis) || "(empty)"]]} />,
  "claude/last-prompt": (r) => (
    <>
      <Text text={r.lastPrompt} />
      <Kvs pairs={[["leafUuid", code(r.leafUuid)]]} />
    </>
  ),
  "claude/queue-operation": (r) => (
    <>
      <Kvs pairs={[["operation", str(r.operation)]]} />
      <Prose text={r.content} />
    </>
  ),
  "codex/session_meta": (r) => {
    const p = obj(r.payload);
    const base = obj(p.base_instructions);
    const baseText = typeof base.text === "string" ? base.text : "";
    return (
      <>
        <Kvs
          pairs={[
            ["cwd", code(p.cwd)],
            ["cli", str(p.cli_version)],
            ["provider", str(p.model_provider)],
            ["source", str(p.source)],
            ["originator", str(p.originator)],
            ["history mode", str(p.history_mode)],
            ["context window", fmt(num(p.context_window))],
            ["git", p.git ? pretty(p.git) : undefined],
          ]}
        />
        <Details summary={`base_instructions (${fmt(baseText.length)} chars)`}>{baseText ? <Code lang="markdown" text={baseText} /> : null}</Details>
      </>
    );
  },
  "codex/turn_context": (r) => {
    const p = obj(r.payload);
    const sandbox = obj(p.sandbox_policy);
    return (
      <>
        <Kvs
          pairs={[
            ["model", code(p.model)],
            ["cwd", code(p.cwd)],
            ["approval", str(p.approval_policy)],
            ["sandbox", str(sandbox.type)],
            ["network", <Flag key="n" value={sandbox.network_access} />],
            ["personality", str(p.personality)],
            ["timezone", str(p.timezone)],
            ["date", str(p.current_date)],
          ]}
        />
        <Details summary="all turn context">
          <Json value={p} />
        </Details>
      </>
    );
  },
  "codex/world_state": (r) => {
    const p = obj(r.payload);
    const state = obj(p.state);
    const pairs: Pair[] = [["full snapshot", <Flag key="f" value={p.full} />]];
    for (const [k, v] of Object.entries(state)) pairs.push([k, typeof v === "boolean" ? <Flag key={k} value={v} /> : pretty(v)]);
    return (
      <>
        <Kvs pairs={pairs} />
        {Object.keys(state).length ? null : <Muted>empty state</Muted>}
      </>
    );
  },
  "codex/response_item/message/user": (r) => <Blocks content={obj(r.payload).content} />,
  "codex/response_item/message/user/injected": (r) => (
    <>
      <Injected />
      <Blocks content={obj(r.payload).content} />
    </>
  ),
  "codex/response_item/message/developer": (r) => <Blocks content={obj(r.payload).content} />,
  "codex/response_item/message/system": (r) => <Blocks content={obj(r.payload).content} />,
  "codex/response_item/message/assistant": (r) => {
    const p = obj(r.payload);
    return (
      <>
        <Blocks content={p.content} />
        <Kvs
          pairs={[
            ["phase", str(p.phase)],
            ["message id", code(p.id)],
          ]}
        />
      </>
    );
  },
  "codex/response_item/reasoning": (r) => {
    const p = obj(r.payload);
    return (
      <>
        <Text text={texts(p.summary) || "(reasoning encrypted; no summary)"} />
        <Kvs pairs={[["encrypted", `${fmt(String(p.encrypted_content ?? "").length)} chars`]]} />
      </>
    );
  },
  "codex/response_item/custom_tool_call": (r) => {
    const p = obj(r.payload);
    return (
      <>
        <Kvs
          pairs={[
            ["tool", code(p.name)],
            ["call_id", code(p.call_id)],
            ["status", str(p.status)],
          ]}
        />
        <ToolInput name={p.name} input={p.input} />
      </>
    );
  },
  "codex/response_item/function_call": (r) => {
    const p = obj(r.payload);
    let a: unknown = p.arguments;
    if (typeof a === "string") {
      try {
        a = JSON.parse(a);
      } catch {
        /* keep the string */
      }
    }
    return (
      <>
        <Kvs
          pairs={[
            ["tool", code(p.name)],
            ["call_id", code(p.call_id)],
          ]}
        />
        <ToolInput name={p.name} input={a} />
      </>
    );
  },
  "codex/response_item/custom_tool_call_output": (r) => {
    const p = obj(r.payload);
    return (
      <>
        <Kvs pairs={[["call_id", code(p.call_id)]]} />
        <Output text={texts(p.output)} title="output" />
      </>
    );
  },
  "codex/response_item/function_call_output": (r) => {
    const p = obj(r.payload);
    return (
      <>
        <Kvs pairs={[["call_id", code(p.call_id)]]} />
        <Output text={texts(p.output)} title="output" />
      </>
    );
  },
  "codex/event_msg/task_started": (r) => {
    const p = obj(r.payload);
    return (
      <Kvs
        pairs={[
          ["turn_id", code(p.turn_id)],
          ["context window", fmt(num(p.model_context_window))],
          ["mode", str(p.collaboration_mode_kind)],
          ["trace", code(p.trace_id)],
        ]}
      />
    );
  },
  "codex/event_msg/task_complete": (r) => {
    const p = obj(r.payload);
    return (
      <>
        <Kvs
          pairs={[
            ["duration", secs(num(p.duration_ms))],
            ["time to first token", ms(p.time_to_first_token_ms)],
          ]}
        />
        <Prose text={p.last_agent_message} />
      </>
    );
  },
  "codex/event_msg/token_count": (r) => {
    const p = obj(r.payload);
    const i = obj(p.info);
    return (
      <>
        <b className="sublabel">this call</b>
        <Usage usage={i.last_token_usage} />
        <b className="sublabel">cumulative</b>
        <Usage usage={i.total_token_usage} />
        <Kvs pairs={[["context window", fmt(num(i.model_context_window))]]} />
        <Details summary="rate limits">{p.rate_limits ? <Json value={p.rate_limits} /> : null}</Details>
      </>
    );
  },
  "codex/event_msg/item_completed/AgentMessage": (r) => <CodexItem item={obj(r.payload).item} />,
  "codex/event_msg/item_completed/CommandExecution": (r) => {
    const it = obj(obj(r.payload).item);
    const command = Array.isArray(it.command) ? it.command.join(" ") : it.command;
    return (
      <>
        <Kvs
          pairs={[
            ["cwd", code(it.cwd)],
            ["status", str(it.status)],
            ["exit", str(it.exit_code)],
            ["duration", it.duration_ms != null ? secs(num(it.duration_ms)) : undefined],
            ["process", str(it.process_id)],
          ]}
        />
        <Bash cmd={command} title="command" />
        {it.aggregated_output ? <Output text={it.aggregated_output} title="output" /> : null}
        <Details summary="parsed_cmd">{it.parsed_cmd ? <Json value={it.parsed_cmd} /> : null}</Details>
      </>
    );
  },
  "codex/event_msg/item_completed/FileChange": (r) => {
    const changes = obj(obj(obj(r.payload).item).changes);
    return (
      <>
        {Object.entries(changes).map(([path, ch]) => {
          const c = obj(ch);
          return (
            <div key={path}>
              <Kvs
                pairs={[
                  ["file", code(path)],
                  ["change", str(c.type)],
                ]}
              />
              <Diff text={(c.unified_diff as string) || pretty(ch)} title="unified diff" />
            </div>
          );
        })}
      </>
    );
  },
  "codex/event_msg/item_completed/Reasoning": (r) => <Text text={texts(obj(obj(r.payload).item).summary_text) || "(no reasoning summary)"} />,
  "codex/event_msg/item_completed/UserMessage": (r) => <CodexItem item={obj(r.payload).item} />,
  "codex/event_msg/item_completed/UserMessage/injected": (r) => (
    <>
      <Injected />
      <CodexItem item={obj(r.payload).item} />
    </>
  ),
};

/** The renderer for a kind, or null when the kind has none. */
export const hasRenderer = (kind: string): boolean => kind in R;

/** The nice body of one parsed record: its kind's renderer (or the JSON fallback) and the envelope. */
export function RecordBody({ harness, rec, kind }: { harness: string; rec: Rec; kind?: string }) {
  const k = kind ?? classify(harness, rec);
  const render = R[k];
  return (
    <>
      {render ? (
        <Comp el={`R.${k}`}>{render(rec)}</Comp>
      ) : (
        <Comp el="R.fallback">
          <Json value={rec} />
        </Comp>
      )}
      <Envelope rec={rec} />
    </>
  );
}
