import { useEffect, useState } from "react";
import { loadResult } from "@/lib/data";
import type { Cell, RunResult } from "@/lib/types";

interface Loaded {
  cell: Cell;
  result: RunResult | null;
  error: string | null;
}

/** The `.result.json` behind a cell; `null` while loading or when `cell` is undefined. */
export function useResult(cell: Cell | undefined): { result: RunResult | null; error: string | null } {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  useEffect(() => {
    if (!cell) return;
    let live = true;
    loadResult(cell)
      .then((result) => live && setLoaded({ cell, result, error: null }))
      .catch((e: unknown) => live && setLoaded({ cell, result: null, error: String(e) }));
    return () => {
      live = false;
    };
  }, [cell]);
  if (!cell || !loaded || loaded.cell !== cell) return { result: null, error: null };
  return { result: loaded.result, error: loaded.error };
}
