/**
 * The reader's SessionTable column preference (ADR 0061): which columns they have turned off.
 *
 * A per-viewer convenience, so it lives in this browser's storage and nowhere else: it is not
 * part of a shared link, and a page whose storage is blocked (a private window, a
 * `file://` origin with site data cleared) simply shows every column. Every read and write is
 * guarded for that reason, and a stored value that is not a list of strings is ignored.
 */

/** The storage key, versioned so a future shape can be told apart from this one. */
export const COLUMN_PREFS_KEY = "xharness.sessionTable.hiddenColumns.v1";

/** The columns a reader can never turn off: without them a row cannot be read at all. */
export const ALWAYS_SHOWN: readonly string[] = ["verdict", "case"];

/** The columns this reader has turned off, or none when nothing usable is stored. */
export function loadHidden(storage: Pick<Storage, "getItem"> | undefined = safeStorage()): Set<string> {
  try {
    const raw = storage?.getItem(COLUMN_PREFS_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed) || !parsed.every((k) => typeof k === "string")) return new Set();
    return new Set(parsed.filter((k) => !ALWAYS_SHOWN.includes(k)));
  } catch {
    return new Set();
  }
}

/** Remember ``hidden`` for this reader; a blocked storage keeps the choice for this page only. */
export function saveHidden(hidden: ReadonlySet<string>, storage: Pick<Storage, "setItem"> | undefined = safeStorage()): void {
  try {
    storage?.setItem(COLUMN_PREFS_KEY, JSON.stringify([...hidden].sort()));
  } catch {
    // Storage refused the write: the preference still applies until the page reloads.
  }
}

/** ``hidden`` with ``key`` flipped; an always-shown column is never hidden. */
export function toggled(hidden: ReadonlySet<string>, key: string): Set<string> {
  const next = new Set(hidden);
  if (next.has(key)) next.delete(key);
  else if (!ALWAYS_SHOWN.includes(key)) next.add(key);
  return next;
}

/** Every optional column hidden: what "Deselect all" leaves. */
export function allHidden(keys: readonly string[]): Set<string> {
  return new Set(keys.filter((k) => !ALWAYS_SHOWN.includes(k)));
}

function safeStorage(): Storage | undefined {
  try {
    return typeof window === "undefined" ? undefined : window.localStorage;
  } catch {
    return undefined;
  }
}
