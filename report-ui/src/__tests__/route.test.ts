import { overviewSearch, parseSearch, routeSearch, sessionSearch } from "@/lib/route";

test("query routes parse and round-trip; legacy fragments parse identically", () => {
  expect(parseSearch("")).toEqual({ view: "overview", sort: null, theme: null });
  expect(parseSearch("?")).toEqual({ view: "overview", sort: null, theme: null });
  expect(parseSearch("?session=abc")).toEqual({
    view: "session",
    sessionId: "abc",
    turn: null,
    turnView: null,
    axis: null,
    rec: null,
    line: null,
    theme: null,
  });
  expect(parseSearch("?session=abc&turn=3&view=detailed")).toMatchObject({ view: "session", sessionId: "abc", turn: 3, turnView: "detailed" });
  expect(parseSearch("?session=abc&view=line")).toMatchObject({ turnView: null });
  expect(sessionSearch("abc", 2, "summary")).toBe("?session=abc&turn=2&view=summary");
  expect(parseSearch(sessionSearch("a b", 2))).toMatchObject({ view: "session", sessionId: "a b", turn: 2, turnView: null });
  // a legacy #session=… deeplink parses the same, so old links keep working
  expect(parseSearch("#session=abc&turn=3")).toMatchObject({ view: "session", sessionId: "abc", turn: 3 });
});

test("the newer params parse, serialise in a fixed order, and reject junk", () => {
  expect(parseSearch("?session=abc&axis=line&rec=raw&theme=dark")).toMatchObject({ axis: "line", rec: "raw", theme: "dark" });
  expect(parseSearch("?session=abc&axis=banana&rec=x&theme=y&line=abc")).toMatchObject({ axis: null, rec: null, theme: null, line: null });
  expect(parseSearch("?session=abc&line=17")).toMatchObject({ line: 17 });
  expect(sessionSearch("abc", 2, "detailed", { axis: "line", rec: "raw", line: 9, theme: "dark" })).toBe(
    "?session=abc&turn=2&view=detailed&axis=line&rec=raw&line=9&theme=dark",
  );
});

test("overview sort and theme round-trip", () => {
  expect(overviewSearch()).toBe("?");
  expect(overviewSearch({ key: "estimated_cost_usd", dir: "desc" }, "dark")).toBe("?sort=estimated_cost_usd&dir=desc&theme=dark");
  expect(parseSearch("?sort=turns&dir=asc")).toEqual({ view: "overview", sort: { key: "turns", dir: "asc" }, theme: null });
  expect(parseSearch("?sort=turns")).toMatchObject({ sort: { key: "turns", dir: "asc" } });
});

test("routeSearch reproduces exactly the parsed route", () => {
  for (const search of ["?session=abc&turn=2&view=detailed&axis=line&rec=raw&line=9&theme=dark", "?sort=turns&dir=desc&theme=light", "?session=abc"]) {
    expect(routeSearch(parseSearch(search))).toBe(search);
  }
});
