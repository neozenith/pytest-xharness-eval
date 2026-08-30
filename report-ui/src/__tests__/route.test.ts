import { overviewSearch, overviewWith, parseSearch, routeSearch, sessionSearch } from "@/lib/route";

test("query routes parse and round-trip; legacy fragments parse identically", () => {
  const noFacets = { skill: null, harness: null, model: null };
  const bare = { view: "overview", sort: null, summarySort: null, facets: noFacets, theme: null };
  expect(parseSearch("")).toEqual(bare);
  expect(parseSearch("?")).toEqual(bare);
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
  expect(parseSearch("?sort=turns&dir=asc")).toEqual({
    view: "overview",
    sort: { key: "turns", dir: "asc" },
    summarySort: null,
    facets: { skill: null, harness: null, model: null },
    theme: null,
  });
  expect(parseSearch("?sort=turns")).toMatchObject({ sort: { key: "turns", dir: "asc" } });
});

test("the two overview tables sort on their own param pairs, and neither disturbs the other", () => {
  // one URL expresses both orders at once, which is the whole reason for the second pair
  const both = parseSearch("?sort=turns&dir=desc&ssort=cost&sdir=asc");
  expect(both).toMatchObject({ sort: { key: "turns", dir: "desc" }, summarySort: { key: "cost", dir: "asc" } });
  expect(routeSearch(both)).toBe("?sort=turns&dir=desc&ssort=cost&sdir=asc");
  // the summary pair alone leaves the session table on its own default
  expect(parseSearch("?ssort=billed&sdir=desc")).toMatchObject({ sort: null, summarySort: { key: "billed", dir: "desc" } });
  // a key with no direction is ascending; a direction with no key is not a sort at all
  expect(parseSearch("?ssort=runs")).toMatchObject({ summarySort: { key: "runs", dir: "asc" } });
  expect(parseSearch("?sdir=desc")).toMatchObject({ summarySort: null });
  expect(parseSearch("?ssort=runs&sdir=sideways")).toMatchObject({ summarySort: { key: "runs", dir: "asc" } });
});

test("overviewWith changes one param and carries every sibling through", () => {
  const start = parseSearch("?sort=turns&dir=desc&ssort=cost&sdir=asc&harness=claude&theme=dark");
  // the bug this exists to prevent: a control that respelled the route dropped whatever it
  // predated — the filter chips cleared `sort`, and the sort heads cleared `facets`
  expect(overviewWith(start, { summarySort: { key: "runs", dir: "desc" } })).toEqual({
    ...start,
    summarySort: { key: "runs", dir: "desc" },
  });
  // from a session route only the theme survives: there is no overview state to preserve
  expect(overviewWith(parseSearch("?session=abc&theme=dark"), { sort: { key: "at", dir: "asc" } })).toEqual({
    view: "overview",
    sort: { key: "at", dir: "asc" },
    summarySort: null,
    facets: { skill: null, harness: null, model: null },
    theme: "dark",
  });
});

test("the three overview facets parse as lists, and absent or empty means every value", () => {
  expect(parseSearch("?skill=discovery&harness=claude,codex")).toMatchObject({
    view: "overview",
    facets: { skill: ["discovery"], harness: ["claude", "codex"], model: null },
  });
  // present-but-empty is still "every skill", never "no skill"
  expect(parseSearch("?skill=")).toMatchObject({ facets: { skill: null } });
  // trimmed, empties dropped, deduped first-wins
  expect(parseSearch("?skill=a,,%20a%20,b")).toMatchObject({ facets: { skill: ["a", "b"] } });
  // a value the data does not carry is kept, so the URL round-trips and lands on the empty state
  expect(parseSearch("?harness=gone")).toMatchObject({ facets: { harness: ["gone"] } });
  // a session URL never carries them
  const session = parseSearch("?session=abc&skill=discovery");
  expect(session.view).toBe("session");
  expect(session).not.toHaveProperty("facets");
});

test("facets serialise last, in a fixed order, with literal commas", () => {
  expect(overviewSearch(null, null, { skill: ["discovery"], harness: null, model: null })).toBe("?skill=discovery");
  expect(overviewSearch(null, null, { harness: ["b", "c"], skill: null, model: null })).toBe("?harness=b,c");
  expect(overviewSearch({ key: "turns", dir: "desc" }, "dark", { skill: ["a"], harness: ["b", "c"], model: ["d"] })).toBe(
    "?sort=turns&dir=desc&skill=a&harness=b,c&model=d&theme=dark",
  );
  // today's deeplinks stay byte-identical: the third argument is optional and last
  expect(overviewSearch()).toBe("?");
  expect(overviewSearch({ key: "estimated_cost_usd", dir: "desc" }, "dark")).toBe("?sort=estimated_cost_usd&dir=desc&theme=dark");
  expect(overviewSearch(null, null, { skill: null, harness: null, model: null })).toBe("?");
});

test("routeSearch reproduces exactly the parsed route", () => {
  for (const search of [
    "?session=abc&turn=2&view=detailed&axis=line&rec=raw&line=9&theme=dark",
    "?sort=turns&dir=desc&theme=light",
    "?session=abc",
    "?sort=turns&dir=desc&skill=discovery&harness=claude,codex&theme=dark",
  ]) {
    expect(routeSearch(parseSearch(search))).toBe(search);
  }
});
