/**
 * `ClusterTable`'s caption states a population its cuts (or lack of cuts) were
 * computed over -- `phiScale` is built from EVERY cluster at this boundary across
 * the whole graph (lib/graph.ts's `toElements`), not from the `clusters` prop this
 * table actually renders rows for, which is narrowed to whatever the current
 * filters left `used` (see `toElements`'s `used` set). The cuts-branch of the
 * caption already says so out loud ("this graph's N measurable clusters"); this
 * file pins that the no-cuts branch says it too, rather than stating a bare count
 * a reader would reasonably read as "rows in the table below me".
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ClusterTable } from "./Panels";
import type { PhiScale } from "@/lib/metrics";
import type { Cluster } from "@/lib/types";

const cluster = (phi: number | null): Cluster => ({
  internal: 4,
  cut: 1,
  vol: 5,
  phi,
  measurable: phi !== null,
  names: 1,
  nloc: 10,
});

describe("ClusterTable's caption, when there are too few clusters to rank", () => {
  it("attributes its count to the whole graph, not to the (possibly filtered) rows below it", () => {
    // Reproduces a real filtered view: the fixture graph has 2 measurable folder
    // clusters overall (phiScale.n = 2, below the tercile floor of 3, so cuts is
    // null), but a language filter narrowing the view to one folder leaves only 1
    // row for this table to actually draw -- the caption's count and the table's
    // row count now genuinely disagree, and the caption has to say why.
    const phiScale: PhiScale = {
      cuts: null,
      n: 2,
      band: () => "mid",
    };
    render(
      <ClusterTable
        clusters={[["web/app/components", cluster(0)]]}
        level="folder"
        roots={["src/pkg", "web/app"]}
        phiScale={phiScale}
      />,
    );

    const caption = screen.getByText(/measurable cluster/).closest("caption")!;
    expect(caption.textContent).toContain("This graph has 2 measurable clusters");
    // The old wording stated the bare count with nothing to mark it as a
    // graph-wide figure, which reads as a claim about the one row actually drawn.
    expect(caption.textContent).not.toMatch(/^\s*2 measurable clusters at this boundary/);
  });
});
