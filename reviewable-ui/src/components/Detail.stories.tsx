import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";
import { Detail } from "@/components/Panels";
import { calledNode, emptyGraph, hubNode, orphanNode, sampleGraph } from "@/stories/fixtures";
import type { Graph, GraphNode } from "@/lib/types";

/** Rendered inside the same `<aside className="right">` (with its heading) `App.tsx` places it in. */
const meta = {
  title: "Panels/Detail",
  component: Detail,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <aside className="right" aria-labelledby="inspector-heading" style={{ width: 320 }}>
        <h2 id="inspector-heading" className="sr-only">
          Inspector
        </h2>
        <Story />
      </aside>
    ),
  ],
  args: {
    graph: sampleGraph,
    onSelect: fn(),
  },
} satisfies Meta<typeof Detail>;

export default meta;
type Story = StoryObj<typeof meta>;

/** Nothing tapped yet: the prompt copy, not a blank panel. */
export const NoSelection: Story = {
  args: { node: null },
};

/** A hub: calls three other definitions, is called by none. Every "Calls" row is a button. */
export const Hub: Story = {
  args: { node: hubNode },
};

/** Called from two places, calls out to nothing -- both lists render, one of them empty. */
export const Called: Story = {
  args: { node: calledNode },
};

/**
 * Exactly one caller, one call site: "leverage" used to read "1 callers, 1 sites"
 * unconditionally, the same singular/plural agreement failure the Lede fix (a few
 * hundred lines below this same component in Panels.tsx) already had to fix for
 * its own "N caller(s), M call site(s)" sentence -- this line just hadn't been.
 * `Widget.constructor` (fixtures.ts) is the only sample node with leverage exactly 1.
 */
const soloLeverageNode: GraphNode = {
  id: "src/solo.py::once",
  name: "once",
  lang: "python",
  root: "src",
  folder: "src",
  file: "src/solo.py",
  cls: null,
  line: 1,
  nloc: 5,
  depth: 1,
  isMethod: false,
  leverage: 1,
  callSites: 1,
  fanOut: 0,
};
export const SingleCallerAndSite: Story = {
  args: { node: soloLeverageNode },
};

/** A true orphan: no caller and no callee in the graph. Both "Called by" and "Calls" read (0). */
export const Orphan: Story = {
  args: { node: orphanNode },
};

/**
 * Selected, but excluded by a filter -- reachable by clicking a caller in this very
 * panel, or the lede's link, while a search or language filter is narrowing the view.
 * Design-review finding #6: the canvas says nothing about a node it never drew, so
 * without this the panel describes a definition the reader cannot find on screen.
 */
export const OffSliceFiltered: Story = {
  args: { node: calledNode, offSlice: "filtered" },
};

/**
 * Selected, but past the node cap. Same situation, different remedy -- which is why
 * `offSlice` is a union and not a boolean: "clear the filter" and "raise the cap" are
 * different next actions, and "not shown" would tell the reader neither.
 */
export const OffSliceCapped: Story = {
  args: { node: hubNode, offSlice: "capped" },
};

/**
 * Design-review round 3, finding #2 -- verified real: `sampleGraph`'s highest degree
 * is well under 12 (the reviewer could not reproduce this on the app's own fixtures
 * for the same reason), so this story builds a node with 15 callers specifically to
 * cross the render cap. Before the fix, "Called by (15)" rendered only 12 buttons
 * with nothing marking the other 3 as cut; the fix names them instead of dropping
 * them silently, the same rule the node-cap banner already applies one panel over.
 */
const popularNode: GraphNode = {
  id: "src/hub.py::popular",
  name: "popular",
  lang: "python",
  root: "src",
  folder: "src",
  file: "src/hub.py",
  cls: null,
  line: 1,
  nloc: 12,
  depth: 1,
  isMethod: false,
  leverage: 15,
  callSites: 15,
  fanOut: 0,
};
const callerNodes: GraphNode[] = Array.from({ length: 15 }, (_, i) => ({
  id: `src/callers.py::caller_${i}`,
  name: `caller_${i}`,
  lang: "python",
  root: "src",
  folder: "src",
  file: "src/callers.py",
  cls: null,
  line: i + 1,
  nloc: 4,
  depth: 1,
  isMethod: false,
  leverage: 0,
  callSites: 0,
  fanOut: 1,
}));
const manyCallersGraph: Graph = {
  ...emptyGraph,
  nodes: [popularNode, ...callerNodes],
  edges: callerNodes.map((c) => ({ source: c.id, target: popularNode.id, sites: 1 })),
};
export const ManyCallers: Story = {
  args: { graph: manyCallersGraph, node: popularNode },
};
