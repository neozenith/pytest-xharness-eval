import { useEffect, useState } from "react";
import { loadLog } from "@/lib/data";
import type { Cell } from "@/lib/types";

interface Loaded {
  cell: Cell;
  lines: string[];
  error: string | null;
}

/**
 * The session log behind a cell as raw lines. `lines[n - 1]` is log line `n`, the number the
 * ledger's `records` arrays and the report's `L<n>` ids use. `null` while loading.
 */
export function useLog(cell: Cell | undefined): { lines: string[] | null; error: string | null } {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  useEffect(() => {
    if (!cell) return;
    let live = true;
    loadLog(cell)
      .then((text) => live && setLoaded({ cell, lines: splitLog(text), error: null }))
      .catch((e: unknown) => live && setLoaded({ cell, lines: [], error: String(e) }));
    return () => {
      live = false;
    };
  }, [cell]);
  if (!cell || !loaded || loaded.cell !== cell) return { lines: null, error: null };
  return { lines: loaded.lines, error: loaded.error };
}

/** Split a JSONL text into lines, dropping only a trailing empty line so numbering matches the file. */
export function splitLog(text: string): string[] {
  const lines = text.split("\n");
  if (lines.length && lines[lines.length - 1] === "") lines.pop();
  return lines;
}
