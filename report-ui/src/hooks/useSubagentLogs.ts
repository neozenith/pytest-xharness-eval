import { useEffect, useState } from "react";
import { loadSubagentLog } from "@/lib/data";
import type { Cell, RunResult, Subagent } from "@/lib/types";
import { splitLog } from "./useLog";

/** One spawned thread's transcript as raw lines; `lines[n - 1]` is the line its ledger calls `n`. */
export interface SubagentLog {
  lines: string[];
  error: string | null;
}

interface Loaded {
  result: RunResult;
  logs: Map<string, SubagentLog>;
}

/**
 * Every transcript this session's subagents left (ADR 0033), keyed by subagent id — `null`
 * while any of them is still loading, so a band can say "loading" rather than claim the
 * thread has no records.
 *
 * The whole set loads in one pass: a session spawns a handful of threads at most, they are
 * fetched (or read out of the inline payload) together, and the map appears only once they
 * have all settled — one state transition rather than one per thread. A thread whose
 * transcript could not be read is in the map with its error, never missing from it.
 *
 * Eager, not per-opened-band: a transcript is a fraction of the session log beside it (64KB
 * of threads against 3.0MB of primary logs across the sweep this was built on), the whole
 * lot is already resident on an inline page, and loading on open would put a spinner inside
 * every band the reader expands. The cost that would be worth deferring is the *rendering*
 * — `view=detailed` mounts a `RecordCard` per line of every turn of every thread, on top of
 * the primary transcript already doing the same — and that budget belongs to the view
 * toggle, which has always spent it that way for the primary thread.
 */
export function useSubagentLogs(cell: Cell | undefined, result: RunResult | null): Map<string, SubagentLog> | null {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  useEffect(() => {
    if (!cell || !result) return;
    let live = true;
    const subs: Subagent[] = result.subagents ?? [];
    void Promise.all(
      subs.map(async (sub): Promise<[string, SubagentLog]> => {
        try {
          return [sub.id, { lines: splitLog(await loadSubagentLog(cell, sub)), error: null }];
        } catch (e: unknown) {
          return [sub.id, { lines: [], error: String(e) }];
        }
      }),
    ).then((entries) => {
      if (live) setLoaded({ result, logs: new Map(entries) });
    });
    return () => {
      live = false;
    };
  }, [cell, result]);
  if (!cell || !result) return null;
  return loaded?.result === result ? loaded.logs : null;
}
