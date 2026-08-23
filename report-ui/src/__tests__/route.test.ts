import { parseHash, sessionHash } from "@/lib/route";

test("hash routes use the first microsite's form and round-trip", () => {
  expect(parseHash("")).toEqual({ view: "overview" });
  expect(parseHash("#")).toEqual({ view: "overview" });
  expect(parseHash("#session=abc")).toEqual({ view: "session", sessionId: "abc", turn: null, turnView: null });
  expect(parseHash("#session=abc&turn=3&view=detailed")).toEqual({ view: "session", sessionId: "abc", turn: 3, turnView: "detailed" });
  expect(parseHash("#session=abc&view=line")).toMatchObject({ turnView: null });
  expect(sessionHash("abc", 2, "summary")).toBe("#session=abc&turn=2&view=summary");
  expect(parseHash(sessionHash("a b", 2))).toEqual({ view: "session", sessionId: "a b", turn: 2, turnView: null });
});
