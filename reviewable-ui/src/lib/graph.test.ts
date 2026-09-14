import { describe, expect, it } from "vitest";
import { DEFAULT_FILTERS, shortCluster, toElements } from "./graph";
import { metricById } from "./metrics";
import { clusterOf, type Graph, type GraphNode } from "./types";

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
  leverage: 0,
  callSites: 0,
  fanOut: 0,
  ...over,
});

const graph = (nodes: GraphNode[], edges: Graph["edges"] = []): Graph => ({
  generated: "2026-09-12T00:00:00Z",
  sources: [{ root: "src", lang: "python", files: 1 }],
  nodes,
  edges,
  clusters: {
    language: {
      python: {
        internal: 1,
        cut: 0,
        vol: 2,
        phi: 0,
        measurable: false,
        names: nodes.length,
        nloc: 10,
      },
    },
    folder: {
      "src/a": {
        internal: 1,
        cut: 0,
        vol: 2,
        phi: 0.1,
        measurable: true,
        names: nodes.length,
        nloc: 10,
      },
    },
    file: {
      "src/a/x.py": {
        internal: 1,
        cut: 0,
        vol: 2,
        phi: 0.2,
        measurable: true,
        names: nodes.length,
        nloc: 10,
      },
    },
    class: {},
  },
  summary: {
    language: { clusters: 1, modularity: 0, insidePct: 100 },
    folder: { clusters: 1, modularity: 0.5, insidePct: 80 },
    file: { clusters: 1, modularity: 0.4, insidePct: 60 },
    class: { clusters: 0, modularity: 0, insidePct: 0 },
  },
  totals: {
    nodes: nodes.length,
    edges: edges.length,
    callSites: edges.length,
    resolvedPct: 100,
    ambiguous: 0,
    unresolved: 0,
    orphanPct: 0,
    maxDepth: 3,
  },
});

describe("clusterOf", () => {
  it("returns the key for each boundary level", () => {
    const n = node({ id: "a", cls: "K" });
    expect(clusterOf(n, "language")).toBe("python");
    expect(clusterOf(n, "folder")).toBe("src/a");
    expect(clusterOf(n, "file")).toBe("src/a/x.py");
    expect(clusterOf(n, "class")).toBe("src/a/x.py::K");
  });

  it("names the module pseudo-class when there is no class", () => {
    expect(clusterOf(node({ id: "a" }), "class")).toBe("src/a/x.py::<module>");
  });
});

describe("toElements", () => {
  const metric = metricById("leverage");

  it("emits one compound parent per used cluster, plus the nodes", () => {
    const g = graph([node({ id: "a" }), node({ id: "b" })]);
    const s = toElements(g, "folder", metric, DEFAULT_FILTERS);
    expect(s.elements.filter((e) => e.data.kind === "cluster")).toHaveLength(1);
    expect(s.elements.filter((e) => e.data.kind === "def")).toHaveLength(2);
    expect(s.shown).toBe(2);
  });

  it("drops edges whose endpoints were filtered out", () => {
    const g = graph(
      [node({ id: "a" }), node({ id: "b", lang: "typescript" })],
      [{ source: "a", target: "b", sites: 1 }],
    );
    const s = toElements(g, "folder", metric, {
      ...DEFAULT_FILTERS,
      langs: ["python"],
    });
    expect(s.elements.some((e) => e.data.source)).toBe(false);
  });

  it("drops edges below the weight floor", () => {
    const g = graph(
      [node({ id: "a" }), node({ id: "b" })],
      [{ source: "a", target: "b", sites: 1 }],
    );
    expect(
      toElements(g, "folder", metric, {
        ...DEFAULT_FILTERS,
        minWeight: 2,
      }).elements.some((e) => e.data.source),
    ).toBe(false);
    expect(
      toElements(g, "folder", metric, {
        ...DEFAULT_FILTERS,
        minWeight: 1,
      }).elements.some((e) => e.data.source),
    ).toBe(true);
  });

  it("keeps the highest-metric nodes when the cap bites", () => {
    const g = graph([
      node({ id: "low", leverage: 0 }),
      node({ id: "high", leverage: 9 }),
      node({ id: "mid", leverage: 4 }),
    ]);
    const s = toElements(g, "folder", metric, { ...DEFAULT_FILTERS, limit: 2 });
    const ids = s.elements
      .filter((e) => e.data.kind === "def")
      .map((e) => e.data.id);
    expect(ids).toContain("high");
    expect(ids).toContain("mid");
    expect(ids).not.toContain("low");
    expect(s.hiddenByLimit).toBe(1);
  });

  it("hides orphans only when asked", () => {
    const g = graph([
      node({ id: "a", leverage: 0 }),
      node({ id: "b", leverage: 2 }),
    ]);
    expect(toElements(g, "folder", metric, DEFAULT_FILTERS).shown).toBe(2);
    expect(
      toElements(g, "folder", metric, { ...DEFAULT_FILTERS, hideOrphans: true })
        .shown,
    ).toBe(1);
  });

  it("matches the search against name and file", () => {
    const g = graph([
      node({ id: "alpha", name: "alpha" }),
      node({ id: "beta", name: "beta" }),
    ]);
    expect(
      toElements(g, "folder", metric, { ...DEFAULT_FILTERS, search: "alph" })
        .shown,
    ).toBe(1);
    expect(
      toElements(g, "folder", metric, { ...DEFAULT_FILTERS, search: "x.py" })
        .shown,
    ).toBe(2);
  });
});

describe("shortCluster", () => {
  it("keeps the tail of a path and splits a class key", () => {
    expect(shortCluster("src/pytest_xharness_eval/model", "folder")).toBe(
      "pytest_xharness_eval/model",
    );
    expect(shortCluster("src/a/x.py::K", "class")).toBe("x.py · K");
    expect(shortCluster("python", "language")).toBe("python");
  });
});
