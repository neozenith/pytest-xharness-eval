import { aggregatesTitle, formatAggregate, headline, headlineValue, metricName } from "@/lib/metrics";
import { IMPORTANT_METRICS } from "./metricsDoc";

const metric = (id: string) => IMPORTANT_METRICS.find((m) => m.id === id)!;

test("the headline is the declaration's first aggregate", () => {
  expect(headline(metric("cost"))).toBe("median");
  expect(headline(metric("context"))).toBe("mean");
  expect(headline(metric("compactions"))).toBe("mean");
  expect(headline(metric("verdict"))).toBe("pass_rate");
  expect(headlineValue(metric("cost"), { median: 0.4, n: 1 })).toBe(0.4);
  expect(headlineValue(metric("cost"), undefined)).toBeNull();
});

test("an aggregate prints in its metric's unit, and a share of samples as a percentage whatever the unit", () => {
  expect(formatAggregate(metric("cost"), "median", 0.41234)).toBe("$0.412");
  expect(formatAggregate(metric("tokens"), "median", 120_245)).toBe("120.2k");
  expect(formatAggregate(metric("context"), "mean", 12.04)).toBe("12.0%");
  expect(formatAggregate(metric("thinking"), "mean", 0.25)).toBe("25.0%");
  expect(formatAggregate(metric("wall"), "median", 61_500)).toBe("61.5s");
  expect(formatAggregate(metric("throughput"), "median", 41.27)).toBe("41.3");
  expect(formatAggregate(metric("compactions"), "mean", 2)).toBe("2");
  expect(formatAggregate(metric("compactions"), "mean", 0.5)).toBe("0.5");
  // `share` is a share of samples even on a count metric: "half the runs compacted"
  expect(formatAggregate(metric("compactions"), "share", 0.5)).toBe("50.0%");
  expect(formatAggregate(metric("cost"), "n", 3)).toBe("3");
  expect(formatAggregate(metric("cost"), "median", null)).toBe("–");
});

test("a column's name is its headline's operation and the field it reduces", () => {
  expect(metricName(metric("cost"))).toBe("median estimated_cost_usd");
  expect(metricName(metric("skill_loaded"))).toBe("mean skill_files_loaded / skill_files");
});

test("a title spells out every aggregate in declaration order, a missing one as the glyph", () => {
  expect(aggregatesTitle(metric("subagents"), { mean: 0.5, share: 0.25, n: 4 })).toBe("mean 0.5 · share of samples with any 25.0% · n 4");
  expect(aggregatesTitle(metric("cost"), { median: null, p25: null, p75: null, n: 0 })).toBe("median – · p25 – · p75 – · n 0");
});
