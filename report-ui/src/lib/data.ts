/**
 * Where the page's data comes from (ADR 0020, ADR 0024): the inline payload when
 * `report.py --inline` embedded one, otherwise fetched from beside the page. Every
 * accessor goes through here so a component never knows which mode it is in.
 */
import type { Cell, DesignTokens, Index, RunResult } from "./types";

const inline = () => (typeof window === "undefined" ? undefined : window.__XH_DATA__);

/**
 * In-flight load counter, exposed as `window.__XH_PENDING__` so an end-to-end test can
 * wait for "every fetch this route started has settled" instead of guessing with sleeps.
 */
function track<T>(p: Promise<T>): Promise<T> {
  if (typeof window === "undefined") return p;
  window.__XH_PENDING__ = (window.__XH_PENDING__ ?? 0) + 1;
  return p.finally(() => {
    window.__XH_PENDING__ = (window.__XH_PENDING__ ?? 1) - 1;
  });
}

async function getJSON<T>(path: string): Promise<T> {
  return track(
    (async () => {
      const res = await fetch(path, { cache: "no-store" });
      if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
      return (await res.json()) as T;
    })(),
  );
}

async function getText(path: string): Promise<string> {
  return track(
    (async () => {
      const res = await fetch(path, { cache: "no-store" });
      if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
      return res.text();
    })(),
  );
}

export const loadIndex = (): Promise<Index> => {
  const d = inline();
  return d ? Promise.resolve(d.index) : getJSON<Index>("index.json");
};

export const loadTokens = (): Promise<DesignTokens> => {
  const d = inline();
  return d ? Promise.resolve(d.tokens) : getJSON<DesignTokens>("report.tokens.json");
};

const resultCache = new Map<string, Promise<RunResult>>();

export const loadResult = (cell: Cell): Promise<RunResult> => {
  const d = inline();
  if (d) {
    const r = d.results[cell.session_id];
    return r ? Promise.resolve(r) : Promise.reject(new Error(`no inline result for ${cell.session_id}`));
  }
  let p = resultCache.get(cell.result);
  if (!p) {
    p = getJSON<RunResult>(cell.result);
    resultCache.set(cell.result, p);
  }
  return p;
};

export const loadLog = (cell: Cell): Promise<string> => {
  const d = inline();
  if (d) return Promise.resolve(d.logs[cell.session_id] ?? "");
  return cell.log ? getText(cell.log) : Promise.resolve("");
};

export const isInline = () => Boolean(inline());
