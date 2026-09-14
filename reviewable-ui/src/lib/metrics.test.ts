/**
 * The two properties this file exists to defend are the two an adversarial review
 * found broken, and neither had a test:
 *
 *   1. Conductance is banded relative to the graph in front of you, never against a
 *      constant. The old `phi < 0.25 ? "low" : ...` was invented, and contradicted
 *      the research the whole app is built on.
 *   2. Every metric bands monotonically in magnitude. Leverage and callSites used to
 *      invert -- leverage 1 banded "high", leverage 3+ banded "low" -- so two of the
 *      five metrics ran on the opposite polarity to the other three while sharing a
 *      single legend.
 *
 * Both regressions were type-clean and test-clean. The second is checked as a
 * property over every metric rather than case-by-case, because "each metric is
 * consistent with itself" is exactly the weaker thing the old tests checked.
 */
import { describe, expect, it } from "vitest";
import { BAND, METRICS, phiScale, type BandKey, type PhiSample } from "./metrics";

const measured = (...phis: number[]): PhiSample[] =>
  phis.map((phi) => ({ phi, measurable: true }));

const RANK: Record<Exclude<BandKey, "none">, number> = { low: 1, mid: 2, high: 3 };

describe("phiScale", () => {
  it("splits at terciles of the measurable clusters, not at fixed thresholds", () => {
    // Nine values, so the nearest-rank cuts land on sorted[3] and sorted[6].
    const s = phiScale(measured(0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09));
    expect(s.n).toBe(9);
    expect(s.cuts).toEqual([0.04, 0.07]);
    expect(s.band(0.01, true)).toBe("low");
    expect(s.band(0.05, true)).toBe("mid");
    expect(s.band(0.09, true)).toBe("high");
  });

  it("bands by rank, so the same phi lands differently in different graphs", () => {
    // 0.3 is the largest value in one graph and the smallest in the other. Under the
    // old absolute thresholds it was "mid" in both, which is the bug: it reported a
    // property of the number rather than a property of the graph.
    const tight = phiScale(measured(0.1, 0.2, 0.3));
    const loose = phiScale(measured(0.3, 0.6, 0.9));
    expect(tight.band(0.3, true)).toBe("high");
    expect(loose.band(0.3, true)).toBe("low");
  });

  it("says nothing when there is no distribution to rank", () => {
    for (const few of [phiScale([]), phiScale(measured(0.4)), phiScale(measured(0.4, 0.8))]) {
      expect(few.cuts).toBeNull();
      expect(few.band(0.4, true)).toBe("mid");
    }
  });

  it("ignores unmeasurable clusters entirely, and bands them `none`", () => {
    const s = phiScale([
      ...measured(0.1, 0.2, 0.3),
      { phi: 0.9, measurable: false },
      { phi: null, measurable: true },
    ]);
    expect(s.n).toBe(3);
    expect(s.cuts).toEqual([0.2, 0.3]);
    expect(s.band(0.9, false)).toBe("none");
    expect(s.band(null, true)).toBe("none");
  });

  it("tolerates a degenerate distribution rather than manufacturing a spread", () => {
    // Every cluster identical: the cuts collapse, "low" is empty, and that is the
    // honest reading -- there is no spread to show.
    const s = phiScale(measured(0.5, 0.5, 0.5, 0.5));
    expect(s.cuts).toEqual([0.5, 0.5]);
    expect(s.band(0.5, true)).toBe("high");
  });
});

describe("metric bands", () => {
  it.each(METRICS.map((m) => [m.id, m] as const))(
    "%s bands monotonically in magnitude",
    (_id, metric) => {
      let seen = 0;
      for (let v = 0; v <= 200; v++) {
        const band = metric.band(v);
        // `none` is reserved for "not measurable" and is not a rank, so it is only
        // legal at zero and is skipped by the monotonicity check.
        if (band === "none") {
          expect(v).toBe(0);
          continue;
        }
        expect(RANK[band]).toBeGreaterThanOrEqual(seen);
        seen = RANK[band];
      }
      // A metric that never leaves one band would pass the check above vacuously.
      expect(seen).toBe(RANK.high);
    },
  );

  it("uses every band across the five metrics, and only the four that exist", () => {
    const used = new Set(METRICS.flatMap((m) => [0, 1, 2, 3, 20, 50, 200].map((v) => m.band(v))));
    expect([...used].sort()).toEqual(["high", "low", "mid", "none"]);
    expect(Object.keys(BAND).sort()).toEqual(["high", "low", "mid", "none"]);
  });
});
