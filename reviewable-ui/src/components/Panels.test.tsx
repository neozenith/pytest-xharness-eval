/**
 * Unit coverage for the sentences `Lede` composes from counts, ratios and
 * superlatives. Storybook (`Lede.stories.tsx`) pins the visual states; this file pins
 * the exact grammar, because a story only fails a reviewer's eye, not a test run.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Lede } from "./Panels";
import type { Cluster, Graph, GraphNode } from "@/lib/types";

const node = (over: Partial<GraphNode> & { id: string }): GraphNode => ({
  name: over.id,
  lang: "python",
  root: "src",
  folder: "src/a",
  file: "src/a/x.py",
  cls: null,
  line: 1,
  nloc: 10,
  depth: 3,
  isMethod: false,
  leverage: 1,
  callSites: 1,
  fanOut: 0,
  ...over,
});

const oneNode = node({ id: "src/a/x.py::solo", leverage: 4, callSites: 5 });

const graph: Graph = {
  generated: "2026-09-12T00:00:00Z",
  sources: [{ root: "src", lang: "python", files: 1 }],
  nodes: [oneNode],
  edges: [],
  clusters: { language: {}, folder: {}, file: {}, class: {} },
  summary: {
    language: { clusters: 1, modularity: 0, insidePct: 100 },
    folder: { clusters: 1, modularity: 0, insidePct: 100 },
    file: { clusters: 1, modularity: 0, insidePct: 100 },
    class: { clusters: 1, modularity: 0, insidePct: 100 },
  },
  totals: {
    nodes: 1,
    edges: 0,
    callSites: 0,
    resolvedPct: 100,
    ambiguous: 0,
    unresolved: 0,
    orphanPct: 0,
    maxDepth: 1,
  },
};

const cluster = (phi: number): Cluster => ({
  internal: 4,
  cut: 1,
  vol: 5,
  phi,
  measurable: true,
  names: 1,
  nloc: 10,
});

const allVisible = new Set([oneNode.id]);

describe("Lede's flat-distribution sentence", () => {
  it("gives the single-cluster case its own sentence -- not a pluralised tie", () => {
    // Exactly one measurable cluster: `lo` and `hi` are the same array entry, so
    // `lo[1].phi === hi[1].phi` is trivially true. That is not evidence of a tie
    // -- there is no second cluster for this one to be tied *with* -- and the old
    // branch rendered it as one anyway ("share the same conductance ... between
    // them"), which is singular-subject-plural-verb agreement failure on top of
    // asserting a tie between a cluster and nothing.
    render(
      <Lede
        graph={graph}
        level="folder"
        clusters={[["src/a", cluster(0.059)]]}
        shown={1}
        total={1}
        visibleIds={allVisible}
        keptIds={allVisible}
      />,
    );

    const lede = screen.getByTestId("lede");
    expect(lede.textContent).not.toMatch(/share the same conductance/);
    expect(lede.textContent).not.toMatch(/between them/);
    // Singular subject needs a singular verb, and "it" refers to the one cluster
    // -- not "they"/"them", which only make sense once a second cluster exists.
    expect(lede.textContent).toContain("Only 1 measurable folder cluster is drawn");
    expect(lede.textContent).not.toContain("1 measurable folder clusters");
  });

  it("still names a real tie once two or more clusters share a phi", () => {
    // The n>1 flat-distribution branch this file's sibling defect left alone --
    // pinned here so the n=1 fix above can't accidentally swallow it.
    render(
      <Lede
        graph={graph}
        level="folder"
        clusters={[
          ["src/a", cluster(0.059)],
          ["src/b", cluster(0.059)],
        ]}
        shown={1}
        total={1}
        visibleIds={allVisible}
        keptIds={allVisible}
      />,
    );

    const lede = screen.getByTestId("lede");
    expect(lede.textContent).toContain("All 2 measurable folder clusters drawn share the same conductance");
  });
});
