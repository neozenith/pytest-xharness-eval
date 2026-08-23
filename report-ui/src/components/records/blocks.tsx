/**
 * B: one renderer per content block type (glossary level *blocks*): `text`, `input_text`,
 * `output_text`, `Text`, `thinking`, `redacted_thinking`, `tool_use`, `tool_result`; and the
 * two message renderers, `claudeMessage` and `codexItem`.
 */
import type { ReactNode } from "react";
import { fmt } from "@/lib/format";
import { leadingTag } from "@/lib/records";
import { Comp, Mono } from "./Comp";
import { ToolInput } from "./tools";
import { Details, Json, Kvs, Output, Text, Usage, Xmlish, pretty } from "./values";

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const code = (v: unknown): ReactNode => (v ? <Mono>{String(v)}</Mono> : undefined);
const str = (v: unknown): string | undefined => (v == null ? undefined : String(v));

/** The text carried by a content value: a string, or the text/output of each block. */
export const texts = (content: unknown): string =>
  Array.isArray(content)
    ? content
        .map((b) => (isObj(b) ? ((b.text ?? b.output) as string | undefined) : typeof b === "string" ? b : ""))
        .filter(Boolean)
        .join("\n")
    : typeof content === "string"
      ? content
      : content == null
        ? ""
        : pretty(content);

/** Prose, or XML-tagged sections when the text opens with a tag. */
export const Prose = ({ text }: { text: unknown }) => (leadingTag(text) ? <Xmlish text={text} /> : <Text text={text} />);

const B: Record<string, (b: Obj) => ReactNode> = {
  text: (b) => <Prose text={b.text} />,
  input_text: (b) => <Prose text={b.text} />,
  output_text: (b) => <Prose text={b.text} />,
  Text: (b) => <Prose text={b.text} />,
  thinking: (b) => (
    <>
      <Text text={(b.thinking as string) || "(thinking text omitted by the CLI)"} />
      <Kvs pairs={[["signature", b.signature ? `${fmt(String(b.signature).length)} chars` : undefined]]} />
    </>
  ),
  redacted_thinking: () => <Text text="(redacted thinking)" />,
  tool_use: (b) => (
    <>
      <Kvs
        pairs={[
          ["tool", code(b.name)],
          ["id", code(b.id)],
          ["caller", str((b.caller as Obj | undefined)?.type)],
        ]}
      />
      <ToolInput name={b.name} input={b.input} />
    </>
  ),
  tool_result: (b) => (
    <>
      <Kvs
        pairs={[
          ["tool_use_id", code(b.tool_use_id)],
          ["is_error", b.is_error ? <span className="text-bad">true</span> : "false"],
        ]}
      />
      <Output text={texts(b.content)} title="content" />
    </>
  ),
};

const BLOCK_COLOUR: Record<string, string> = {
  tool_use: "var(--xh-category-tool_call, #4338ca)",
  tool_result: "var(--xh-category-tool_result, #0f766e)",
  thinking: "var(--xh-category-thinking, #6d28d9)",
  text: "var(--xh-category-assistant_text, #065f46)",
};

/** One content block: a left-ruled section headed by its type. */
export function Block({ block }: { block: unknown }) {
  if (typeof block === "string") return <Prose text={block} />;
  const b = isObj(block) ? block : {};
  const kind = String(b.type ?? "unknown");
  const render = B[kind];
  return (
    <div className={`block ${kind} my-[0.45rem] border-l-[3px] py-[0.1rem] pl-[0.7rem]`} style={{ borderColor: BLOCK_COLOUR[kind] ?? "var(--xh-line)" }}>
      <div className="bhead text-muted-foreground mb-[0.15rem] font-mono text-[0.72rem]">{kind}</div>
      {render ? (
        <Comp el={`B.${kind}`}>{render(b)}</Comp>
      ) : (
        <Comp el="B.fallback">
          <Json value={b} />
        </Comp>
      )}
    </div>
  );
}

/** A message's content: prose for a string, one Block per element for a list. */
export function Blocks({ content }: { content: unknown }) {
  if (typeof content === "string") return <Prose text={content} />;
  const list = Array.isArray(content) ? content : [];
  return (
    <>
      {list.map((b, i) => (
        <Block key={i} block={b} />
      ))}
    </>
  );
}

/** A Claude API message: its blocks, then model, stop reason, message id and usage. */
export function ClaudeMessage({ message }: { message: unknown }) {
  const m = isObj(message) ? message : {};
  return (
    <Comp el="claudeMessage">
      <Blocks content={m.content} />
      <Kvs
        pairs={[
          ["model", str(m.model)],
          ["stop", str(m.stop_reason)],
          ["message id", code(m.id)],
        ]}
      />
      <Usage usage={m.usage} />
    </Comp>
  );
}

/** A Codex item: its content blocks, with every other field collapsed. */
export function CodexItem({ item }: { item: unknown }) {
  const it = isObj(item) ? item : {};
  const { content, ...rest } = it;
  return (
    <Comp el="codexItem">
      <Blocks content={content} />
      <Details summary="item fields">
        <Json value={rest} />
      </Details>
    </Comp>
  );
}
