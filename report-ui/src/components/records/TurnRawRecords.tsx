/**
 * The session-log records of one turn (glossary: `TurnRawRecords`): a heading with the
 * turn's line ranges and its measured context, then one `RecordCard` per log line. A call
 * record is annotated with its own context (`ctx 7.2%`); a tool result with the next turn's
 * prompt it became part of (`→ t4 7.5%`).
 */
import { El } from "@/components/El";
import { fmt, pct, windowLabel } from "@/lib/format";
import { sessionSearch } from "@/lib/route";
import { categoryOf, classify } from "@/lib/records";
import type { Call, RunResult } from "@/lib/types";
import { Muted } from "./Comp";
import { RecordCardClaude, RecordCardCodex, type CtxTag, type RecordView } from "./RecordCard";

/** `<session_id>/t<n>`: the id of a turn's details block, the target of `#session=…&turn=n`. */
export const turnId = (sessionId: string, n: number): string => `${sessionId}/t${n}`;

/** `[3, 4, 5, 9]` -> `3-5, 9`. */
export function ranges(nums: number[]): string {
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
}

const RESULT_LIKE = new Set(["tool_result", "tool_exec", "file_change"]);

/** The context annotation for one record of turn `call`, or null when the turn has no measurement. */
export function ctxFor(result: RunResult, call: Call, kind: string): CtxTag | null {
  if (call.context_pct == null) return null;
  const next = result.calls[call.n] ?? null; // calls are 0-indexed; call.n is 1-based, so this is turn n+1
  if (RESULT_LIKE.has(categoryOf(kind)) && next && next.context_pct != null) {
    return {
      text: `→ t${next.n} ${pct(next.context_pct)}`,
      title: `this result enters turn ${next.n}'s context, measured at ${fmt(next.context_tokens)} tokens`,
    };
  }
  return {
    text: `ctx ${pct(call.context_pct)}`,
    title: `turn ${call.n} processed ${fmt(call.context_tokens)} of a ${windowLabel(result.context_window)} window`,
  };
}

interface Props {
  result: RunResult;
  call: Call;
  /** The session log; `lines[n - 1]` is log line `n`. `null` when no log was captured beside the result. */
  lines: string[] | null;
  view: RecordView;
}

export function TurnRawRecords({ result, call, lines, view }: Props) {
  const records = call.records ?? [];
  return (
    <div
      className="detail SessionTurnDetails"
      style={{ borderRadius: 8, background: "color-mix(in srgb, var(--xh-accent) 5%, transparent)", padding: "0.6rem 0.8rem 1rem" }}
      id={turnId(result.session_id, call.n)}
      data-el="TurnRawRecords"
    >
      <h4 className="muted" style={{ margin: "0.6rem 0", fontSize: "0.75rem", fontWeight: 500, letterSpacing: "0.04em", textTransform: "uppercase" }}>
        Session-log records for this turn · lines {ranges(records)} · context {pct(call.context_pct)} of {windowLabel(result.context_window)}
        <El name="TurnRawRecords" />
      </h4>
      {lines == null ? (
        <p>
          <Muted>no captured log beside this result</Muted>
        </p>
      ) : records.length === 0 ? (
        <p>
          <Muted>no records attributed to this turn</Muted>
        </p>
      ) : (
        records.map((n) => {
          const raw = lines[n - 1] ?? "";
          let kind = `${result.harness}/unparseable`;
          try {
            kind = classify(result.harness, JSON.parse(raw));
          } catch {
            /* unparseable stays unparseable */
          }
          const Card = result.harness === "codex" ? RecordCardCodex : RecordCardClaude;
          return (
            <Card
              key={n}
              lineNo={n}
              raw={raw}
              ctx={ctxFor(result, call, kind)}
              view={view}
              permalink={sessionSearch(result.session_id, null, null, { line: n })}
            />
          );
        })
      )}
    </div>
  );
}
