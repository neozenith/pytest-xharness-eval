/**
 * T: one renderer per tool payload (glossary level *tool payloads*): Claude's `Bash`, `Read`,
 * `Edit`, `MultiEdit`, `Write`, `Skill`, `Glob`, `Grep`, and Codex's `exec` (the `cmd` inside
 * `tools.exec_command({...})` as a shell block, `apply_patch` bodies as diffs, the full
 * JavaScript collapsed). A tool with no renderer falls back to `T.fallback`.
 */
import type { ReactNode } from "react";
import { Comp, Mono } from "./Comp";
import { Bash, Code, Details, Diff, Json, Kvs, extLang } from "./values";

type Input = Record<string, unknown>;

const code = (v: unknown): ReactNode => (v ? <Mono>{String(v)}</Mono> : undefined);
const str = (v: unknown): string | undefined => (v == null ? undefined : String(v));

/**
 * A JavaScript object literal rewritten as JSON: bare keys quoted, single-quoted strings
 * double-quoted, trailing commas dropped. Anything that is not data (a call, an expression)
 * survives the rewrite and fails `JSON.parse`, which is the point: the session log is agent
 * output, so this text is never *evaluated* — an earlier `Function(...)` here ran it in the
 * reader's browser.
 */
function literalToJson(lit: string): string {
  let out = "";
  let i = 0;
  while (i < lit.length) {
    const ch = lit[i]!;
    if (ch === '"' || ch === "'") {
      let s = "";
      i++;
      while (i < lit.length && lit[i] !== ch) {
        if (lit[i] === "\\" && i + 1 < lit.length) {
          const next = lit[i + 1]!;
          s += next === "'" ? "'" : `\\${next}`;
          i += 2;
        } else {
          s += lit[i] === '"' ? '\\"' : lit[i];
          i++;
        }
      }
      out += `"${s}"`;
      i++;
    } else if (/[A-Za-z_$]/.test(ch)) {
      const id = /^[A-Za-z_$][\w$]*/.exec(lit.slice(i))![0];
      i += id.length;
      out += /^\s*:/.test(lit.slice(i)) ? `"${id}"` : id;
    } else if (ch === ",") {
      i++;
      if (!/^\s*[}\]]/.test(lit.slice(i))) out += ",";
    } else {
      out += ch;
      i++;
    }
  }
  return out;
}

/** The object literal inside `tools.exec_command({...})`, parsed leniently and never evaluated. */
export function codexExec(input: string): Input | null {
  const m = /exec_command\s*\(\s*(\{[\s\S]*?\})\s*\)/.exec(input || "");
  if (!m) return null;
  const lit = m[1]!;
  for (const text of [lit, literalToJson(lit)]) {
    try {
      const v: unknown = JSON.parse(text);
      if (v && typeof v === "object" && !Array.isArray(v)) return v as Input;
    } catch {
      /* not (yet) JSON */
    }
  }
  const cmd = /cmd\s*:\s*"((?:\\.|[^"\\])*)"/.exec(lit);
  return cmd ? { cmd: JSON.parse(`"${cmd[1]}"`) as string } : null;
}

/** A Claude `Edit` as a unified diff: old lines removed, new lines added. */
export function editDiff(input: Input): string {
  const old = String(input.old_string ?? "");
  const neu = String(input.new_string ?? "");
  const file = String(input.file_path || "");
  return (
    `--- ${file || "old"}\n+++ ${file || "new"}\n` +
    old
      .split("\n")
      .map((l) => "-" + l)
      .join("\n") +
    "\n" +
    neu
      .split("\n")
      .map((l) => "+" + l)
      .join("\n")
  );
}

const T: Record<string, (i: Input) => ReactNode> = {
  Bash: (i) => (
    <>
      <Kvs
        pairs={[
          ["description", str(i.description)],
          ["timeout", str(i.timeout)],
          ["run_in_background", i.run_in_background ? "true" : undefined],
        ]}
      />
      <Bash cmd={i.command} title="command" />
    </>
  ),
  Read: (i) => (
    <Kvs
      pairs={[
        ["file", code(i.file_path)],
        ["offset", str(i.offset)],
        ["limit", str(i.limit)],
        ["pages", str(i.pages)],
      ]}
    />
  ),
  Edit: (i) => (
    <>
      <Kvs
        pairs={[
          ["file", code(i.file_path)],
          ["replace_all", i.replace_all ? "true" : undefined],
        ]}
      />
      <Diff text={editDiff(i)} title="edit" />
    </>
  ),
  MultiEdit: (i) => (
    <>
      <Kvs pairs={[["file", code(i.file_path)]]} />
      {((i.edits as Input[] | undefined) ?? []).map((e, n) => (
        <Diff key={n} text={editDiff({ ...e, file_path: i.file_path })} title={`edit ${n + 1}`} />
      ))}
    </>
  ),
  Write: (i) => (
    <>
      <Kvs pairs={[["file", code(i.file_path)]]} />
      <Code lang={extLang(i.file_path)} text={i.content} title="content" />
    </>
  ),
  Skill: (i) => (
    <Kvs
      pairs={[
        ["skill", code(i.skill)],
        ["args", str(i.args)],
      ]}
    />
  ),
  Glob: (i) => (
    <Kvs
      pairs={[
        ["pattern", code(i.pattern)],
        ["path", code(i.path)],
      ]}
    />
  ),
  Grep: (i) => (
    <Kvs
      pairs={[
        ["pattern", code(i.pattern)],
        ["path", code(i.path)],
        ["glob", str(i.glob)],
        ["output_mode", str(i.output_mode)],
      ]}
    />
  ),
};

/** Codex `exec`: its input is a JavaScript string, not an object. */
function Exec({ input }: { input: unknown }) {
  if (typeof input !== "string") return <Json value={input} />;
  if (/\*\*\* Begin Patch/.test(input)) {
    const m = /\*\*\* Begin Patch[\s\S]*?\*\*\* End Patch/.exec(input.replace(/\\n/g, "\n"));
    return (
      <>
        <Diff text={m ? m[0] : input} title="apply_patch" />
        <Details summary="full tool input (javascript)">
          <Code lang="javascript" text={input} />
        </Details>
      </>
    );
  }
  const x = codexExec(input);
  if (!x) return <Code lang="javascript" text={input} title="input" />;
  return (
    <>
      <Kvs
        pairs={[
          ["workdir", code(x.workdir)],
          ["yield_time_ms", str(x.yield_time_ms)],
          ["max_output_tokens", str(x.max_output_tokens)],
        ]}
      />
      <Bash cmd={x.cmd} title="cmd" />
      <Details summary="full tool input (javascript)">
        <Code lang="javascript" text={input} />
      </Details>
    </>
  );
}

/** The payload of one tool call, by tool name; unknown tools show their input as code or JSON. */
export function ToolInput({ name, input }: { name: unknown; input: unknown }) {
  const key = String(name ?? "");
  if (key === "exec")
    return (
      <Comp el="T.exec">
        <Exec input={input} />
      </Comp>
    );
  const render = T[key];
  if (render) {
    const i = (input && typeof input === "object" ? input : {}) as Input;
    return <Comp el={`T.${key}`}>{render(i)}</Comp>;
  }
  return <Comp el="T.fallback">{typeof input === "string" ? <Code lang="" text={input} title="input" /> : <Json value={input ?? {}} title="input" />}</Comp>;
}
