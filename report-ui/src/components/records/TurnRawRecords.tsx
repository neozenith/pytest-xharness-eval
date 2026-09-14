/**
 * The transcript records of one turn (glossary: `TurnRawRecords`, `SubagentRawRecords`): a
 * heading with the turn's line ranges and its measured context, then one `RecordCard` per
 * log line. A call record is annotated with its own context (`ctx 7.2%`); a tool result with
 * the next turn's prompt it became part of (`→ t4 7.5%`).
 *
 * A session has more than one transcript: its own `log.jsonl`, and one under `subagents/`
 * per thread it spawned (ADR 0033), each numbering its lines from 1 and each with a ledger
 * of its own. Both are the same thing to a reader — turns, records, line numbers — so both
 * render through `ThreadRawRecords`, and a `RecordThread` is what tells them apart: which
 * ledger measures the turn, which transcript the line numbers index, and how a record's
 * element id and deeplink are spelled so two threads' `L7`s never collide.
 */
import { El } from "@/components/El";
import { fmt, pct, windowLabel } from "@/lib/format";
import { sessionSearch } from "@/lib/route";
import { categoryOf, classify } from "@/lib/records";
import type { Call, RunResult, Subagent } from "@/lib/types";
import { Muted } from "./Comp";
import { RecordCard, type CtxTag, type RecordView } from "./RecordCard";

/** `<session_id>/t<n>`: the id of a turn's details block, the target of `?session=…&turn=n`. */
export const turnId = (sessionId: string, n: number): string => `${sessionId}/t${n}`;

/** `<subagent_id>/t<n>`: the id of a spawned thread's turn block, the target of `?…&subturn=<id>/<n>`. */
export const subagentTurnId = (subagentId: string, n: number): string => `${subagentId}/t${n}`;

/** `<subagent_id>/L<n>`: a record card's id inside a spawned thread, distinct from the primary `L<n>`. */
export const subagentLineId = (subagentId: string, line: number): string => `${subagentId}/L${line}`;

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

/**
 * What annotating a record needs of a thread: the ledger the turn belongs to, so the *next*
 * turn can be found, and the window its percentages are of. A `RunResult` satisfies it as it
 * stands; a subagent supplies its own `calls` and the run's window, which is the one both
 * threads were measured against.
 */
export interface Ledger {
  calls: Call[];
  context_window: number | null;
}

/** The context annotation for one record of turn `call`, or null when the turn has no measurement. */
export function ctxFor(ledger: Ledger, call: Call, kind: string): CtxTag | null {
  if (call.context_pct == null) return null;
  const next = ledger.calls[call.n] ?? null; // calls are 0-indexed; call.n is 1-based, so this is turn n+1
  if (RESULT_LIKE.has(categoryOf(kind)) && next && next.context_pct != null) {
    return {
      text: `→ t${next.n} ${pct(next.context_pct)}`,
      title: `this result enters turn ${next.n}'s context, measured at ${fmt(next.context_tokens)} tokens`,
    };
  }
  return {
    text: `ctx ${pct(call.context_pct)}`,
    title: `turn ${call.n} processed ${fmt(call.context_tokens)} of a ${windowLabel(ledger.context_window)} window`,
  };
}

/**
 * One transcript on the page: the primary session log, or one spawned thread's. Everything
 * `ThreadRawRecords` needs that differs between the two, and nothing that does not.
 */
export interface RecordThread {
  /** The harness whose record catalogue classifies these lines; a subagent shares its parent's. */
  harness: string;
  /** The ledger this turn belongs to, and the window its percentages are of. */
  ledger: Ledger;
  /** The transcript: `lines[n - 1]` is line `n`. `null` when none was captured. */
  lines: string[] | null;
  /** Why there is no transcript, when the load failed rather than never happened. */
  error?: string | null;
  /** What the heading calls this transcript ("Session-log", "Transcript"). */
  what: string;
  /** The glossary name of the block this thread renders as. */
  el: "TurnRawRecords" | "SubagentRawRecords";
  /** The element id of a turn's records block. */
  blockId: (n: number) => string;
  /** The element id of one record card, unique across every thread on the page. */
  anchor: (line: number) => string;
  /** The deeplink to one record, or undefined when this thread is not addressable by URL. */
  permalink: (line: number) => string | undefined;
  /** The class the block carries, which names it the way `el` does. */
  className: string;
}

/** The session's own log: `L<n>` ids and `line=` deeplinks, exactly as they have always been. */
export const primaryThread = (result: RunResult, lines: string[] | null): RecordThread => ({
  harness: result.harness,
  ledger: result,
  lines,
  what: "Session-log",
  el: "TurnRawRecords",
  className: "detail SessionTurnDetails",
  blockId: (n) => turnId(result.session_id, n),
  anchor: (line) => `L${line}`,
  permalink: (line) => sessionSearch(result.session_id, null, null, { line }),
});

/**
 * One spawned thread's transcript: its own ledger, its own line numbering, and ids and
 * deeplinks qualified by the subagent id so they cannot collide with the primary thread's.
 */
export const subagentThread = (result: RunResult, sub: Subagent, lines: string[] | null, error: string | null = null): RecordThread => ({
  harness: result.harness,
  ledger: { calls: sub.calls, context_window: result.context_window },
  lines,
  error,
  what: "Transcript",
  el: "SubagentRawRecords",
  className: "detail SubagentTurnDetails",
  blockId: (n) => subagentTurnId(sub.id, n),
  anchor: (line) => subagentLineId(sub.id, line),
  permalink: (line) => (sub.id ? sessionSearch(result.session_id, null, null, { subLine: { id: sub.id, n: line } }) : undefined),
});

interface ThreadProps {
  thread: RecordThread;
  call: Call;
  view: RecordView;
}

/** One turn's records, from whichever transcript the thread names (glossary: `TurnRawRecords`). */
export function ThreadRawRecords({ thread, call, view }: ThreadProps) {
  const records = call.records ?? [];
  const { lines } = thread;
  return (
    <div
      className={thread.className}
      style={{ borderRadius: 8, background: "color-mix(in srgb, var(--xh-accent) 5%, transparent)", padding: "0.6rem 0.8rem 1rem" }}
      id={thread.blockId(call.n)}
      data-el={thread.el}
    >
      <h4 className="muted" style={{ margin: "0.6rem 0", fontSize: "0.75rem", fontWeight: 500, letterSpacing: "0.04em", textTransform: "uppercase" }}>
        {thread.what} records for this turn · lines {ranges(records)} · context {pct(call.context_pct)} of {windowLabel(thread.ledger.context_window)}
        <El name={thread.el} />
      </h4>
      {lines == null ? (
        <p>
          <Muted>{thread.error ?? "no captured log beside this result"}</Muted>
        </p>
      ) : records.length === 0 ? (
        <p>
          <Muted>no records attributed to this turn</Muted>
        </p>
      ) : (
        records.map((n) => {
          const raw = lines[n - 1] ?? "";
          let kind = `${thread.harness}/unparseable`;
          try {
            kind = classify(thread.harness, JSON.parse(raw));
          } catch {
            /* unparseable stays unparseable */
          }
          return (
            <RecordCard
              key={n}
              harness={thread.harness}
              lineNo={n}
              raw={raw}
              ctx={ctxFor(thread.ledger, call, kind)}
              view={view}
              anchor={thread.anchor(n)}
              permalink={thread.permalink(n)}
            />
          );
        })
      )}
    </div>
  );
}

interface Props {
  result: RunResult;
  call: Call;
  /** The session log; `lines[n - 1]` is log line `n`. `null` when no log was captured beside the result. */
  lines: string[] | null;
  view: RecordView;
}

/** The primary thread's records for one turn. */
export function TurnRawRecords({ result, call, lines, view }: Props) {
  return <ThreadRawRecords thread={primaryThread(result, lines)} call={call} view={view} />;
}

interface SubagentProps {
  result: RunResult;
  sub: Subagent;
  call: Call;
  /** The subagent's own transcript; `null` while it loads or when none was captured. */
  lines: string[] | null;
  error?: string | null;
  view: RecordView;
}

/** One spawned thread's records for one of its turns (glossary: `SubagentRawRecords`). */
export function SubagentRawRecords({ result, sub, call, lines, error = null, view }: SubagentProps) {
  return <ThreadRawRecords thread={subagentThread(result, sub, lines, error)} call={call} view={view} />;
}
