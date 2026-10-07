import { describe, expect, it } from "vitest";
import { ALWAYS_SHOWN, COLUMN_PREFS_KEY, allHidden, loadHidden, saveHidden, toggled } from "@/lib/columnPrefs";

/** A storage double: an in-memory map behind the two methods the helpers use. */
function memory(initial?: string): Pick<Storage, "getItem" | "setItem"> & { value: string | null } {
  const store = { value: initial ?? null } as Pick<Storage, "getItem" | "setItem"> & { value: string | null };
  store.getItem = (key: string) => (key === COLUMN_PREFS_KEY ? store.value : null);
  store.setItem = (key: string, v: string) => {
    if (key === COLUMN_PREFS_KEY) store.value = v;
  };
  return store;
}

describe("SessionTable column preferences (ADR 0061)", () => {
  it("round-trips a hidden set through storage, sorted", () => {
    const store = memory();
    saveHidden(new Set(["turns", "coverage"]), store);
    expect(store.value).toBe('["coverage","turns"]');
    expect([...loadHidden(store)].sort()).toEqual(["coverage", "turns"]);
  });

  it("shows every column when nothing usable is stored", () => {
    expect(loadHidden(memory())).toEqual(new Set());
    expect(loadHidden(memory("not json"))).toEqual(new Set());
    expect(loadHidden(memory('{"turns": true}'))).toEqual(new Set());
    expect(loadHidden(memory("[1, 2]"))).toEqual(new Set());
    expect(loadHidden(undefined)).toEqual(new Set());
  });

  it("never hides an always-shown column, even when storage says so", () => {
    expect(loadHidden(memory('["verdict", "case", "turns"]'))).toEqual(new Set(["turns"]));
    expect(toggled(new Set(), "verdict")).toEqual(new Set());
    expect(allHidden(["verdict", "case", "turns", "cost"])).toEqual(new Set(["turns", "cost"]));
    expect(ALWAYS_SHOWN).toEqual(["verdict", "case"]);
  });

  it("toggles a column off and back on", () => {
    const off = toggled(new Set(), "turns");
    expect(off).toEqual(new Set(["turns"]));
    expect(toggled(off, "turns")).toEqual(new Set());
  });

  it("keeps working when storage refuses the write", () => {
    const refusing = {
      setItem: () => {
        throw new Error("QuotaExceededError");
      },
    };
    expect(() => saveHidden(new Set(["turns"]), refusing)).not.toThrow();
  });
});
