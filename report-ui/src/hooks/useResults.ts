import { useEffect, useState } from "react";
import { loadResult } from "@/lib/data";
import type { Cell, RunResult } from "@/lib/types";

/** Every ledgered cell's result, keyed by session id, for the overview chart; fills in as they load. */
export function useResults(cells: Cell[]): Record<string, RunResult | null> {
  const [results, setResults] = useState<Record<string, RunResult | null>>({});
  useEffect(() => {
    let live = true;
    const wanted = cells.filter((c) => c.has_ledger);
    Promise.all(
      wanted.map((c) =>
        loadResult(c)
          .then((r) => [c.session_id, r] as const)
          .catch(() => [c.session_id, null] as const),
      ),
    ).then((pairs) => live && setResults(Object.fromEntries(pairs)));
    return () => {
      live = false;
    };
  }, [cells]);
  return results;
}
