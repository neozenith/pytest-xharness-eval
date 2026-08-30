import { caseShort, compact, modelShort, modelShortNames, NONE } from "@/lib/format";

test("a token count abbreviates to three significant figures, and small numbers stay whole", () => {
  expect(compact(1_504_090)).toBe("1.5M");
  expect(compact(29_412)).toBe("29.4k");
  // the boundaries: 1000 is the first `k`, 1e6 the first `M`
  expect(compact(999)).toBe("999");
  expect(compact(1_000)).toBe("1.0k");
  // rounding must not push a figure past its own unit: 999,999 is 1.0M, never `1,000.0k`
  expect(compact(999_999)).toBe("1.0M");
  expect(compact(1_000_000)).toBe("1.0M");
  // one decimal, always — `1.0k` and `29.4k` have to line their points up in a numeric column
  expect(compact(1_050)).toBe("1.1k");
  expect(compact(null)).toBe(NONE);
  expect(compact(Number.NaN)).toBe(NONE);
});

test("a model drops its vendor prefix and a case its eval_ prefix", () => {
  expect(modelShort("claude-sonnet-5")).toBe("sonnet-5");
  expect(modelShort("gpt-5.6-sol")).toBe("5.6-sol");
  // only a leading vendor token, and only once: a model that carries the word elsewhere keeps it
  expect(modelShort("some-claude-thing")).toBe("some-claude-thing");
  expect(caseShort("eval_dual_density")).toBe("dual_density");
  expect(caseShort("dual_density")).toBe("dual_density");
});

test("shortening is abandoned for the whole sweep the moment two models would collide", () => {
  const distinct = modelShortNames(["claude-sonnet-5", "gpt-5.6-sol"]);
  expect(distinct("claude-sonnet-5")).toBe("sonnet-5");
  expect(distinct("gpt-5.6-sol")).toBe("5.6-sol");

  /*
   * Two rows both reading `opus-5` with different titles is worse than a wide column, and a
   * partial map (some short, some full) reads as an inconsistency rather than as a rule — so the
   * collision disables shortening for every model, not just the pair that collided.
   */
  const collides = modelShortNames(["claude-opus-5", "gpt-opus-5", "claude-sonnet-5"]);
  expect(collides("claude-opus-5")).toBe("claude-opus-5");
  expect(collides("gpt-opus-5")).toBe("gpt-opus-5");
  expect(collides("claude-sonnet-5")).toBe("claude-sonnet-5");

  // a model the map never saw still shortens, so a late arrival is never printed as blank
  expect(distinct("claude-haiku-5")).toBe("haiku-5");
});
