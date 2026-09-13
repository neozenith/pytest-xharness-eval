/**
 * `Detail`'s leverage line ("N callers, M sites") is the same "count leverage as
 * callers/call sites" sentence `Lede`'s superlative renders a few hundred lines
 * below in this same file -- and that one pluralises correctly (`caller{n === 1 ?
 * "" : "s"}`). This line did not: it printed the bare nouns unconditionally, so a
 * definition with exactly one caller and one call site read "1 callers, 1 sites".
 * Every existing fixture/story used a node with 0, 2 or 3 of each (see
 * Detail.stories.tsx), so nothing had exercised n=1 here before.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Detail } from "./Panels";
import type { Graph, GraphNode } from "@/lib/types";

const soloNode: GraphNode = {
  id: "src/a.py::once",
  name: "once",
  lang: "python",
  root: "src",
  folder: "src",
  file: "src/a.py",
  cls: null,
  line: 1,
  nloc: 5,
  depth: 1,
  isMethod: false,
  leverage: 1,
  callSites: 1,
  fanOut: 0,
};

const graph: Graph = {
  generated: "2026-09-12T00:00:00Z",
  sources: [{ root: "src", lang: "python", files: 1 }],
  nodes: [soloNode],
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

describe("Detail's leverage line", () => {
  it("singularises caller/site when there is exactly one of each", () => {
    render(<Detail node={soloNode} graph={graph} offSlice={null} />);
    const detail = screen.getByTestId("detail");
    expect(detail.textContent).toContain("1 caller, 1 site");
    expect(detail.textContent).not.toContain("1 callers");
    expect(detail.textContent).not.toContain("1 sites");
  });
});
